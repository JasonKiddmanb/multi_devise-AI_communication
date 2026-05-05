# App 分发包使用说明

## 这是什么？

`app/` 目录是一个**自包含的分发包**。用户下载后，只需要：

1. 运行 `tools\download.bat` 下载 Ollama 和 Tailscale（一次性的）
2. 双击 `start.bat` 启动服务
3. iPhone 上打开 Safari 就能用

**不需要安装 Docker，不需要手动配置环境变量，不需要记命令。**

---

## 分发给用户前的准备

### 方法一：用户自行下载（推荐）

把整个 `app/` 文件夹发给用户，用户运行：

```powershell
# 双击即可，自动下载 Ollama + Tailscale
app\tools\download.bat
```

### 方法二：你打包好再分发

如果你要做一个完整的离线包，先在自己电脑上运行 `download.bat`：

```powershell
# 这会下载文件到 tools/ollama/ 和 tools/tailscale/
app\tools\download.bat
```

然后把整个 `app/` 文件夹压缩发出去。用户解压后直接双击 `start.bat` 即可，不需要再下载任何东西。

> **注意：** Tailscale 安装包约 20MB，Ollama 约 500MB。建议先压缩再分发。

---

## 用户操作流程

### PC 端

1. **解压** 你发的文件夹
2. 进入 `app/` 目录
3. **双击 `start.bat`**（如果弹出管理员权限提示，点"是"）
4. 等待脚本自动完成：
   - 安装 Tailscale（如果系统没有）
   - 弹出浏览器登录 Tailscale 账号
   - 启动 Ollama 和聊天网页
5. 命令行窗口显示 Tailscale IP，如 `100.88.22.11`

### iPhone 端

1. App Store 搜索 **Tailscale** 安装
2. 登录**同一个** Tailscale 账号
3. 打开 **Safari** → 输入 `http://<PC的TailscaleIP>:8080`
4. 选择模型 → 开始聊天

---

## 常见问题

### 弹出"需要管理员权限"
第一次运行需要管理员权限来：
- 安装 Tailscale（如果系统没有）
- 启动 Web 服务器监听 8080 端口

以后运行可能不需要（如果 Tailscale 已经安装）。

### 提示 Ollama 没有模型
在 PC 的 PowerShell 中运行：

```powershell
ollama pull llama3.2
```

拉取完成后，刷新 iPhone 上的网页即可。

### 如何停止
在命令行窗口按 `Ctrl+C`，脚本会自动关闭 Ollama 和 Web 服务器。

### 能不能开机自启？
可以把 `start.bat` 添加到 Windows 开机启动项：

```powershell
# 创建一个快捷方式到启动文件夹
shell:startup
```
