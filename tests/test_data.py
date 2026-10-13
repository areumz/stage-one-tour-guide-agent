import httpx
import pytest

from tests.conftest import MINI_RAW
from tour_guide.data import (
    ArtistsCache,
    DataUnavailable,
    Show,
    city_names,
    load_shows,
    make_http_fetcher,
    slug_set,
)


class Clock:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t


def make_fetch(results):
    """results: 호출마다 소비되는 dict 또는 Exception 리스트."""
    calls = []

    async def fetch():
        calls.append(1)
        r = results[min(len(calls) - 1, len(results) - 1)]
        if isinstance(r, Exception):
            raise r
        return r

    fetch.calls = calls
    return fetch


def test_load_shows_from_featured_cities(artists):
    shows = load_shows(artists[1])
    assert shows == [
        Show("velvet", "BUS", "부산", shows[0].date),
        Show("velvet", "SEO", "서울", shows[1].date),
    ]
    assert shows[0].date.isoformat() == "2026-09-24"


def test_enums(artists):
    assert slug_set(artists) == frozenset({"aurora", "velvet"})
    names = city_names(artists)
    assert names["SEO"] == "서울"
    assert set(names) == {"LA", "SEO", "TYO", "BUS"}


async def test_cache_hits_within_ttl():
    clock = Clock()
    fetch = make_fetch([MINI_RAW])
    cache = ArtistsCache(fetch, ttl_seconds=300, clock=clock)
    await cache.get()
    clock.t = 299
    await cache.get()
    assert len(fetch.calls) == 1
    clock.t = 301
    await cache.get()
    assert len(fetch.calls) == 2


async def test_stale_served_on_failure_and_retry_backoff():
    clock = Clock()
    fetch = make_fetch([MINI_RAW, RuntimeError("down"), MINI_RAW])
    cache = ArtistsCache(fetch, ttl_seconds=300, clock=clock)
    first = await cache.get()
    clock.t = 301
    stale = await cache.get()  # 실패 → 이전 값
    assert [a.slug for a in stale] == [a.slug for a in first]
    assert len(fetch.calls) == 2
    clock.t = 320  # 실패 후 30초 안에는 재시도하지 않는다
    await cache.get()
    assert len(fetch.calls) == 2
    clock.t = 332
    await cache.get()
    assert len(fetch.calls) == 3


async def test_raises_when_no_stale():
    cache = ArtistsCache(make_fetch([RuntimeError("down")]))
    with pytest.raises(DataUnavailable):
        await cache.get()


async def test_invalid_payload_counts_as_failure():
    cache = ArtistsCache(make_fetch([{"artists": [{"slug": "x"}]}]))
    with pytest.raises(DataUnavailable):
        await cache.get()


async def test_http_fetcher_hits_artists_endpoint():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        return httpx.Response(200, json=MINI_RAW)

    fetch = make_http_fetcher("https://example.com", transport=httpx.MockTransport(handler))
    assert (await fetch()) == MINI_RAW
    assert seen["url"] == "https://example.com/api/artists"
