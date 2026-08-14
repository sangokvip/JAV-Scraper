"""
在线试看服务：把 player/av_player_server.py 的 Flask 应用
在 GUI 进程内以守护线程启动（空闲端口自动分配），
代理沿用 GUI 的代理设置。打包版随 app 一起分发，无需单独开终端。
"""
import importlib.util
import os
import socket
import sys
import threading

from lib.logger import get_logger

log = get_logger(__name__)

_lock = threading.Lock()
_state = {"port": None, "module": None}


def _player_dir() -> str:
    # 打包态：PyInstaller 解包目录；开发态：项目根/player
    base = getattr(sys, '_MEIPASS', None)
    if base and os.path.isdir(os.path.join(base, 'player')):
        return os.path.join(base, 'player')
    return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'player')


def ensure_server(proxy_url: str = None) -> int:
    """
    启动（或复用）本地播放服务器，返回监听端口。
    flask 未安装或加载失败时抛出异常，由调用方向用户解释。
    """
    with _lock:
        if _state["port"]:
            if _state["module"] is not None:
                _state["module"].PROXY = proxy_url or None
            return _state["port"]

        server_py = os.path.join(_player_dir(), "av_player_server.py")
        spec = importlib.util.spec_from_file_location("av_player_server", server_py)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        mod.PROXY = proxy_url or None

        # 端口 0 由系统分配空闲端口，避免 5000 被占用
        probe = socket.socket()
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
        probe.close()

        threading.Thread(
            target=lambda: mod.app.run(host="127.0.0.1", port=port, debug=False,
                                       threaded=True, use_reloader=False),
            daemon=True,
        ).start()

        _state["port"] = port
        _state["module"] = mod
        log.info(f"在线播放服务已启动: http://127.0.0.1:{port}")
        return port
