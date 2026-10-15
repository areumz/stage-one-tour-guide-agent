from datetime import datetime

from tour_guide.clock import KST
from tour_guide.limits import RateLimiter, SessionStore

T0 = datetime(2026, 10, 13, 12, 0, tzinfo=KST).timestamp()


class Clock:
    def __init__(self, t=T0):
        self.t = t

    def __call__(self):
        return self.t


def test_per_minute_window():
    c = Clock()
    rl = RateLimiter(per_minute=3, per_ip_daily=100, global_daily=100, clock=c)
    assert [rl.check("1.1.1.1") for _ in range(4)] == [True, True, True, False]
    assert rl.check("2.2.2.2") is True  # 다른 IP 는 영향 없음
    c.t += 61
    assert rl.check("1.1.1.1") is True


def test_per_ip_daily():
    c = Clock()
    rl = RateLimiter(per_minute=100, per_ip_daily=2, global_daily=100, clock=c)
    assert rl.check("a") and rl.check("a")
    assert rl.check("a") is False
    assert rl.check("b") is True


def test_global_daily_kill_switch():
    c = Clock()
    rl = RateLimiter(per_minute=100, per_ip_daily=100, global_daily=2, clock=c)
    assert rl.check("a") and rl.check("b")
    assert rl.check("c") is False


def test_rejected_requests_are_not_counted():
    c = Clock()
    rl = RateLimiter(per_minute=1, per_ip_daily=2, global_daily=100, clock=c)
    assert rl.check("a") is True
    assert rl.check("a") is False  # 분당 초과: 일일 카운트에 넣지 않는다
    c.t += 61
    assert rl.check("a") is True
    c.t += 61
    assert rl.check("a") is False  # 일일 2회 소진


def test_resets_at_kst_midnight():
    c = Clock()
    rl = RateLimiter(per_minute=100, per_ip_daily=1, global_daily=1, clock=c)
    assert rl.check("a") is True
    assert rl.check("a") is False
    c.t = datetime(2026, 10, 14, 0, 1, tzinfo=KST).timestamp()
    assert rl.check("a") is True


def _store(c, **kw):
    return SessionStore(clock=c, **kw)


def test_history_keeps_only_recent_turns_and_counts_commits():
    s = _store(Clock(), history_turns=2)
    for i in range(3):
        s.commit("a", f"q{i}", f"a{i}")
    assert s.history("a") == [("q1", "a1"), ("q2", "a2")]
    assert s.history("nobody") == []


def test_turn_limit_counts_committed_turns_only():
    s = _store(Clock(), turn_limit=2)
    assert s.turn_limit_reached("a") is False  # 없는 세션은 만들지 않는다
    s.commit("a", "q", "a")
    assert s.turn_limit_reached("a") is False
    s.commit("a", "q", "a")
    assert s.turn_limit_reached("a") is True
    assert s.turn_limit_reached("b") is False


def test_acquire_release_and_busy():
    s = _store(Clock())
    assert s.try_acquire("a") is not None
    assert s.try_acquire("a") is None
    assert s.try_acquire("b") is not None  # 다른 세션은 영향 없음
    s.release("a")
    assert s.try_acquire("a") is not None
    s.release("zzz")  # 없는 세션 해제는 조용히 무시


def test_stale_in_flight_mark_is_ignored():
    c = Clock()
    s = _store(c, busy_stale_seconds=120)
    assert s.try_acquire("a") is not None
    c.t += 119
    assert s.try_acquire("a") is None
    c.t += 2
    assert s.try_acquire("a") is not None  # 해제 누락 안전망


def test_ttl_expires_idle_session_and_unknown_id_starts_fresh():
    c = Clock()
    s = _store(c, ttl_seconds=1800)
    s.commit("a", "q", "a")
    c.t += 1801
    assert s.history("a") == []
    assert s.turn_limit_reached("a") is False
    s.commit("a", "q2", "a2")  # 만료된 id 도 새 세션으로 정상 동작
    assert s.history("a") == [("q2", "a2")]


def test_lru_evicts_oldest_and_skips_in_flight():
    c = Clock()
    s = _store(c, max_sessions=2)
    s.commit("old", "q", "a")
    c.t += 1
    assert s.try_acquire("busy") is not None
    c.t += 1
    s.commit("new", "q", "a")  # 세 번째 세션: 가장 오래된 것부터, 진행 중은 건너뛴다
    assert s.history("old") == []
    assert s.history("new") == [("q", "a")]
    assert s.try_acquire("busy") is None  # 진행 중 세션은 남아 있다


def test_history_returns_a_copy():
    s = _store(Clock())
    s.commit("a", "q", "a")
    s.history("a").append(("x", "y"))
    assert s.history("a") == [("q", "a")]


def test_stale_request_cannot_release_a_newer_requests_mark():
    c = Clock()
    s = _store(c, busy_stale_seconds=120)
    old = s.try_acquire("a")
    c.t += 121  # 첫 요청이 오래 걸려 표시가 오래된 것으로 취급된다
    new = s.try_acquire("a")
    assert new is not None and new != old
    s.release("a", old)  # 늦게 끝난 첫 요청의 해제는 새 요청의 표시를 지우지 않는다
    assert s.try_acquire("a") is None
    s.release("a", new)
    assert s.try_acquire("a") is not None
