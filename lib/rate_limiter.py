"""
进程级请求限速器。

把「并发度」与「出网 QPS」解耦：worker 可以并发跑，
但对同一平台的请求间隔由全局限速器统一保证，
避免并发数提高后请求频率线性放大导致封禁。
"""
import threading
import time


class RateLimiter:
    """最小间隔限速器：所有线程共享，acquire() 返回即获得放行。"""

    def __init__(self, min_interval: float):
        self.min_interval = float(min_interval)
        self._lock = threading.Lock()
        self._next_allowed = 0.0

    def acquire(self):
        if self.min_interval <= 0:
            return
        with self._lock:
            now = time.monotonic()
            wait = self._next_allowed - now
            if wait > 0:
                # 排队占位：后来的线程顺延一个间隔，保证全局节奏均匀
                self._next_allowed += self.min_interval
            else:
                self._next_allowed = now + self.min_interval
                wait = 0.0
        if wait > 0:
            time.sleep(wait)


# 每个平台一个全局限速器
_limiters = {}
_limiters_lock = threading.Lock()


def get_limiter(name: str, min_interval: float) -> RateLimiter:
    with _limiters_lock:
        limiter = _limiters.get(name)
        if limiter is None:
            limiter = RateLimiter(min_interval)
            _limiters[name] = limiter
        return limiter
