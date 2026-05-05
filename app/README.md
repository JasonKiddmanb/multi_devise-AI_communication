# AI Remote Compute Mesh — 自包含 App

这是你的 V1 分发包目录。用户下载此文件夹后，运行 `start.bat` 即可使用。

## 目录结构

```
app/
├── start.bat              ← 双击启动！入口在这里
├── start.ps1              ← 启动器脚本（自动处理一切）
├── web/
│   └── index.html         ← 聊天网页界面（内置，无需联网）
└── tools/
    ├── download.bat       ← 下载 Ollama + Tailscale 到本地
    ├── ollama/            ← 放 ollama.exe + DLL
    └── tailscale/         ← 放 Tailscale MSI 安装包
```
