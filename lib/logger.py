"""
统一日志。

config.py 早已定义 LOG_LEVEL/LOG_FORMAT 但全项目一直用 print——
打包成 GUI 后输出直接进虚空，无从排查。日志现在同时进：
- 控制台（开发态可见）
- DATA_DIR/logs/app.log 滚动文件（打包版用户可提供给开发者）
"""
import logging
import logging.handlers
import sys

import config

_configured = False


def setup_logging():
    """进程内幂等初始化，main.py 启动时调用一次。"""
    global _configured
    if _configured:
        return
    _configured = True

    level = getattr(logging, str(getattr(config, 'LOG_LEVEL', 'INFO')).upper(), logging.INFO)
    fmt = getattr(config, 'LOG_FORMAT', '%(asctime)s [%(levelname)s] %(name)s: %(message)s')
    datefmt = getattr(config, 'LOG_DATE_FORMAT', '%Y-%m-%d %H:%M:%S')
    formatter = logging.Formatter(fmt, datefmt)

    root = logging.getLogger()
    root.setLevel(level)

    console = logging.StreamHandler(sys.stderr)
    console.setFormatter(formatter)
    root.addHandler(console)

    try:
        log_dir = config.DATA_DIR / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        file_handler = logging.handlers.RotatingFileHandler(
            log_dir / "app.log", maxBytes=2 * 1024 * 1024, backupCount=3, encoding="utf-8")
        file_handler.setFormatter(formatter)
        root.addHandler(file_handler)
    except Exception:
        # 文件日志不可用时保底控制台输出，不阻塞启动
        pass


def get_logger(name: str) -> logging.Logger:
    setup_logging()
    return logging.getLogger(name)
