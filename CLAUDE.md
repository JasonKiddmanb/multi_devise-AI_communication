# CLAUDE.md — AI Remote Compute Mesh

## Interaction Preference
- Always respond in Chinese (Simplified), regardless of the input language.

## Project Vision
- Build a personal, secure, decentralized AI compute mesh.
- V1 (current): Access Windows PC's Ollama from iOS via browser, over Tailscale VPN — works outside LAN.
- V2: Extend to iOS/macOS/iPadOS/Windows/Linux — bidirectional compute sharing, file transfer, remote desktop. All traffic inside Tailscale's encrypted tunnels.

## Current Architecture & Key Decisions
- **Client strategy:** Browser-first, no native iOS app yet.
  - Tailscale’s system VPN lets Safari reach private Tailscale IPs — zero additional code on iOS.
  - Deploy Open WebUI on the PC, access it from iPhone Safari via `http://<PC-Tailscale-IP>:8080`.
  - PWA can provide app-like experience later without App Store.
- **How it works outside LAN:**
  - Tailscale assigns a stable `100.x.x.x` IP to the PC, reachable from anywhere.
  - Automatically handles NAT traversal; falls back to encrypted DERP relays if direct P2P fails.
  - Connection is always encrypted (WireGuard), no port exposure to the public internet.
- **LAN vs. remote path — automatic:**
  - Tailscale continuously probes available paths (LAN IP, WAN IP, relays).
  - When both devices are on the same LAN, it automatically uses the LAN path for lower latency.
  - When the device leaves the LAN, it seamlessly fails over to a relayed or direct WAN path.
  - No manual switching, no MAC address logic needed.

## Tech Stack
- **Network layer:** Tailscale (WireGuard mesh VPN)
- **AI inference:** Ollama
- **Web UI:** Open WebUI (MIT license)
- **Future components:**
  - RustDesk — remote desktop (AGPL)
  - LocalSend — encrypted LAN file transfer (MIT)
  - Headscale — self-hosted Tailscale coordinator
  - WebRTC — P2P communication

## Ports & IPs
- Ollama API: `11434`
- Open WebUI: `8080`
- Tailscale IP range: `100.64.0.0/10`

## Developer Preferences
- Always prefer open-source solutions (MIT, Apache, AGPL).
- All cross-device communication must be encrypted. No plaintext HTTP over public networks.
- Avoid non-standard cryptographic implementations to prevent export compliance issues.

## Roadmap
- **V1 (current):** iOS → VPN → Browser → Web UI → PC Ollama (works from anywhere)
- **V2:** Multi-platform mesh with bidirectional calls, file sharing, remote desktop — all over Tailscale.