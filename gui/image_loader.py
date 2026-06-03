import requests
from PySide6.QtCore import QRunnable, QObject, Signal

class ImageLoadSignals(QObject):
    loaded = Signal(str, str, bytes, bool)  # filepath, url, content, is_poster
    finished_worker = Signal(object)        # worker object itself

class ImageLoadWorker(QRunnable):
    """
    后台图片异步网络下载 Worker，解耦主线程以防图片解析加载网络 I/O 阻塞 GUI 刷新。
    """
    def __init__(self, filepath: str, url: str, proxies: dict = None, session: requests.Session = None, is_poster: bool = False):
        super().__init__()
        self.filepath = filepath
        self.url = url
        self.proxies = proxies
        self.session = session
        self.is_poster = is_poster
        self.signals = ImageLoadSignals()

    def run(self):
        try:
            try:
                caller = self.session if self.session else requests
                r = caller.get(self.url, timeout=10, proxies=self.proxies)
                if r.status_code == 200:
                    self.signals.loaded.emit(self.filepath, self.url, r.content, self.is_poster)
            except Exception:
                pass
        finally:
            self.signals.finished_worker.emit(self)

def _parse_cookie_string(cookie_string: str) -> dict:
    cookies = {}
    raw = str(cookie_string or "").strip()
    if not raw:
        return cookies
    for part in raw.split(";"):
        pair = part.strip()
        if not pair or "=" not in pair:
            continue
        key, value = pair.split("=", 1)
        key = key.strip()
        value = value.strip()
        if key:
            cookies[key] = value
    return cookies

def _normalize_javdb_cookie_input(cookie_input: str) -> dict:
    raw = str(cookie_input or "").strip()
    if not raw:
        return {}
    parsed = _parse_cookie_string(raw)
    if not parsed:
        parsed = {"_jdb_session": raw}
    session_value = str(parsed.get("_jdb_session", "")).strip()
    if not session_value:
        return {}
    normalized = {
        "_jdb_session": session_value,
        "list_mode": "h",
        "theme": "auto",
        "over18": "1",
        "locale": "zh",
    }
    for key in ("list_mode", "theme", "over18", "locale"):
        value = str(parsed.get(key, "")).strip()
        if value:
            normalized[key] = value
    return normalized

class SearchSignals(QObject):
    finished = Signal(list, str)  # codes, error_msg
    finished_worker = Signal(object)

class SearchWorker(QRunnable):
    """
    后台搜索 Worker，防范由于网络请求延迟挂起 GUI 主线程。
    """
    def __init__(self, keyword: str, page: int, proxies: dict = None, cookie_string: str = ""):
        super().__init__()
        self.keyword = keyword
        self.page = page
        self.proxies = proxies
        self.cookie_string = cookie_string
        self.signals = SearchSignals()

    def run(self):
        try:
            try:
                from javdb_api import JavdbAPI
                
                api = JavdbAPI()
                
                if self.cookie_string:
                    cookies = _normalize_javdb_cookie_input(self.cookie_string)
                    for k, v in cookies.items():
                        api.session.cookies.set(k, v)
                        
                if self.proxies:
                    api.session.proxies.update(self.proxies)
                    
                res = api.search_videos(self.keyword, page=self.page)
                videos = res.get("videos", [])
                codes = []
                for v in videos:
                    c = v.get("code")
                    if c:
                        codes.append(c.upper())
                self.signals.finished.emit(codes, "")
            except Exception as e:
                self.signals.finished.emit([], str(e))
        finally:
            self.signals.finished_worker.emit(self)
