# RustDesk — 远程桌面

## 用途
通过 Tailscale 网络提供远程桌面能力，替代 TeamViewer/AnyDesk。

## 架构
- 自建 RustDesk Server（中继）或纯 P2P
- 客户端通过 Tailscale IP 直连
- 所有流量在 WireGuard 隧道内传输
