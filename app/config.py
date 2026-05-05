"""AI Remote Compute Mesh — 配置常量"""
import os

APP_DIR  = os.path.dirname(os.path.abspath(__file__))
WEB_DIR  = os.path.join(APP_DIR, "web")
DB_PATH  = os.path.join(APP_DIR, "history.db")
LOG_PATH = os.path.join(APP_DIR, "server.log")
PORT     = 8080

SESSION_DAYS = 7

# 管理员默认密码（仅首次初始化时使用）
ADMIN_DEFAULT_PASSWORD = os.environ.get("ADMIN_DEFAULT_PASSWORD", "admin123")

# MAC 白名单 — 逗号分隔的 MAC 地址（无分隔符，小写十六进制）
# 例: "aabbccddeeff,112233445566"
# 留空则仅检查 localhost（不检查 MAC）
ADMIN_MAC_WHITELIST = [
    m for m in os.environ.get("ADMIN_MAC_WHITELIST", "")
    .lower().replace(":", "").replace("-", "").split(",")
    if len(m) == 12
]
