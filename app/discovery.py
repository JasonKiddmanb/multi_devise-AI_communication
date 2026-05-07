"""AI Remote Compute Mesh — 设备发现 + Ollama 扫描模块"""
import json
import platform
import socket
import subprocess
import urllib.request
from logger import log

OLLAMA_PORT = 11434

def get_local_ip() -> str:
    """获取本机 Tailscale IP"""
    try:
        r = subprocess.run(["tailscale", "ip", "-4"], capture_output=True, text=True, timeout=5)
        if r.returncode == 0:
            ip = r.stdout.strip()
            if ip:
                return ip
    except Exception:
        pass
    return "127.0.0.1"

def get_host_info() -> dict:
    """返回本机信息"""
    return {
        "name": socket.gethostname(),
        "os": platform.system().lower(),
    }

def get_tailscale_peers() -> list[dict]:
    """通过 tailscale status --json 获取所有设备"""
    try:
        r = subprocess.run(["tailscale", "status", "--json"],
                          capture_output=True, text=True, timeout=5)
        if r.returncode != 0:
            return []
        data = json.loads(r.stdout)
        peers = data.get("Peer")
        if not peers:
            return []
        result = []
        for ip, info in peers.items():
            if not info.get("Online"):
                continue
            result.append({
                "ip": ip,
                "name": info.get("HostName", ip),
                "os": (info.get("OS") or "unknown").lower(),
            })
        return result
    except Exception as e:
        log.warning("Tailscale peer discovery failed: %s", e)
        return []

def scan_ollama(ip: str) -> list[dict] | None:
    """探测设备上是否运行 Ollama，返回模型列表"""
    url = f"http://{ip}:{OLLAMA_PORT}/api/tags"
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=3) as resp:
            data = json.loads(resp.read())
            return data.get("models", [])
    except Exception:
        return None

def discover() -> dict:
    """发现所有设备及其 Ollama 模型"""
    tailscale_ip = get_local_ip()
    host_info = get_host_info()

    # 始终扫描本机
    local_models = scan_ollama("127.0.0.1")
    if local_models is None:
        local_models = scan_ollama(tailscale_ip)

    nodes = [{
        "ip": tailscale_ip,
        "name": host_info["name"],
        "os": host_info["os"],
        "is_self": True,
        "online": True,
        "models": local_models or [],
    }]

    # 扫描 Tailscale 网络中的其他设备
    for peer in get_tailscale_peers():
        if peer["ip"] == tailscale_ip:
            continue  # 跳过自己
        log.info("Scanning Ollama on %s (%s)", peer["name"], peer["ip"])
        models = scan_ollama(peer["ip"])
        if models is not None:
            nodes.append({
                "ip": peer["ip"],
                "name": peer["name"],
                "os": peer["os"],
                "is_self": False,
                "online": True,
                "models": models,
            })
            log.info("Found Ollama on %s (%s): %d models",
                     peer["name"], peer["ip"], len(models))

    return {"nodes": nodes}
