# AI Remote Compute Mesh

**Use your PC's local LLMs from iPhone — works anywhere, always encrypted.**

**在 iPhone 上使用 PC 的本地大模型 — 任何网络下都能用，全部加密。**

```
┌─────────────┐    Tailscale WireGuard (v1.96.3)      ┌──────────────────┐
│  iPhone      │ ──────── 任何网络 / any network ────→  │  Windows PC      │
│  Safari      │     ┌───────────────────────┐        │                  │
│              │     │ Same WiFi → P2P       │        │  python server.py│
│  无需安装    │     │ Cellular  → DERP relay│        │  ├─ Ollama 0.23  │
│  无需配置    │     │ Auto switch, seamless │        │  └─ Web UI       │
└─────────────┘     └───────────────────────┘        └──────────────────┘
```

---

## Versions / 版本要求

| Component | Version | Required |
|-----------|---------|----------|
| Python | 3.12+ | Required / 必需 |
| Ollama | 0.23.0 | Required / 必需 |
| Tailscale | 1.96.3 | Required / 必需 (VPN mesh) |
| OS | Windows 11 | Server side / 服务端 |

Ollama environment variables / 环境变量 (permanent / 已永久设置):
```
OLLAMA_HOST=0.0.0.0
OLLAMA_ORIGINS=*
```

---

## Quick Start / 快速启动

### 1. Prerequisites / 前提

- [Python 3.12+](https://www.python.org/downloads/) installed
- [Ollama 0.23.0](https://ollama.com/download) installed & running
- [Tailscale 1.96.3](https://tailscale.com/download) installed & logged in
- Ollama env vars set permanently (see above)

### 2. Launch / 启动

```powershell
# Option A: Double-click / 双击
app\start.bat

# Option B: Command line / 命令行
cd app
python server.py
```

Output / 输出:
```
AI Remote Mesh — Server started / 服务器已启动
  Local:   http://localhost:8080
  Database: app\history.db
  Log:      app\server.log
  Ctrl+C to stop / 停止
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
| Multi-user auth | Register, login, PBKDF2-SHA256 password hashing, 64-char token, 7-day session |
| Admin approval | New users pending until admin approves via admin panel |
| Chat history | SQLite (WAL mode), create/read/delete conversations, per-user isolation |
| Model tags | Each AI response shows which model generated it |
| Markdown rendering | Tables, code blocks, LaTeX (`$$` `$`), headers, bold/italic |
| Auto model scan | Detects Ollama models on page load + 60s background polling |
| Admin panel | Approve/delete users, view system logs (localhost only) |
| Logging | Rotating file logs (5MB × 3), records auth events & API access |
| Mobile responsive | Fixed topbar + bottombar, scrollable chat, sidebar overlay |
| Self-contained | Zero external Python dependencies, zero external JS libraries |

---

## API Routes / API 路由

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/api/auth/register` | No | Register new user (pending) |
| POST | `/api/auth/login` | No | Login, returns token + user |
| POST | `/api/auth/logout` | Yes | Invalidate session |
| GET | `/api/auth/me` | Yes | Current user info |
| GET | `/api/admin/users` | Admin | List all users |
| POST | `/api/admin/users/<id>/approve` | Admin | Approve pending user |
| DELETE | `/api/admin/users/<id>` | Admin | Delete user |
| GET | `/api/admin/logs` | Admin | Server logs (last 200 lines) |
| GET | `/api/conversations` | Yes | List user's conversations |
| POST | `/api/conversations` | Yes | Create new conversation |
| GET | `/api/conversations/<id>` | Yes | Get conversation with messages |
| POST | `/api/conversations/<id>` | Yes | Save messages to conversation |
| DELETE | `/api/conversations/<id>` | Yes | Delete conversation |

---

## Project Structure / 目录结构

```
app/
├── server.py               ← Backend / 后端 (auth + API + static files)
├── config.py               ← Configuration / 配置常量
├── db.py                   ← Database init + all SQL / 数据库操作
├── auth.py                 ← Password hashing + token / 认证模块
├── logger.py               ← Logging system / 日志系统
├── history.db              ← SQLite database (auto-created)
├── server.log              ← Rotating log file (auto-created)
├── start.bat               ← Double-click to launch / 双击启动
├── web/
│   ├── login.html          ← Login & register page
│   ├── chat.html           ← Chat interface (auth required)
│   ├── admin.html          ← Admin panel (localhost only)
│   └── index.html          ← Auto-redirect to login
└── tools/
    ├── download.bat         ← Download Ollama + Tailscale installers
    ├── ollama/              ← Place ollama.exe here
    └── tailscale/           ← Place Tailscale installer here
```

---

## Security / 安全

- **Auth**: PBKDF2-SHA256 (60,000 iterations) + 64-char random token + 7-day expiry
- **Transport**: All cross-device traffic encrypted via Tailscale WireGuard, no public ports exposed
- **Admin isolation**: Admin panel restricted to `127.0.0.1` (+ optional server MAC whitelist), remote access returns 403
- **User isolation**: Each user sees only their own conversations
- **Log privacy**: Logs record operations (login/register/approve) only — no chat message content is logged
- **Zero dependencies**: Python stdlib only, no pip installs needed
