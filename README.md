# AI Remote Compute Mesh

**在 iPhone 上使用 PC 的本地大模型，任何网络下都能用，全部加密。**

```
┌─────────────┐    Tailscale WireGuard 加密隧道     ┌──────────────────┐
│  iPhone      │ ──────── 任何网络下可用 ────────→    │  Windows PC      │
│  Safari      │     ┌───────────────────────┐      │                  │
│              │     │ 同一 WiFi → P2P 直连   │      │  app/start.bat   │
│  无需安装    │     │ 蜂窝数据 → DERP 中继   │      │  ├─ Ollama 模型  │
│  无需配置    │     │ 自动切换，完全无感      │      │  └─ 网页界面     │
└─────────────┘     └───────────────────────┘      └──────────────────┘
```

---

## 🚀 一键启动（推荐）

把以下文件夹分发给用户，运行 `start.bat` 即可：

```
app/
├── start.bat              ← 双击启动！
├── start.ps1              ← 自动处理一切（启动 Ollama + 网页服务器）
├── web/
│   └── index.html         ← 聊天界面（内置，无需联网）
└── tools/
    ├── ollama/            ← 放 ollama.exe
    └── tailscale/         ← 放 Tailscale MSI 安装包
```

### 首次使用

```powershell
# 1. 下载 Ollama + Tailscale 到 tools/ 目录
app\tools\download.bat

# 2. 双击 start.bat（右键 → 以管理员身份运行）
app\start.bat
```

程序会自动：
1. ✅ 安装 Tailscale（如系统未安装）
2. ✅ 启动 Ollama（内置或系统）
3. ✅ 启动网页聊天界面（端口 8080，**不需要 Docker**）
4. ✅ 显示 Tailscale IP → 在 iPhone Safari 打开即可

### 在 iPhone 上

1. App Store 安装 **Tailscale**，登录同账号
2. 打开 Safari → `http://<PC的TailscaleIP>:8080`
3. 选择模型，开始聊天

---

## 🔧 目录结构

```
├── app/                    ← 自包含分发包
│   ├── start.bat           ← 启动入口
│   ├── start.ps1           ← 启动器（Ollama + 网页服务器）
│   ├── web/index.html      ← 聊天界面
│   └── tools/
│       ├── download.bat    ← 下载 Ollama + Tailscale
│       ├── ollama/         ← ollama.exe (自行下载放入)
│       └── tailscale/      ← Tailscale MSI (自行下载放入)
├── docs/
│   ├── quickstart.md       # 详细使用教程
│   └── app-guide.md        # App 分发包说明
├── scripts/                # 辅助脚本
├── docker-compose.yml      # Open WebUI（Docker 方式，可选）
└── v2/                     # V2 规划
```

---

## 两种方式对比

| 方式 | 需要 | 适合 |
|------|------|------|
| **app/（推荐）** | 下载文件夹 → 双击 start.bat | 快速分发给用户 |
| **Docker 方式** | 安装 Docker + Open WebUI | 需要完整 WebUI 功能 |

---

## 安全

- 所有跨设备流量经 WireGuard 加密，不暴露公网端口
- Ollama 绑定 `0.0.0.0`，但仅 Tailscale 网络可达
- 可使用 Tailscale ACL 限制设备间访问
