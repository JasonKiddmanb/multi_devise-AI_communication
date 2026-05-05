"""AI Remote Compute Mesh — 日志系统"""
import logging
import logging.handlers
import sys
from config import LOG_PATH

def setup_logging() -> logging.Logger:
    logger = logging.getLogger("ai-remote")
    logger.setLevel(logging.INFO)

    # 文件 — 5MB 滚动，保留 3 个备份
    fh = logging.handlers.RotatingFileHandler(
        LOG_PATH, maxBytes=5_000_000, backupCount=3, encoding="utf-8"
    )
    fh.setLevel(logging.INFO)
    fh.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
    ))
    logger.addHandler(fh)

    # 控制台
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.INFO)
    ch.setFormatter(logging.Formatter("[%(levelname)s] %(message)s"))
    logger.addHandler(ch)

    return logger

log = setup_logging()
