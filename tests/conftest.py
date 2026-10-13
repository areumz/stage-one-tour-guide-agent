from datetime import date

import pytest
from contracts.artists import ArtistsResponse

# 라이브 데이터와 무관한 고정 데이터. 도구·가드레일 테스트의 기대값은 이 데이터와 TODAY 기준이다.
TODAY = date(2026, 10, 13)


def _artist(slug, name, name_ko, total_cities, cities, news="참고 문구"):
    return {
        "slug": slug,
        "name": name,
        "nameKo": name_ko,
        "news": news,
        "tour": {"badge": "● World Tour 2026", "titleKo": f"{name_ko} 월드투어", "year": 2026},
        "stats": {"cities": total_cities, "countries": 3, "tracks": 2},
        "cities": [{"code": c, "name": n, "date": d} for c, n, d in cities],
        "tracks": [
            {"no": 1, "title": "Dawn Chorus", "duration": "3:42"},
            {"no": 2, "title": "Glass Tide", "duration": "4:01"},
        ],
    }


MINI_RAW = {
    "artists": [
        _artist(
            "aurora", "AURORA", "오로라", 26,
            [
                ("LA", "로스앤젤레스", "2026-08-22"),
                ("SEO", "서울", "2026-12-15"),
                ("TYO", "도쿄", "2027-01-20"),
            ],
            news="AURORA 월드투어 서울 공연 D-3",
        ),
        _artist(
            "velvet", "VELVET", "벨벳", 8,
            [("BUS", "부산", "2026-09-24"), ("SEO", "서울", "2026-11-23")],
        ),
    ]
}


@pytest.fixture
def mini_raw():
    return MINI_RAW


@pytest.fixture
def artists():
    return ArtistsResponse.model_validate(MINI_RAW).artists
