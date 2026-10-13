from datetime import datetime

from tour_guide.clock import KST
from tour_guide.limits import RateLimiter

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
