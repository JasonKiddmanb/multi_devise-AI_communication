#!/usr/bin/env python3
"""AI Remote Compute Mesh — Python 后端
   认证 + 管理员审批 + MAC 限制 + 日志
"""
import http.server
import json
import os
import re
import threading
import time
import urllib.parse
import urllib.request
import mimetypes
import uuid
import subprocess
import platform

from config import PORT, WEB_DIR, LOG_PATH, ADMIN_MAC_WHITELIST
from logger import log
from db import init_db, create_user, get_user_by_username, get_user_by_id
from db import list_users, approve_user, delete_user
from db import create_session, validate_session, delete_session
from db import list_conversations, get_conversation, create_conversation, save_messages, delete_conversation
from auth import hash_password, verify_password, generate_token, make_expires_at
from discovery import discover, is_ollama_running, start_ollama, is_tailscale_running, start_tailscale

# ==================== 管理员 MAC 验证 ====================

def _get_local_macs():
    """返回本机所有 MAC 地址（小写十六进制，无分隔符）"""
    macs = set()
    node = uuid.getnode()
    if node not in (0, 0x00005E0053FF):
        macs.add(f"{node:012x}")
    if platform.system() == "Windows":
        try:
            r = subprocess.run(["getmac", "/v", "/fo", "csv"],
                               capture_output=True, text=True, timeout=5)
            for line in r.stdout.strip().split("\n")[1:]:
                parts = line.replace('"', '').split(",")
                if len(parts) >= 3:
                    addr = parts[2].strip().replace("-", "").lower()
                    if len(addr) == 12:
                        macs.add(addr)
        except Exception:
            pass
    return macs

def is_admin_allowed(client_ip: str) -> bool:
    if client_ip != "127.0.0.1":
        return False
    if ADMIN_MAC_WHITELIST:
        local_macs = _get_local_macs()
        if not (local_macs & set(ADMIN_MAC_WHITELIST)):
            log.warning("Admin MAC check failed: local=%s, whitelist=%s", local_macs, ADMIN_MAC_WHITELIST)
            return False
    return True

# ==================== 联网搜索 ====================

def web_search(query: str) -> dict:
    """使用 Bing 搜索（无 API Key，解析 HTML）"""
    encoded = urllib.parse.quote(query)
    url = f"https://www.bing.com/search?q={encoded}&count=8"
    ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": ua})
        with urllib.request.urlopen(req, timeout=15) as resp:
            html = resp.read().decode("utf-8", errors="replace")
        results = []
        # 解析 <li class="b_algo"> 块
        for block in re.findall(r'<li[^>]*class="b_algo"[^>]*>(.*?)</li>', html, re.DOTALL)[:10]:
            title_m = re.search(r'<h2[^>]*>.*?<a[^>]*href="(.*?)"[^>]*>(.*?)</a>', block, re.DOTALL)
            snippet_m = re.search(r'<p[^>]*>(.*?)</p>', block, re.DOTALL)
            if title_m:
                title = re.sub(r'<[^>]+>', '', title_m.group(2)).strip()
                link = title_m.group(1)
                snippet = ""
                if snippet_m:
                    snippet = re.sub(r'<[^>]+>', '', snippet_m.group(1)).strip()
                if title:
                    results.append({"title": title, "snippet": snippet, "link": link})
        return {"query": query, "results": results}
    except Exception as e:
        log.warning("Web search failed: %s", e)
        return {"query": query, "results": [], "error": str(e)}

# ==================== 请求处理 ====================

class RequestHandler(http.server.BaseHTTPRequestHandler):
    server_version = "AI-Remote/1.0"

    def log_message(self, format, *args):
        ua = self.headers.get("User-Agent", "-")
        b = ua.split(' ')[0][:40]
        log.info("[%s] %s — %s — %s", self.client_address[0], format % args, b,
                 self.headers.get("Referer", "-"))

    def _add_cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,DELETE,OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type,Authorization")

    def _json(self, code, data):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self._add_cors()
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.end_headers()
        self.wfile.write(body)

    def _read_body(self) -> dict:
        length = int(self.headers.get("Content-Length", 0))
        if length == 0:
            return {}
        return json.loads(self.rfile.read(length))

    # ==================== Auth Helpers ====================

    def _get_user(self) -> dict | None:
        auth = self.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            return None
        return validate_session(self.db, auth[7:])

    def _require_auth(self) -> dict | None:
        user = self._get_user()
        if not user:
            self._json(401, {"error": "unauthorized"})
            return None
        if not user["approved"]:
            self._json(403, {"error": "account pending approval"})
            return None
        return user

    def _require_admin(self) -> dict | None:
        user = self._require_auth()
        if not user:
            return None
        if user["role"] != "admin":
            self._json(403, {"error": "admin required"})
            return None
        if not is_admin_allowed(self.client_address[0]):
            self._json(403, {"error": "admin panel only accessible from localhost"})
            return None
        return user

    # ==================== 静态文件 ====================

    def _serve_file(self, path):
        file_path = path.lstrip("/") or "index.html"
        full_path = os.path.abspath(os.path.join(WEB_DIR, file_path))
        if not full_path.startswith(os.path.abspath(WEB_DIR)):
            self.send_response(403)
            self._add_cors()
            self.end_headers()
            return

        # admin.html 仅限 localhost（+ MAC白名单）
        if "admin" in os.path.basename(full_path).lower():
            if not is_admin_allowed(self.client_address[0]):
                self.send_response(403)
                self._add_cors()
                self.end_headers()
                self.wfile.write(b"Forbidden - localhost only")
                return

        if not os.path.isfile(full_path):
            # SPA fallback: /chat.html or /login.html
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

    # ==================== HTTP 方法 ====================

    def do_OPTIONS(self):
        self.send_response(204)
        self._add_cors()
        self.end_headers()

    def do_GET(self):
        path = urllib.parse.urlparse(self.path).path

        # --- Auth API ---
        if path == "/api/auth/me":
            user = self._require_auth()
            if not user:
                return
            return self._json(200, {"id": user["id"], "username": user["username"], "role": user["role"]})

        # --- Admin API ---
        if path == "/api/admin/users":
            user = self._require_admin()
            if not user:
                return
            users = list_users(self.db)
            return self._json(200, users)

        if path == "/api/admin/logs":
            user = self._require_admin()
            if not user:
                return
            try:
                with open(LOG_PATH, "r", encoding="utf-8") as f:
                    all_lines = [l.rstrip("\n") for l in f.readlines()]
                # 返回倒序（最新在前），最多 200 条
                return self._json(200, {"lines": all_lines[-200:][::-1]})
            except FileNotFoundError:
                return self._json(200, {"lines": []})

        # --- Discovery ---
        if path == "/api/discovery":
            user = self._require_auth()
            if not user:
                return
            data = discover()
            return self._json(200, data)

        # --- Conversations ---
        m = re.match(r'^/api/conversations/(\d+)$', path)
        if m:
            user = self._require_auth()
            if not user:
                return
            conv = get_conversation(self.db, int(m.group(1)))
            if not conv:
                return self._json(404, {"error": "not found"})
            conv_owner = conv.get("user_id")
            if conv_owner != user["id"] and user["role"] != "admin":
                return self._json(404, {"error": "not found"})
            return self._json(200, conv)

        if path == "/api/conversations":
            user = self._require_auth()
            if not user:
                return
            convs = list_conversations(self.db, user["id"])
            return self._json(200, convs)

        # --- Static ---
        self._serve_file(path)

    def do_POST(self):
        path   = urllib.parse.urlparse(self.path).path
        body   = self._read_body()

        # --- Auth API ---
        if path == "/api/auth/register":
            username = (body.get("username") or "").strip()
            password = (body.get("password") or "").strip()
            if not username or not password:
                return self._json(400, {"error": "username and password required"})
            if len(username) < 2 or len(password) < 4:
                return self._json(400, {"error": "username >=2 chars, password >=4 chars"})
            pwhash = hash_password(password)
            uid = create_user(self.db, username, pwhash)
            if uid is None:
                return self._json(409, {"error": "username already exists"})
            log.info("New user '%s' registered from %s", username, self.client_address[0])
            return self._json(201, {"ok": True, "message": "registration submitted, pending approval"})

        if path == "/api/auth/login":
            username = (body.get("username") or "").strip()
            password = (body.get("password") or "").strip()
            if not username or not password:
                return self._json(400, {"error": "username and password required"})
            user = get_user_by_username(self.db, username)
            if not user or not verify_password(password, user["password"]):
                log.warning("Failed login for '%s' from %s", username, self.client_address[0])
                return self._json(401, {"error": "invalid username or password"})
            if not user["approved"]:
                return self._json(403, {"error": "account pending approval"})
            token = generate_token()
            create_session(self.db, user["id"], token, make_expires_at())
            log.info("User '%s' logged in from %s", username, self.client_address[0])
            return self._json(200, {
                "token": token,
                "user": {"id": user["id"], "username": user["username"], "role": user["role"]}
            })

        if path == "/api/auth/logout":
            auth = self.headers.get("Authorization", "")
            if auth.startswith("Bearer "):
                delete_session(self.db, auth[7:])
            return self._json(200, {"ok": True})

        # --- Search ---
        if path == "/api/search":
            user = self._require_auth()
            if not user:
                return
            query = (body.get("query") or "").strip()
            if not query:
                return self._json(400, {"error": "query required"})
            results = web_search(query)
            return self._json(200, results)

        # --- Admin API ---
        m = re.match(r'^/api/admin/users/(\d+)/approve$', path)
        if m:
            user = self._require_admin()
            if not user:
                return
            ok = approve_user(self.db, int(m.group(1)))
            if ok:
                log.info("Admin '%s' approved user id=%s", user["username"], m.group(1))
                return self._json(200, {"ok": True})
            return self._json(404, {"error": "user not found or already approved"})

        # --- Conversations ---
        m = re.match(r'^/api/conversations/(\d+)$', path)
        if m:
            user = self._require_auth()
            if not user:
                return
            conv_id = int(m.group(1))
            conv = get_conversation(self.db, conv_id)
            if not conv:
                return self._json(404, {"error": "not found"})
            conv_owner = conv.get("user_id")
            if conv_owner != user["id"] and user["role"] != "admin":
                return self._json(404, {"error": "not found"})
            save_messages(
                self.db, conv_id,
                body.get("messages", []),
                body.get("title"),
                body.get("model"),
            )
            return self._json(200, {"ok": True})

        if path == "/api/conversations":
            user = self._require_auth()
            if not user:
                return
            cid = create_conversation(
                self.db,
                body.get("title", "新对话"),
                body.get("model", ""),
                user["id"],
            )
            log.info("User '%s' created conversation %d", user["username"], cid)
            return self._json(201, {"id": cid})

        self._json(404, {"error": "not found"})

    def do_DELETE(self):
        path = urllib.parse.urlparse(self.path).path

        # --- Admin API ---
        m = re.match(r'^/api/admin/users/(\d+)$', path)
        if m:
            user = self._require_admin()
            if not user:
                return
            target_id = int(m.group(1))
            if target_id == user["id"]:
                return self._json(400, {"error": "cannot delete yourself"})
            ok = delete_user(self.db, target_id)
            if ok:
                log.warning("Admin '%s' deleted user id=%d", user["username"], target_id)
                return self._json(200, {"ok": True})
            return self._json(404, {"error": "user not found"})

        # --- Conversations ---
        m = re.match(r'^/api/conversations/(\d+)$', path)
        if m:
            user = self._require_auth()
            if not user:
                return
            conv = get_conversation(self.db, int(m.group(1)))
            if not conv:
                return self._json(404, {"error": "not found"})
            conv_owner = conv.get("user_id")
            if conv_owner != user["id"] and user["role"] != "admin":
                return self._json(404, {"error": "not found"})
            delete_conversation(self.db, int(m.group(1)))
            log.info("User '%s' deleted conversation %s", user["username"], m.group(1))
            return self._json(200, {"ok": True})

        self._json(404, {"error": "not found"})


# ==================== 启动 ====================

def main():
    db = init_db()
    # 将 db 注入到 RequestHandler 类（每个请求共享同一连接）
    RequestHandler.db = db

    # ==================== Ollama 看门狗（后台守护线程） ====================
    def _ollama_watchdog():
        first = True
        while True:
            if not is_ollama_running():
                if first:
                    log.warning("Ollama not running, auto-starting...")
                else:
                    log.warning("Ollama 已离线，正在重新启动...")
                start_ollama()
                first = False
            time.sleep(30)

    t = threading.Thread(target=_ollama_watchdog, daemon=True)
    t.start()

    # ==================== Tailscale 看门狗（后台守护线程） ====================
    def _tailscale_watchdog():
        first = True
        while True:
            if not is_tailscale_running():
                if first:
                    log.warning("Tailscale not running, auto-starting...")
                else:
                    log.warning("Tailscale 已离线，正在重新启动...")
                # 等待数秒再次确认，避免误判（如用户正在手动启动中）
                time.sleep(5)
                if not is_tailscale_running():
                    start_tailscale()
                else:
                    log.info("Tailscale is now running (manual start detected)")
                first = False
            time.sleep(60)

    t2 = threading.Thread(target=_tailscale_watchdog, daemon=True)
    t2.start()

    server = http.server.HTTPServer(("0.0.0.0", PORT), RequestHandler)
    log.info("============================================")
    log.info("AI Remote Mesh — 服务器已启动")
    log.info("  本机: http://localhost:%d", PORT)
    log.info("  数据库: %s", os.path.abspath(os.path.join(os.path.dirname(__file__), "history.db")))
    log.info("  日志: %s", os.path.join(os.path.dirname(__file__), "server.log"))
    log.info("  Ctrl+C 停止")
    log.info("============================================")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        log.info("服务器已停止")
        server.server_close()

if __name__ == "__main__":
    main()
