"""AI Remote Compute Mesh — 认证模块"""
import hashlib
import secrets
from datetime import datetime, timedelta
from config import SESSION_DAYS

PBKDF2_ITERATIONS = 60000

def hash_password(password: str) -> str:
    """返回 'iterations$hexsalt$hexhash' 格式的 PBKDF2-SHA256 哈希"""
    salt = secrets.token_bytes(32)
    key = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, PBKDF2_ITERATIONS)
    return f"{PBKDF2_ITERATIONS}${salt.hex()}${key.hex()}"

def verify_password(password: str, stored: str) -> bool:
    """验证密码，使用 timing-safe 比较
       支持两种格式:
         'iterations$salt$hash' (新格式, 含迭代次数)
         'salt$hash' (旧格式, 默认 100000 迭代)
    """
    try:
        parts = stored.split('$')
        if len(parts) == 3:
            iterations = int(parts[0])
            salt_hex, key_hex = parts[1], parts[2]
        elif len(parts) == 2:
            iterations = 100000  # 旧格式默认值
            salt_hex, key_hex = parts[0], parts[1]
        else:
            return False
    except (ValueError, AttributeError):
        return False
    salt = bytes.fromhex(salt_hex)
    expected = bytes.fromhex(key_hex)
    actual = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, iterations)
    return secrets.compare_digest(expected, actual)

def generate_token() -> str:
    return secrets.token_hex(32)  # 64 字符

def make_expires_at() -> str:
    return (datetime.now() + timedelta(days=SESSION_DAYS)).isoformat()
