import time
from collections import deque
from collections.abc import Callable
from datetime import date, datetime

from tour_guide.clock import KST


class RateLimiter:
    """IP별 분당·일일 한도와 전체 일일 한도(킬스위치). 서버 메모리라 재시작 시 초기화 (best-effort, 설계 §6)."""

    def __init__(
        self,
        per_minute: int,
        per_ip_daily: int,
        global_daily: int,
        clock: Callable[[], float] = time.time,
    ):
        self._per_minute = per_minute
        self._per_ip_daily = per_ip_daily
        self._global_daily = global_daily
        self._clock = clock
        self._recent: dict[str, deque[float]] = {}
        self._daily: dict[str, int] = {}
        self._global = 0
        self._day: date | None = None

    def _roll_day(self, now: float) -> None:
        day = datetime.fromtimestamp(now, KST).date()
        if day != self._day:
            # 자정(KST)마다 전부 비우므로 IP 딕셔너리는 하루치 이상 커지지 않는다
            self._day = day
            self._recent.clear()
            self._daily.clear()
            self._global = 0

    def check(self, ip: str) -> bool:
        now = self._clock()
        self._roll_day(now)
        if self._global >= self._global_daily:
            return False
        if self._daily.get(ip, 0) >= self._per_ip_daily:
            return False
        window = self._recent.setdefault(ip, deque())
        while window and now - window[0] >= 60:
            window.popleft()
        if len(window) >= self._per_minute:
            return False
        window.append(now)
        self._daily[ip] = self._daily.get(ip, 0) + 1
        self._global += 1
        return True
