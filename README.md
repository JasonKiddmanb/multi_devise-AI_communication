# AI Remote Compute Mesh

**在 iPhone 上使用 PC 的本地大模型，任何网络下都能用，全部加密。**

```
┌─────────────┐    Tailscale WireGuard 加密隧道     ┌──────────────────┐
│  iPhone      │ ──────── 任何网络下可用 ────────→    │  Windows PC      │
│  Safari      │     ┌───────────────────────┐      │                  │
│              │     │ 同一 WiFi → P2P 直连   │      │  python server.py│
│  无需安装    │     │ 蜂窝数据 → DERP 中继   │      │  ├─ Ollama 模型  │
│  无需配置    │     │ 自动切换，完全无感      │      │  └─ 网页界面     │
└─────────────┘     └───────────────────────┘      └──────────────────┘
```

---

## 功能

- **多设备支持** — 用户注册/登录，每个用户独立会话，互不干扰
- **管理员审批** — 新注册用户需管理员在 PC 后台审批后才能使用
- **聊天气泡** — 自适应移动端，顶部栏/底部栏固定，中间滚动
- **历史对话** — SQLite 存储全部对话，侧边栏切换/删除/新建
- **模型标签** — 每条 AI 回复标注使用的模型名称
- **Markdown 渲染** — 表格、代码块、LaTeX 公式、标题、粗斜体等格式化输出
- **模型自动扫描** — 进入页面自动检测 Ollama 可用模型，60s 后台轮询
- **管理员面板** — 仅限本机 localhost 访问，用户审批管理 + 系统日志查看
- **完整日志** — 滚动日志文件（5MB × 3），记录登录/注册/审批/API 操作

---

## 一键启动

### 前提条件

- Windows PC，已安装 [Python 3.12+](https://www.python.org/downloads/)
- [Ollama](https://ollama.com/download) 已安装并运行
- [Tailscale](https://tailscale.com/download) 已安装并登录
- Ollama 环境变量（已永久设置）：
  ```
  OLLAMA_HOST=0.0.0.0
  OLLAMA_ORIGINS=*
  ```

### 启动

```powershell
cd app
python server.py
```

输出：
```
AI Remote Mesh — 服务器已启动
  本机: http://localhost:8080
  数据库: E:\...\app\history.db
  日志: E:\...\app\server.log
  Ctrl+C 停止
```

浏览器打开 `http://localhost:8080`，首次启动自动创建管理员账号。

### 在 iPhone 上

1. App Store 安装 **Tailscale**，登录同账号
2. 打开 Safari → `http://<PC的TailscaleIP>:8080`
3. 注册账号 → 等待管理员审批（管理员在 PC 上打开 `http://localhost:8080/admin.html`）
4. 审批通过后即可开始聊天

---

## 默认管理员账号

首次启动自动创建：

| 用户名 | 密码 |
|--------|------|
| `admin` | `admin123` |

**请登录后立即修改密码！** 控制面板地址：`http://localhost:8080/admin.html`（仅限本机访问）

---

## 目录结构

```
app/
├── server.py               ← Python 后端（认证 + API + 静态文件）
├── config.py               ← 配置常量
├── db.py                   ← 数据库初始化 + SQL 操作
├── auth.py                 ← 密码哈希 + Token 管理
├── logger.py               ← 日志系统
├── history.db              ← SQLite 数据库（自动创建）
├── server.log              ← 滚动日志文件（自动创建）
├── web/
│   ├── login.html          ← 登录/注册页面
│   ├── chat.html           ← 聊天界面（需登录）
│   ├── admin.html          ← 管理员审批面板（仅限 localhost）
│   └── index.html          ← 自动跳转到 login.html
├── start.bat               ← 启动入口
├── start.ps1               ← 启动器（备用）
└── tools/
    ├── download.bat         ← 下载 Ollama + Tailscale
    ├── ollama/              ← ollama.exe（自行下载放入）
    └── tailscale/           ← Tailscale 安装包（自行下载放入）
```

---

## API 路由

| 方法 | 路径 | 认证 | 说明 |
|------|------|------|------|
| POST | `/api/auth/register` | 否 | 用户注册（待审批） |
| POST | `/api/auth/login` | 否 | 登录，返回 Token |
| POST | `/api/auth/logout` | 是 | 退出登录 |
| GET | `/api/auth/me` | 是 | 当前用户信息 |
| GET | `/api/admin/users` | 管理员 | 用户列表 |
| POST | `/api/admin/users/<id>/approve` | 管理员 | 审批用户 |
| DELETE | `/api/admin/users/<id>` | 管理员 | 删除用户 |
| GET | `/api/admin/logs` | 管理员 | 系统日志（最近 200 行） |
| GET | `/api/conversations` | 是 | 当前用户的对话列表 |
| POST | `/api/conversations` | 是 | 创建新对话 |
| GET | `/api/conversations/<id>` | 是 | 获取对话详情（含消息） |
| POST | `/api/conversations/<id>` | 是 | 保存消息到对话 |
| DELETE | `/api/conversations/<id>` | 是 | 删除对话 |

---

## 安全

- **认证**：PBKDF2-SHA256 密码哈希 + 64 位随机 Token + 7 天过期
- **加密传输**：所有跨设备流量经 Tailscale WireGuard 加密，不暴露公网端口
- **管理员隔离**：管理面板仅限 `127.0.0.1` 访问，远程返回 403
- **用户隔离**：每个用户只能查看自己的对话
- **日志隐私**：日志仅记录操作（登录/注册/审批），不含聊天消息内容
