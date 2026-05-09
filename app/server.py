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

from config import PORT, WEB_DIR, LOG_PATH, ADMIN_MAC_WHITELIST, UPLOAD_DIR, MAX_UPLOAD_SIZE, ALLOWED_EXTENSIONS
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

    def _read_multipart_file(self) -> dict | None:
        """解析 multipart/form-data，返回 {filename, content_type, body(bytes)}"""
        ct = self.headers.get("Content-Type", "")
        m = re.search(r'boundary=(.+)', ct)
        if not m:
            return None
        boundary = m.group(1).strip().strip('"').encode()
        length = int(self.headers.get("Content-Length", 0))
        if length == 0 or length > MAX_UPLOAD_SIZE:
            return None

        raw = self.rfile.read(length)
        # 拆分 boundary 块
        parts = raw.split(b'--' + boundary)
        for part in parts:
            if b'Content-Disposition' not in part:
                continue
            header_end = part.find(b'\r\n\r\n')
            if header_end == -1:
                continue
            header_text = part[:header_end].decode("utf-8", errors="replace")
            body = part[header_end + 4:]
            # 去掉尾部的 \r\n--
            if body.endswith(b'\r\n'):
                body = body[:-2]
            elif body.endswith(b'--\r\n'):
                body = body[:-4]

            # 从 Content-Disposition 提取 filename
            disp_m = re.search(r'filename="(.*?)"', header_text, re.IGNORECASE)
            if not disp_m:
                continue
            filename = os.path.basename(disp_m.group(1))
            if not filename:
                continue

            content_type = ""
            type_m = re.search(r'Content-Type:\s*(\S+)', header_text, re.IGNORECASE)
            if type_m:
                content_type = type_m.group(1)

            return {
                "filename": filename,
                "content_type": content_type,
                "body": body,
            }
        return None

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
        # 去除 ?v= 缓存破坏参数
        if "?" in path:
            path = path.split("?")[0]
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
        # HTML 文件禁止缓存（保证前端始终最新）
        cache_value = "no-store" if ct and "html" in ct else "no-cache"
        self.send_header("Cache-Control", cache_value)
        self.end_headers()
        with open(full_path, "rb") as f:
            self.wfile.write(f.read())

    def _serve_upload(self, path):
        """提供上传的文件（需要认证）"""
        log.debug("_serve_upload called: path=%s", path)
        user = self._require_auth()
        if not user:
            return
        # 安全提取文件名
        raw = path.replace("/uploads/", "", 1)
        if ".." in raw or "/" in raw or "\\" in raw:
            return self._json(400, {"error": "invalid filename"})
        file_path = os.path.normpath(os.path.join(UPLOAD_DIR, raw))
        if not file_path.startswith(os.path.abspath(UPLOAD_DIR)):
            return self._json(400, {"error": "invalid filename"})
        if not os.path.isfile(file_path):
            return self._json(404, {"error": "file not found"})
        ct, _ = mimetypes.guess_type(file_path)
        self.send_response(200)
        self._add_cors()
        self.send_header("Content-Type", ct or "application/octet-stream")
        self.send_header("Content-Disposition", f'inline; filename="{raw}"')
        self.send_header("Cache-Control", "private, max-age=3600")
        self.end_headers()
        with open(file_path, "rb") as f:
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

        # --- favicon（静默返回空，避免 404 日志噪音） ---
        if path == "/favicon.ico":
            self.send_response(200)
            self.send_header("Content-Type", "image/x-icon")
            self.send_header("Cache-Control", "public, max-age=86400")
            self.end_headers()
            return

        # --- Uploaded files ---
        if path.startswith("/uploads/"):
            self._serve_upload(path)
            return

        # --- Static ---
        self._serve_file(path)

    def do_POST(self):
        path   = urllib.parse.urlparse(self.path).path

        # --- File upload（需要原始 body，必须在 _read_body 之前处理） ---
        if path == "/api/upload":
            try:
                user = self._require_auth()
                if not user:
                    return
                file_info = self._read_multipart_file()
                if not file_info:
                    return self._json(400, {"error": "no file provided or invalid upload"})
                filename = file_info["filename"]
                ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
                if ext not in ALLOWED_EXTENSIONS:
                    return self._json(400, {"error": f"file type .{ext} not allowed"})
                import uuid
                unique_name = f"{uuid.uuid4().hex[:12]}_{filename}"
                dest = os.path.join(UPLOAD_DIR, unique_name)
                with open(dest, "wb") as f:
                    f.write(file_info["body"])
                log.info("User '%s' uploaded: %s (%d bytes)",
                         user["username"], filename, len(file_info["body"]))
                return self._json(201, {
                    "ok": True,
                    "filename": filename,
                    "url": f"/uploads/{unique_name}",
                    "size": len(file_info["body"]),
                    "mime": file_info["content_type"],
                })
            except Exception as e:
                log.error("Upload failed: %s", e, exc_info=True)
                return self._json(500, {"error": f"upload failed: {e}"})

        body   = self._read_body()

        # --- Ollama Chat Proxy（解决前端 CORS 问题） ---
        if path == "/api/chat":
            if not self._require_auth():
                return
            try:
                ollama_host = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")
                if not ollama_host.startswith("http"):
                    ollama_host = "http://" + ollama_host
                ollama_host = ollama_host.rstrip("/")
                # 0.0.0.0 是监听地址，不能作为连接目标，替换为 127.0.0.1
                ollama_host = ollama_host.replace("://0.0.0.0", "://127.0.0.1")
                # 如果 OLLAMA_HOST 未指定端口（如 "0.0.0.0"），补上默认 11434
                # 如果 OLLAMA_HOST 未指定端口，补上默认 11434
                parsed = urllib.parse.urlparse(ollama_host)
                if not parsed.port:
                    ollama_host += ":11434"
                import urllib.request as _ur
                target_url = f"{ollama_host}/api/chat"
                req = _ur.Request(
                    target_url,
                    data=json.dumps(body).encode(),
                    headers={"Content-Type": "application/json"},
                )
                resp = _ur.urlopen(req, timeout=120)
                # 流式转发
                self.send_response(200)
                self._add_cors()
                self.send_header("Content-Type", "application/x-ndjson")
                self.end_headers()
                while True:
                    chunk = resp.read(4096)
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    self.wfile.flush()
                return
            except Exception as e:
                log.error("Chat proxy failed: %s", e, exc_info=True)
                return self._json(502, {"error": f"Ollama proxy failed: {e}"})

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
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    # 将 db 注入到 RequestHandler 类（每个请求共享同一连接）
    RequestHandler.db = db

    # ==================== Ollama 看门狗（后台守护线程） ====================
    def _ollama_watchdog():
        was_offline = False
        while True:
            if is_ollama_running():
                if was_offline:
                    log.info("Ollama is running again")
                else:
                    log.info("Ollama is running")
                was_offline = False
            else:
                if not was_offline:
                    log.warning("Ollama not running, auto-starting...")
                else:
                    log.warning("Ollama still offline, retrying...")
                start_ollama()
                was_offline = True
            time.sleep(30)

    t = threading.Thread(target=_ollama_watchdog, daemon=True)
    t.start()

    # ==================== Tailscale 守护（只启动一次，避免反复 tailscale up 打断连接） ====================
    def _tailscale_watchdog():
        first = True
        while True:
            running = is_tailscale_running()
            if not running:
                if first:
                    log.warning("Tailscale not running, auto-starting...")
                    start_tailscale()
                    first = False
                else:
                    # 非首次离线 —— 只警告，不自动重启（避免 tailscale up 反复调用打断已有连接）
                    log.warning("Tailscale is offline (auto-restart disabled to avoid connection cycling)")
            else:
                if first:
                    log.info("Tailscale is running")
                first = False
            time.sleep(120)  # 每 2 分钟检查一次

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
