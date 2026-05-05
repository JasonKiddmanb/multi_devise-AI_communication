#!/usr/bin/env bash
set -euo pipefail

# --------------------------------------------------
# AI Remote Compute Mesh — Linux/macOS setup (V1)
# 所有流量经 Tailscale WireGuard 加密隧道，支持 LAN 直连和远程中继
# --------------------------------------------------

RED='\033[0;31m'; GREEN='\033[0;32m'; CYAN='\033[0;36m'; YELLOW='\033[1;33m'; NC='\033[0m'
STEP=0
step() { STEP=$((STEP+1)); echo -e "\n${CYAN}[$STEP] $1${NC}"; }
check_cmd() {
    if command -v "$1" &>/dev/null; then echo -e "  ${GREEN}✔ $1 found${NC}"; return 0
    else echo -e "  ${RED}✘ $1 not found${NC}"; return 1; fi
}

# --------------------------------------------------
step "Checking prerequisites"
# --------------------------------------------------
has_docker=true; has_ollama=true; has_tailscale=true
check_cmd docker || has_docker=false
check_cmd ollama  || { echo -e "  ${YELLOW}→ Install from https://ollama.com/download${NC}"; has_ollama=false; }
check_cmd tailscale || { echo -e "  ${YELLOW}→ Install from https://tailscale.com/download${NC}"; has_tailscale=false; }

$has_docker && $has_ollama && $has_tailscale || exit 1

# --------------------------------------------------
step "Configuring Ollama for Tailscale network access"
# --------------------------------------------------
if [ "${OLLAMA_HOST:-}" != "0.0.0.0" ]; then
    echo -e "  ${YELLOW}Setting OLLAMA_HOST=0.0.0.0${NC}"
    echo 'export OLLAMA_HOST=0.0.0.0' | sudo tee /etc/profile.d/ollama-host.sh >/dev/null
    export OLLAMA_HOST=0.0.0.0
    echo -e "  ${YELLOW}⚠ Restart Ollama: systemctl restart ollama (Linux) or quit/relaunch (macOS)${NC}"
else
    echo -e "  ${GREEN}✔ OLLAMA_HOST already set to 0.0.0.0${NC}"
fi

# --------------------------------------------------
step "Checking Tailscale status"
# --------------------------------------------------
TS_IP=$(tailscale ip -4 2>/dev/null || true)
if [ -n "$TS_IP" ]; then
    echo -e "  ${GREEN}✔ Tailscale is online — IP: $TS_IP${NC}"
    echo -e "  → 同 LAN 下走直连，远程走 DERP 中继，自动切换"
else
    echo -e "  ${RED}✘ Tailscale not connected. Run 'tailscale up'${NC}"; exit 1
fi

# --------------------------------------------------
step "Launching Open WebUI"
# --------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

docker pull ghcr.io/open-webui/open-webui:main
docker compose -f "$PROJECT_ROOT/docker-compose.yml" up -d

echo -e "\n  ${GREEN}✔ Open WebUI is running!${NC}"
echo -e "  ${CYAN}─────────────────────────────────────${NC}"
echo -e "  ${CYAN}Local:    http://localhost:8080${NC}"
echo -e "  ${CYAN}Over VPN: http://${TS_IP}:8080${NC}"
echo -e "  ${CYAN}─────────────────────────────────────${NC}"
echo -e "\n  Next: Open Safari on iOS → http://${TS_IP}:8080"
