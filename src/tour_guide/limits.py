import time
from collections import OrderedDict, deque
from collections.abc import Callable
from dataclasses import dataclass, field
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


@dataclass
class _Session:
    history: list[tuple[str, str]] = field(default_factory=list)
    committed_turns: int = 0
    in_flight_since: float | None = None
    # 어느 요청의 표시인지 구분한다. 오래된 요청의 release 가 새 요청의 표시를 지우지 않게 한다
    in_flight_token: int = 0
    last_used: float = 0.0


class SessionStore:
    """서버 메모리 세션: 최근 N턴 텍스트, 커밋된 턴 수, 진행 중 표시 (설계 §7, §7.3).

    이벤트 루프가 하나라 "확인 -> 표시" 사이에 await 만 없으면 락이 필요 없다.
    재시작 시 사라지는 것은 "대화는 저장하지 않음" 원칙상 허용한다.
    """

    def __init__(
        self,
        *,
        max_sessions: int = 500,
        ttl_seconds: float = 1800.0,
        history_turns: int = 6,
        turn_limit: int = 20,
        busy_stale_seconds: float = 120.0,
        clock: Callable[[], float] = time.time,
    ):
        self._max = max_sessions
        self._ttl = ttl_seconds
        self._turns = history_turns
        self._turn_limit = turn_limit
        self._stale = busy_stale_seconds
        self._clock = clock
        self._token = 0
        # 마지막 사용 순서로 유지한다 (앞이 가장 오래된 것)
        self._items: OrderedDict[str, _Session] = OrderedDict()

    def _busy(self, s: _Session, now: float) -> bool:
        # 해제 누락 버그가 있어도 세션이 영구히 막히지 않게 오래된 표시는 무시한다
        return s.in_flight_since is not None and now - s.in_flight_since < self._stale

    def _purge(self, now: float) -> None:
        for sid in list(self._items):
            s = self._items[sid]
            if now - s.last_used < self._ttl:
                break
            if not self._busy(s, now):
                del self._items[sid]

    def _touch(self, sid: str, now: float) -> _Session:
        self._purge(now)
        s = self._items.get(sid)
        if s is None:
            s = self._items[sid] = _Session()
            while len(self._items) > self._max:
                victim = next((k for k, v in self._items.items() if k != sid and not self._busy(v, now)), None)
                if victim is None:
                    break
                del self._items[victim]
        s.last_used = now
        self._items.move_to_end(sid)
        return s

    def _peek(self, sid: str, now: float) -> _Session | None:
        self._purge(now)
        return self._items.get(sid)

    def turn_limit_reached(self, sid: str) -> bool:
        s = self._peek(sid, self._clock())
        return s is not None and s.committed_turns >= self._turn_limit

    def history(self, sid: str) -> list[tuple[str, str]]:
        s = self._peek(sid, self._clock())
        return list(s.history) if s else []

    def try_acquire(self, sid: str) -> int | None:
        """표시를 잡으면 토큰(양수)을, 이미 진행 중이면 None 을 돌려준다."""
        now = self._clock()
        s = self._touch(sid, now)
        if self._busy(s, now):
            return None
        self._token += 1
        s.in_flight_since = now
        s.in_flight_token = self._token
        return self._token

    def release(self, sid: str, token: int | None = None) -> None:
        s = self._items.get(sid)
        # 토큰이 다르면 오래된 요청이 새 요청의 표시를 지우려는 것이므로 무시한다
        if s is not None and (token is None or s.in_flight_token == token):
            s.in_flight_since = None

    def commit(self, sid: str, user: str, assistant: str) -> None:
        s = self._touch(sid, self._clock())
        s.history.append((user, assistant))
        del s.history[: -self._turns]
        s.committed_turns += 1
