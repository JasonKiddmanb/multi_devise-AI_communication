# V2 — Multi-Platform Compute Mesh

> 目标：实现 iOS/macOS/iPadOS/Windows/Linux 双向计算共享、文件传输和远程桌面。

## 组件

| 组件 | 用途 | 许可证 | 状态 |
|------|------|--------|------|
| [Headscale](v2/headscale/) | 自托管 Tailscale 协调服务器 | BSD | 待规划 |
| [RustDesk](v2/rustdesk/) | 远程桌面（替代 TeamViewer） | AGPL | 待规划 |
| [LocalSend](v2/localsend/) | 加密 LAN 文件传输 | MIT | 待规划 |
| [WebRTC](v2/webrtc/) | 浏览器端 P2P 通信 | — | 待规划 |

## 架构演进

```
V1 (当前)          V2 (规划)
┌──────┐           ┌──────┐
│ iOS  │───VPN──→ │ PC   │    →    │ Mac  │←──→│ PC   │
└──────┘           └──────┘        │ iPad │←──→│ Linux│
                                   │ iOS  │←──→│ 任何  │
                                   └──────┘    └──────┘
                                   双向计算 + 文件 + 远程桌面
                                   全部走 Tailscale 加密隧道
```

## 网络拓扑

- **Tailscale 作为 overlay 网络** — 所有设备在 `100.64.0.0/10` 内分配 IP
- **Headscale**（可选） — 自控制协调服务器，不依赖 Tailscale SaaS
- **WebRTC** — 浏览器间 P2P，可用于未来 Web 客户端直接通信
- 所有流量经 WireGuard 加密

## 安全准则

- 不向公网暴露任何端口
- 可选的 Tailscale ACL 限制设备间访问
- 不使用非标准加密实现
