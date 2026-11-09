"""Rate limiting and admin session handling."""
from __future__ import annotations

import hashlib
import hmac
import secrets
import threading
import time
from collections import defaultdict, deque


class RateLimiter:
    """Sliding-window limiter keyed by (bucket, client IP). In-memory: per process."""

    def __init__(self):
        self._hits: dict[tuple[str, str], deque] = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, bucket: str, key: str, limit: int, window: int) -> tuple[bool, int]:
        now = time.monotonic()
        with self._lock:
            q = self._hits[(bucket, key)]
            while q and now - q[0] > window:
                q.popleft()
            if len(q) >= limit:
                return False, int(window - (now - q[0])) + 1
            q.append(now)
            return True, 0


class AdminSessions:
    """Stateless signed session cookie: '<expiry>.<nonce>.<hmac>'."""
    COOKIE = "qd_admin"
    TTL = 8 * 3600

    def __init__(self, secret: str, token: str):
        self._secret = secret.encode()
        self._token = token
        self._fail = RateLimiter()

    @property
    def enabled(self) -> bool:
        return len(self._token) >= 16

    def check_token(self, candidate: str, ip: str) -> bool:
        ok_rate, _ = self._fail.allow("admin-login", ip, 10, 900)
        if not ok_rate or not self.enabled:
            return False
        return hmac.compare_digest(candidate.encode(), self._token.encode())

    def _sign(self, payload: str) -> str:
        return hmac.new(self._secret, payload.encode(), hashlib.sha256).hexdigest()

    def issue(self) -> str:
        payload = f"{int(time.time()) + self.TTL}.{secrets.token_hex(8)}"
        return f"{payload}.{self._sign(payload)}"

    def verify(self, cookie_value: str | None) -> bool:
        if not cookie_value or cookie_value.count(".") != 2:
            return False
        exp, nonce, sig = cookie_value.split(".")
        if not hmac.compare_digest(sig, self._sign(f"{exp}.{nonce}")):
            return False
        try:
            return int(exp) > time.time()
        except ValueError:
            return False
