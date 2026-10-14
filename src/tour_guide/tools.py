"""읽기 전용 도구의 순수 함수. SDK 래퍼는 agent.py (설계 §5)."""

from datetime import date

from contracts.artists import Artist

from tour_guide.data import Show, city_names, load_shows, slug_set


class ToolInputError(ValueError):
    """도구 입력이 enum 밖. 오류 반환"""


def _show_dict(artist: Artist, show: Show, today: date) -> dict:
    return {
        "artistSlug": artist.slug,
        "artistName": artist.name,
        "cityCode": show.city_code,
        "cityName": show.city_name,
        "date": show.date.isoformat(),
        "daysUntil": (show.date - today).days,
    }


def _find(artists: list[Artist], slug: str) -> Artist:
    for a in artists:
        if a.slug == slug:
            return a
    raise ToolInputError(f"unknown artist slug: {slug}")


def list_artists(artists: list[Artist], today: date) -> list[dict]:
    out = []
    for a in artists:
        upcoming = sorted((s for s in load_shows(a) if s.date >= today), key=lambda s: s.date)
        out.append(
            {
                "slug": a.slug,
                "name": a.name,
                "nameKo": a.nameKo,
                "tourTitle": a.tour.titleKo,
                "nextShow": _show_dict(a, upcoming[0], today) if upcoming else None,
            }
        )
    return out


def get_artist(artists: list[Artist], slug: str, today: date) -> dict:
    a = _find(artists, slug)
    shows = sorted(load_shows(a), key=lambda s: s.date)
    return {
        "slug": a.slug,
        "name": a.name,
        "nameKo": a.nameKo,
        "tourTitle": a.tour.titleKo,
        # 설계 §5: 도시 수는 stats.cities, 목록은 대표 도시(cities[])
        "totalCities": a.stats.cities,
        "countries": a.stats.countries,
        "featuredCities": [_show_dict(a, s, today) for s in shows],
        "tracks": [t.title for t in a.tracks],
        "news": a.news,
    }


def search_shows(
    artists: list[Artist],
    today: date,
    *,
    city: str | None = None,
    month: int | None = None,
    artist: str | None = None,
    upcoming_only: bool = True,
) -> list[dict]:
    if city is not None and city not in city_names(artists):
        raise ToolInputError(f"unknown city code: {city}")
    if month is not None and not 1 <= month <= 12:
        raise ToolInputError(f"month must be 1-12: {month}")
    if artist is not None and artist not in slug_set(artists):
        raise ToolInputError(f"unknown artist slug: {artist}")

    hits = []
    for a in artists:
        if artist is not None and a.slug != artist:
            continue
        for s in load_shows(a):
            if city is not None and s.city_code != city:
                continue
            if month is not None and s.date.month != month:
                continue
            if upcoming_only and s.date < today:
                continue
            hits.append((s.date, a, s))
    hits.sort(key=lambda h: (h[0], h[1].slug))
    return [_show_dict(a, s, today) for _, a, s in hits]
