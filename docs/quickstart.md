# V1 详细教程：iPhone 使用 PC 的本地大模型

## 前置知识

本教程假设你有一台 Windows PC 和一部 iPhone，目标是让 iPhone 在任何网络下都能使用 PC 上跑的大模型。

**核心原理：** Tailscale 创建一个加密的私人网络，把 PC 和 iPhone 放在同一个虚拟局域网里。Open WebUI 提供网页聊天界面。Ollama 负责跑模型。

---

## 第 1 步：安装 Tailscale 并连接

### PC 端
1. 打开 https://tailscale.com/download
2. 下载 Windows 版并安装
3. 点击系统托盘中的 Tailscale 图标 → **Sign in**
4. 用 Google / Microsoft / Apple 账号登录（记下你用的账号）
5. 确认状态显示 **Connected**

### iPhone 端
1. App Store 搜索 **Tailscale** 并安装
2. 打开 Tailscale，点右上角账户图标登录
3. **必须使用和 PC 相同的账号**
4. 打开 **Connect** 开关，状态显示 Connected

### 验证
PC 上打开 PowerShell，运行：

```powershell
tailscale status
```

应该看到类似输出：
```
100.88.22.11  your-pc-name    windows   active
100.66.33.44  your-iphone     ios       active
```

记下 PC 的 `100.x.x.x` 地址，后面要用。

---

## 第 2 步：安装 Ollama 并拉取模型

1. 打开 https://ollama.com/download
2. 下载 Windows 版，双击安装
3. 安装完成后，打开 PowerShell 拉取一个模型：

```powershell
# 推荐入门模型（2GB）
ollama pull llama3.2

# 或更强的（7GB）
ollama pull qwen2.5:7b
```

> 下载速度取决于你的网络，llama3.2 约 2GB，需要几分钟

### 验证
```powershell
ollama list
```
应该能看到你拉取的模型列表。

---

## 第 3 步：配置 Ollama 允许网络访问

默认情况下 Ollama 只能本机访问，需要改成监听所有网络接口：

```powershell
setx OLLAMA_HOST "0.0.0.0"
```

**重要：然后必须重启 Ollama**
- 方法 1：右键系统托盘中的 Ollama 图标 → **Quit Ollama** → 再重新从开始菜单打开
- 方法 2：重启电脑

### 验证环境变量是否生效
```powershell
# 重启 Ollama 后运行
echo $env:OLLAMA_HOST
```
应该输出 `0.0.0.0`

---

## 第 4 步：安装 Docker Desktop 并启动 WebUI

### 安装 Docker Desktop
1. 打开 https://docs.docker.com/desktop/setup/install/windows-install/
2. 下载 Docker Desktop for Windows
3. 双击安装，**确保选择 WSL2 后端**
4. 安装完成后重启电脑
5. 启动 Docker Desktop，等待右下角显示 **Engine running**

### 启动 Open WebUI
```powershell
# 在项目目录下运行
docker compose up -d
```

首次运行会自动拉取镜像（约 1GB），耐心等待。

### 验证
```powershell
docker ps
```
应该看到 `open-webui` 容器在运行，端口 `0.0.0.0:8080`

---

## 第 5 步：从 iPhone 连接

1. 确保 iPhone 的 Tailscale 已打开（显示 Connected）
2. 打开 **Safari**
3. 地址栏输入 `http://<PC的TailscaleIP>:8080`
   - 例如 `http://100.88.22.11:8080`
4. 你会看到 Open WebUI 的注册页面
5. 创建账号（这是 Open WebUI 的管理员账号，存在本机 Docker 中）
6. 登录后，在顶部下拉菜单选择模型（如 `llama3.2`）
7. 输入消息开始聊天

> **查看 IP：** 如果在第 1 步忘了记，PC 上运行 `tailscale ip -4`

---

## 在不同网络下使用

### 在家（同一 WiFi）
- iPhone 和 PC 连同一个路由器
- Tailscale 会自动走 P2P 直连，延迟最低（通常 <5ms）
- 响应速度和 PC 上直接使用基本一样

### 出门在外（蜂窝数据 / 公司 WiFi）
- iPhone 切换到任何网络，Tailscale 保持连接
- 如果无法 P2P 直连，自动切换到 DERP 中继
- 延迟会高一些（取决于中继节点），但功能完全一样
- 不需要任何额外配置

### 判断当前走的是哪种连接
```powershell
tailscale status
```
直连显示 `direct`，中继显示 `relay`。

---

## 常见问题

### Safari 提示"无法打开页面"
- 确认 iPhone 的 Tailscale 已连接（绿色 Connected）
- 确认在 Safari 输入的是 `http://` 不是 `https://`
- 确认 Tailscale IP 地址正确（PC 上运行 `tailscale ip -4`）
- 两台设备必须在同一个 Tailscale 账号下

### 页面打开但显示"连接被拒绝"
- 确认 Ollama 正在运行（PC 上运行 `ollama list`）
- 确认 `OLLAMA_HOST=0.0.0.0` 已设置并重启了 Ollama
- 确认 Docker 容器在运行（`docker ps`）

### WebUI 聊天不回复或报错
- 确认 WebUI 能连上 Ollama：`docker logs open-webui`
- 如果看到 `Connection refused`，重启 WebUI：
  ```powershell
  docker compose restart
  ```

### 响应很慢
- 默认 Ollama 在 Windows 上用 CPU 跑，大模型确实慢
- 可用小模型如 `llama3.2:1b` 或 `qwen2.5:0.5b`
- 如果有 NVIDIA 显卡，安装 CUDA 后可 GPU 加速

### Tailscale 连接不稳定
- 检查网络防火墙是否阻止 Tailscale
- DERP 中继模式下延迟会高一些，属于正常
- 可用 `tailscale ping 100.x.x.x` 测试连通性

---

## 命令速查

```powershell
# Tailscale
tailscale status           # 查看所有设备和连接状态
tailscale ip -4            # 查看本机 Tailscale IP

# Ollama
ollama list                # 查看已拉取的模型
ollama pull <模型名>        # 拉取新模型
ollama run <模型名>         # 在 PC 上直接测试模型

# Docker
docker compose up -d       # 启动 WebUI
docker compose down        # 停止 WebUI
docker compose logs -f     # 查看 WebUI 日志
```

---

## 如果全部手动操作太麻烦

以管理员身份打开 PowerShell，运行：

```powershell
.\scripts\setup.ps1
```

脚本会自动：
- 检查 Tailscale、Ollama、Docker 是否已安装
- 配置 `OLLAMA_HOST=0.0.0.0`
- 检查 Tailscale 连接状态
- 拉取 Open WebUI 镜像
- 启动 WebUI 容器
