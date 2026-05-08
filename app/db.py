"""AI Remote Compute Mesh — 数据库操作"""
import sqlite3
from config import DB_PATH
from logger import log

def init_db():
    db = sqlite3.connect(DB_PATH, check_same_thread=False)
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA foreign_keys=ON")

    db.executescript("""
        CREATE TABLE IF NOT EXISTS conversations (
            id    INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            model TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
        );
        CREATE TABLE IF NOT EXISTS messages (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id INTEGER NOT NULL,
            role            TEXT NOT NULL,
            content         TEXT NOT NULL,
            model           TEXT NOT NULL DEFAULT '',
            created_at      TEXT NOT NULL DEFAULT (datetime('now','localtime')),
            FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS users (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            username    TEXT NOT NULL UNIQUE,
            password    TEXT NOT NULL,
            role        TEXT NOT NULL DEFAULT 'user',
            approved    INTEGER NOT NULL DEFAULT 0,
            created_at  TEXT NOT NULL DEFAULT (datetime('now','localtime')),
            approved_at TEXT
        );
        CREATE TABLE IF NOT EXISTS sessions (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id    INTEGER NOT NULL,
            token      TEXT NOT NULL UNIQUE,
            created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
            expires_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );
    """)

    # 迁移：为旧数据库补充列
    for col, ddl in [
        ("model",      "ALTER TABLE messages ADD COLUMN model TEXT NOT NULL DEFAULT ''"),
        ("user_id",    "ALTER TABLE conversations ADD COLUMN user_id INTEGER REFERENCES users(id) ON DELETE SET NULL"),
        ("eval_count", "ALTER TABLE messages ADD COLUMN eval_count INTEGER NOT NULL DEFAULT 0"),
    ]:
        try:
            db.execute(ddl)
        except sqlite3.OperationalError:
            pass

    db.execute("CREATE INDEX IF NOT EXISTS idx_sessions_token ON sessions(token)")
    db.execute("CREATE INDEX IF NOT EXISTS idx_conversations_user ON conversations(user_id)")

    # 首次运行：创建默认管理员
    cur = db.execute("SELECT COUNT(*) FROM users")
    if cur.fetchone()[0] == 0:
        from auth import hash_password
        from config import ADMIN_DEFAULT_PASSWORD
        db.execute(
            "INSERT INTO users (username, password, role, approved, approved_at) VALUES (?, ?, 'admin', 1, datetime('now','localtime'))",
            ("admin", hash_password(ADMIN_DEFAULT_PASSWORD))
        )
        db.commit()
        log.warning("============================================")
        log.warning("  已创建默认管理员账号:")
        log.warning("  用户名: admin")
        log.warning("  密码:   %s", ADMIN_DEFAULT_PASSWORD)
        log.warning("  请登录后立即修改密码！")
        log.warning("============================================")

    return db


# ==================== 用户操作 ====================

def create_user(db, username: str, password_hash: str) -> int | None:
    try:
        cur = db.execute(
            "INSERT INTO users (username, password) VALUES (?, ?)",
            (username, password_hash)
        )
        db.commit()
        return cur.lastrowid
    except sqlite3.IntegrityError:
        return None  # 用户名已存在

def get_user_by_username(db, username: str) -> dict | None:
    cur = db.execute(
        "SELECT id, username, password, role, approved FROM users WHERE username=?",
        (username,)
    )
    row = cur.fetchone()
    if not row:
        return None
    return {"id": row[0], "username": row[1], "password": row[2], "role": row[3], "approved": bool(row[4])}

def get_user_by_id(db, user_id: int) -> dict | None:
    cur = db.execute(
        "SELECT id, username, role, approved FROM users WHERE id=?", (user_id,)
    )
    row = cur.fetchone()
    if not row:
        return None
    return {"id": row[0], "username": row[1], "role": row[2], "approved": bool(row[3])}

def list_users(db) -> list[dict]:
    cur = db.execute(
        "SELECT id, username, role, approved, created_at, approved_at FROM users ORDER BY created_at DESC"
    )
    return [
        {"id": r[0], "username": r[1], "role": r[2], "approved": bool(r[3]),
         "created_at": r[4], "approved_at": r[5]}
        for r in cur
    ]

def approve_user(db, user_id: int) -> bool:
    cur = db.execute(
        "UPDATE users SET approved=1, approved_at=datetime('now','localtime') WHERE id=? AND approved=0",
        (user_id,)
    )
    db.commit()
    return cur.rowcount > 0

def delete_user(db, user_id: int) -> bool:
    cur = db.execute("DELETE FROM users WHERE id=?", (user_id,))
    db.commit()
    return cur.rowcount > 0


# ==================== 会话操作 ====================

def create_session(db, user_id: int, token: str, expires_at: str):
    db.execute(
        "INSERT INTO sessions (user_id, token, expires_at) VALUES (?, ?, ?)",
        (user_id, token, expires_at)
    )
    db.commit()

def validate_session(db, token: str) -> dict | None:
    cur = db.execute("""
        SELECT u.id, u.username, u.role, u.approved, s.expires_at
        FROM sessions s JOIN users u ON s.user_id = u.id
        WHERE s.token = ?
    """, (token,))
    row = cur.fetchone()
    if not row:
        return None
    from datetime import datetime
    expires = datetime.fromisoformat(row[4])
    if datetime.now() > expires:
        db.execute("DELETE FROM sessions WHERE token=?", (token,))
        db.commit()
        return None
    return {"id": row[0], "username": row[1], "role": row[2], "approved": bool(row[3])}

def delete_session(db, token: str):
    db.execute("DELETE FROM sessions WHERE token=?", (token,))
    db.commit()


# ==================== 对话操作 ====================

def list_conversations(db, user_id: int) -> list[dict]:
    cur = db.execute(
        "SELECT id, title, model, created_at FROM conversations WHERE user_id=? ORDER BY created_at DESC",
        (user_id,)
    )
    return [{"id": r[0], "title": r[1], "model": r[2], "created_at": r[3]} for r in cur]

def get_conversation(db, conv_id: int) -> dict | None:
    cur = db.execute("SELECT role, content, model, eval_count FROM messages WHERE conversation_id=? ORDER BY id ASC", (conv_id,))
    msgs = [{"role": r[0], "content": r[1], "model": r[2], "eval_count": r[3]} for r in cur]
    meta = db.execute("SELECT title, model, user_id FROM conversations WHERE id=?", (conv_id,)).fetchone()
    if not meta:
        return None
    return {"id": int(conv_id), "title": meta[0], "model": meta[1], "user_id": meta[2], "messages": msgs}

def create_conversation(db, title: str, model: str, user_id: int) -> int:
    cur = db.execute(
        "INSERT INTO conversations (title, model, user_id) VALUES (?, ?, ?)",
        (title, model, user_id)
    )
    db.commit()
    return cur.lastrowid

def save_messages(db, conv_id: int, msgs: list, title: str = None, model: str = None):
    for msg in msgs:
        db.execute(
            "INSERT INTO messages (conversation_id, role, content, model, eval_count) VALUES (?, ?, ?, ?, ?)",
            (conv_id, msg.get("role"), msg.get("content"), msg.get("model", ""), msg.get("eval_count", 0))
        )
    if title:
        db.execute("UPDATE conversations SET title=? WHERE id=?", (title, conv_id))
    if model:
        db.execute("UPDATE conversations SET model=? WHERE id=?", (model, conv_id))
    db.commit()

def delete_conversation(db, conv_id: int):
    db.execute("DELETE FROM conversations WHERE id=?", (conv_id,))
    db.commit()
