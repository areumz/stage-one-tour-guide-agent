import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import date

import httpx
from contracts.artists import Artist, ArtistsResponse

RETRY_AFTER_FAILURE_SECONDS = 30.0

Fetcher = Callable[[], Awaitable[dict]]


class DataUnavailable(RuntimeError):
    """on-stage 데이터를 가져올 수 없고 캐시도 없다."""


@dataclass(frozen=True)
class Show:
    artist_slug: str
    city_code: str
    city_name: str
    date: date


def load_shows(artist: Artist) -> list[Show]:
    """공연 목록의 단일 진입점 (설계 §5, §12 #11).

    지금은 cities[] (featured 공연)에서 채운다. on-stage 에 전체 공연 GET 이 생기면
    계약 갱신 후 이 함수만 바꾼다.
    """
    return [Show(artist.slug, c.code, c.name, c.date) for c in artist.cities]


def slug_set(artists: list[Artist]) -> frozenset[str]:
    return frozenset(a.slug for a in artists)


def city_names(artists: list[Artist]) -> dict[str, str]:
    """도시 code → 한국어 이름."""
    return {s.city_code: s.city_name for a in artists for s in load_shows(a)}


def make_http_fetcher(
    base_url: str,
    timeout: float = 5.0,
    transport: httpx.AsyncBaseTransport | None = None,
) -> Fetcher:
    async def fetch() -> dict:
        async with httpx.AsyncClient(timeout=timeout, transport=transport) as client:
            resp = await client.get(f"{base_url}/api/artists")
            resp.raise_for_status()
            return resp.json()

    return fetch


class ArtistsCache:
    """5분 TTL 메모리 캐시. 실패하면 마지막 값을 쓰고 30초 뒤 다시 시도한다."""

    def __init__(
        self,
        fetch: Fetcher,
        ttl_seconds: float = 300.0,
        clock: Callable[[], float] = time.monotonic,
    ):
        self._fetch = fetch
        self._ttl = ttl_seconds
        self._clock = clock
        self._value: list[Artist] | None = None
        self._at = 0.0

    async def get(self) -> list[Artist]:
        now = self._clock()
        if self._value is not None and now - self._at < self._ttl:
            return self._value
        try:
            raw = await self._fetch()
            self._value = ArtistsResponse.model_validate(raw).artists
            self._at = now
        except Exception as exc:
            if self._value is None:
                raise DataUnavailable("on-stage /api/artists 를 읽을 수 없다") from exc
            self._at = now - self._ttl + RETRY_AFTER_FAILURE_SECONDS
        return self._value
