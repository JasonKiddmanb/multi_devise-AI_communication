# AI Remote Compute Mesh

**Use your PC's local LLMs from iPhone — works anywhere, always encrypted.**

**在 iPhone 上使用 PC 的本地大模型 — 任何网络下都能用，全部加密。**

```
┌─────────────┐    Tailscale WireGuard VPN         ┌──────────────────────────┐
│  iPhone      │ ──────── 任何网络 / any network ──→  │  Windows PC              │
│  Safari      │     ┌───────────────────────┐      │                          │
│              │     │ Same WiFi → P2P       │      │  Python HTTP Server      │
│  无需安装    │     │ Cellular  → DERP relay│      │  ├─ Auth + Admin Panel   │
│  无需配置    │     │ Auto switch, seamless │      │  ├─ Chat Proxy / Ollama  │
│              │     └───────────────────────┘      │  ├─ File Upload & Search │
│  或 Docker   │                                    │  ├─ Device Discovery     │
│  Open WebUI  │                                    │  ├─ Ollama Watchdog      │
└─────────────┘                                    │  └─ Tailscale Watchdog   │
                                                    └──────────────────────────┘
```

---

## 概述 / Overview

| 方案 | 描述 | 启动方式 |
|------|------|----------|
| **Python 后端（推荐）** | 零依赖、自包含的网页服务器 | `app\start.ps1` 或 `python server.py` |
| **Docker + Open WebUI** | 容器化部署，功能完整 | `docker compose up -d` |

两条路径共用同一 Tailscale 加密隧道，可同时运行。

---

## Quick Start / 快速启动

### 1. Prerequisites / 前提

- [Python 3.12+](https://www.python.org/downloads/) installed
- [Ollama](https://ollama.com/download) installed & running
- [Tailscale](https://tailscale.com/download) installed & logged in
- Ollama env vars 已永久设置:
  - `OLLAMA_HOST=0.0.0.0`
  - `OLLAMA_ORIGINS=*`

### 2. Launch / 启动 Python 后端

```powershell
# Option A: 一键启动（自动检查 Tailscale + Ollama）
app\start.ps1

# Option B: 仅启动网页服务器（Ollama / Tailscale 已运行时）
app\start-server-only.ps1

# Option C: 命令行
cd app
python server.py
```

输出:
```
AI Remote Mesh — 服务器已启动
  本机: http://localhost:8080
  数据库: app\history.db
  日志: app\server.log
  Ctrl+C 停止
```

### 3. Open browser / 打开浏览器

Navigate to `http://localhost:8080` → auto-redirects to login page.

First launch creates default admin account (see below).

### 4. On iPhone

1. Install **Tailscale** from App Store, login with same account
2. Safari → `http://<PC-Tailscale-IP>:8080`
3. Register an account → wait for admin approval
4. Start chatting with your PC's local models

> **How to find PC's Tailscale IP / 如何查看 Tailscale IP:**
> ```powershell
> tailscale ip -4
> ```
> Example: `100.89.124.123` → Safari: `http://100.89.124.123:8080`

---

## Default Admin / 默认管理员

| Username | Password |
|----------|----------|
| `admin` | `admin123` |

**Change password after first login! / 请登录后立即修改密码！**

Admin panel / 管理面板: `http://localhost:8080/admin.html` (localhost only / 仅限本机)

---

## Features / 功能

| Feature | Description |
|---------|-------------|
| Multi-user auth | Register, login, PBKDF2-SHA256 (60k iterations), 64-char token, 7-day session |
| Admin approval | New users pending until admin approves via admin panel |
| Chat history | SQLite (WAL mode), create/read/delete conversations, per-user isolation |
| Model tags | Each AI response shows which model generated it |
| Markdown rendering | Tables, code blocks, LaTeX (`$$` `$`), headers, bold/italic |
| Device discovery | Scans Tailscale peers + local network for Ollama instances, groups models by device (OS icon + hostname), 60s auto-refresh |
| **Ollama watchdog** | **Server auto-starts Ollama if not running, 30s health check** |
| **Tailscale watchdog** | **Auto-starts Tailscale on first failure, 120s health check** |
| **File upload** | **Drag-free upload via bottom sheet, image preview, 50 MB limit, extensive format support** |
| **Web search** | **Toggleable Bing search integration, results injected as context** |
| **Think section** | **Collapsible `<think>` tag rendering for reasoning models** |
| **Theme toggle** | **Light/Dark mode switch, persisted to localStorage** |
| Admin panel | Approve/delete users, view system logs (latest 200 lines, reverse order) |
| Admin MAC whitelist | Optional hardware MAC restriction for admin panel access |
| Logging | Rotating file logs (5MB × 3), records auth events & API access |
| Log privacy | Logs record operations only — no chat message content is logged |
| Mobile responsive | Fixed topbar + bottombar, sidebar overlay, iOS action sheet, safe-area-inset |
| Self-contained | Zero external Python dependencies, zero external JS libraries |

---

## API Routes / API 路由

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/api/auth/register` | No | Register new user (pending) |
| POST | `/api/auth/login` | No | Login, returns token + user |
| POST | `/api/auth/logout` | Yes | Invalidate session |
| GET | `/api/auth/me` | Yes | Current user info |
| POST | `/api/chat` | Yes | Ollama chat proxy (streaming, resolves CORS) |
| GET | `/api/discovery` | Yes | Scan Tailscale peers for Ollama models |
| POST | `/api/search` | Yes | Bing web search (no API key needed, HTML parsing) |
| POST | `/api/upload` | Yes | Upload file (multipart, 50 MB max) |
| GET | `/uploads/<file>` | Yes | Serve uploaded files (inline, 1h cache) |
| GET | `/api/admin/users` | Admin | List all users |
| POST | `/api/admin/users/<id>/approve` | Admin | Approve pending user |
| DELETE | `/api/admin/users/<id>` | Admin | Delete user |
| GET | `/api/admin/logs` | Admin | Server logs (last 200 lines, reversed) |
| GET | `/api/conversations` | Yes | List user's conversations |
| POST | `/api/conversations` | Yes | Create new conversation |
| GET | `/api/conversations/<id>` | Yes | Get conversation with messages |
| POST | `/api/conversations/<id>` | Yes | Save messages to conversation |
| DELETE | `/api/conversations/<id>` | Yes | Delete conversation |

---

## Project Structure / 目录结构

```
app/
├── server.py               ← Backend / 后端 (auth + API + proxy + static files)
├── config.py               ← Configuration / 配置常量
├── db.py                   ← Database init + all SQL / 数据库操作
├── auth.py                 ← Password hashing + token / 认证模块
├── logger.py               ← Logging system / 日志系统
├── discovery.py            ← Tailscale peer discovery + Ollama watchdog
├── history.db              ← SQLite database (auto-created)
├── server.log              ← Rotating log file (auto-created)
├── start.ps1               ← One-click launcher (Ollama + Tailscale + Web)
├── start-server-only.ps1   ← Web server only (lightweight)
├── uploads/                ← Uploaded files (auto-created)
├── web/
│   ├── login.html          ← Login & register page
│   ├── chat.html           ← Chat interface (auth required) v1.1
│   ├── admin.html          ← Admin panel (localhost only)
│   └── index.html          ← Auto-redirect to login
└── tools/
    ├── download.bat         ← Download Ollama + Tailscale installers
    ├── ollama/              ← Place ollama.exe here
    └── tailscale/           ← Place Tailscale installer here

scripts/
├── setup.ps1               ← Windows deployment script (Docker path)
├── setup.sh                ← Linux/macOS deployment script
├── get-tailscale-ip.ps1    ← Get PC's Tailscale IP
├── check-ts.ps1            ← Tailscale connection checker
├── start-server.ps1        ← Legacy launcher
└── test-api.ps1            ← Quick API health check

docs/
├── quickstart.md           ← Quick start guide
├── setup-checklist.md      ← Prerequisites checklist
└── app-guide.md            ← App usage guide

v2/                         ← Future architecture research
├── headscale/              ← Self-hosted Tailscale coordinator
├── rustdesk/               ← Remote desktop
├── localsend/              ← LAN file transfer
└── webrtc/                 ← P2P communication
```

---

## Configuration / 配置 (config.py)

| Variable | Default | Description |
|----------|---------|-------------|
| `PORT` | `8080` | HTTP server port |
| `SESSION_DAYS` | `7` | Session expiry days |
| `ADMIN_DEFAULT_PASSWORD` | `admin123` | Default admin password (via env `ADMIN_DEFAULT_PASSWORD`) |
| `ADMIN_MAC_WHITELIST` | `""` | Comma-separated MACs for admin panel (via env `ADMIN_MAC_WHITELIST`). Leave empty to skip MAC check. |
| `UPLOAD_DIR` | `app/uploads/` | Uploaded file storage |
| `MAX_UPLOAD_SIZE` | `50 MB` | Maximum file upload size |
| `ALLOWED_EXTENSIONS` | *(see config.py)* | Images, documents, archives, code, media |

---

## Alternative: Docker + Open WebUI

```powershell
# 使用 Docker 部署 Open WebUI（功能完整的聊天界面）
docker compose -f docker-compose.yml up -d
```

Docker 方案通过 `host.docker.internal:11434` 连接本机 Ollama，适合偏好完整 Web UI 的用户。

---

## Security / 安全

- **Auth**: PBKDF2-SHA256 (60,000 iterations) + 64-char random token + 7-day expiry
- **Transport**: All cross-device traffic encrypted via Tailscale WireGuard, no public ports exposed
- **Admin isolation**: Admin panel restricted to `127.0.0.1` (+ optional server MAC whitelist), remote access returns 403
- **User isolation**: Each user sees only their own conversations
- **Log privacy**: Logs record operations (login/register/approve) only — no chat message content is logged
- **Zero dependencies**: Python stdlib only, no pip installs needed
- **File upload**: Extension whitelist, size limit, renamed to UUID to prevent path traversal

---

## Roadmap

- **V1 (current)**: Python backend with auth, chat proxy, device discovery, file upload, web search — all over Tailscale
- **V2**: Multi-platform mesh with bidirectional calls, file sharing, remote desktop via RustDesk/LocalSend/WebRTC — all over Tailscale

---

# 赞助 / Sponsor

如果你觉得这个项目有用，欢迎请我喝杯咖啡。  
If you find this project useful, feel free to buy me a coffee.

![alipay](./alipay.jpg)
