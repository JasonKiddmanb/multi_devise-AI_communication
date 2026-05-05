#!/usr/bin/env python3
"""AI Remote Compute Mesh — Python 后端
   静态文件服务器 + SQLite 聊天历史 API
"""
import http.server
import json
import sqlite3
import os
import urllib.parse
import re
import mimetypes

WEB_DIR  = os.path.join(os.path.dirname(__file__), "web")
DB_PATH  = os.path.join(os.path.dirname(__file__), "history.db")
PORT     = 8080

# --------------------------------------------------
def init_db():
    db = sqlite3.connect(DB_PATH)
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
    """)
    # Migration: add model column if missing (for DBs created before this change)
    try:
        db.execute("ALTER TABLE messages ADD COLUMN model TEXT NOT NULL DEFAULT ''")
    except sqlite3.OperationalError:
        pass  # column already exists
    db.commit()
    return db

# --------------------------------------------------
class APIHandler:
    def __init__(self):
        self.db = init_db()

    def list_conversations(self):
        cur = self.db.execute(
            "SELECT id, title, model, created_at FROM conversations ORDER BY created_at DESC"
        )
        return [{"id": r[0], "title": r[1], "model": r[2], "created_at": r[3]} for r in cur]

    def get_conversation(self, conv_id):
        cur = self.db.execute("SELECT role, content, model FROM messages WHERE conversation_id=? ORDER BY id ASC", (conv_id,))
        msgs = [{"role": r[0], "content": r[1], "model": r[2]} for r in cur]
        meta = self.db.execute("SELECT title, model FROM conversations WHERE id=?", (conv_id,)).fetchone()
        return {"id": int(conv_id), "title": meta[0], "model": meta[1], "messages": msgs} if meta else None

    def create_conversation(self, title, model):
        cur = self.db.execute("INSERT INTO conversations (title, model) VALUES (?, ?)", (title, model))
        self.db.commit()
        return cur.lastrowid

    def save_messages(self, conv_id, msgs, title=None, model=None):
        for msg in msgs:
            self.db.execute(
                "INSERT INTO messages (conversation_id, role, content, model) VALUES (?, ?, ?, ?)",
                (conv_id, msg.get("role"), msg.get("content"), msg.get("model", ""))
            )
        if title:
            self.db.execute("UPDATE conversations SET title=? WHERE id=?", (title, conv_id))
        if model:
            self.db.execute("UPDATE conversations SET model=? WHERE id=?", (model, conv_id))
        self.db.commit()

    def delete_conversation(self, conv_id):
        self.db.execute("DELETE FROM conversations WHERE id=?", (conv_id,))
        self.db.commit()

# --------------------------------------------------
class RequestHandler(http.server.BaseHTTPRequestHandler):
    api = APIHandler()
    server_version = "AI-Remote/1.0"

    def log_message(self, format, *args):
        pass

    def _add_cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,DELETE,OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def _json(self, code, data):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self._add_cors()
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.end_headers()
        self.wfile.write(body)

    def _serve_file(self, path):
        file_path = path.lstrip("/") or "index.html"
        full_path = os.path.abspath(os.path.join(WEB_DIR, file_path))
        if not full_path.startswith(os.path.abspath(WEB_DIR)):
            self.send_response(403)
            self._add_cors()
            self.end_headers()
            return
        if not os.path.isfile(full_path):
            self.send_response(404)
            self._add_cors()
            self.end_headers()
            return
        ct, _ = mimetypes.guess_type(full_path)
        self.send_response(200)
        self._add_cors()
        self.send_header("Content-Type", ct or "application/octet-stream")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        with open(full_path, "rb") as f:
            self.wfile.write(f.read())

    def do_OPTIONS(self):
        self.send_response(204)
        self._add_cors()
        self.end_headers()

    def do_GET(self):
        path = urllib.parse.urlparse(self.path).path

        # API
        m = re.match(r'^/api/conversations/(\d+)$', path)
        if m:
            conv = self.api.get_conversation(int(m.group(1)))
            return self._json(200, conv) if conv else self._json(404, {"error": "not found"})
        elif path == "/api/conversations":
            convs = self.api.list_conversations()
            return self._json(200, convs)

        # Static
        self._serve_file(path)

    def do_POST(self):
        path   = urllib.parse.urlparse(self.path).path
        length = int(self.headers.get("Content-Length", 0))
        body   = json.loads(self.rfile.read(length)) if length > 0 else {}

        # API
        m = re.match(r'^/api/conversations/(\d+)$', path)
        if m:
            self.api.save_messages(
                int(m.group(1)),
                body.get("messages", []),
                body.get("title"),
                body.get("model"),
            )
            return self._json(200, {"ok": True})
        elif path == "/api/conversations":
            cid = self.api.create_conversation(
                body.get("title", "新对话"),
                body.get("model", ""),
            )
            return self._json(201, {"id": cid})

        self._json(404, {"error": "not found"})

    def do_DELETE(self):
        path = urllib.parse.urlparse(self.path).path
        m = re.match(r'^/api/conversations/(\d+)$', path)
        if m:
            self.api.delete_conversation(int(m.group(1)))
            return self._json(200, {"ok": True})
        self._json(404, {"error": "not found"})

# --------------------------------------------------
if __name__ == "__main__":
    server = http.server.HTTPServer(("0.0.0.0", PORT), RequestHandler)
    print(f"AI Remote Mesh — 服务器已启动")
    print(f"  本机: http://localhost:{PORT}")
    print(f"  数据库: {DB_PATH}")
    print(f"  Ctrl+C 停止")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n服务器已停止")
        server.server_close()
