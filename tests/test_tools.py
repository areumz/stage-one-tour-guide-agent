import json
from pathlib import Path

import pytest
from contracts.artists import ArtistsResponse

from tests.conftest import TODAY
from tour_guide.tools import ToolInputError, get_artist, list_artists, search_shows

GOLDEN = Path(__file__).resolve().parents[1] / "contracts" / "fixtures" / "artists_response.json"


def test_list_artists_next_show(artists):
    result = {a["slug"]: a for a in list_artists(artists, TODAY)}
    aurora = result["aurora"]
    assert aurora["tourTitle"] == "오로라 월드투어"
    # LA(2026-08-22)는 지났으므로 다음 공연은 서울 2026-12-15
    assert aurora["nextShow"]["cityCode"] == "SEO"
    assert aurora["nextShow"]["daysUntil"] == 63
    assert result["velvet"]["nextShow"]["date"] == "2026-11-23"
    assert result["velvet"]["nextShow"]["daysUntil"] == 41


def test_list_artists_no_upcoming(artists):
    far = TODAY.replace(year=2030)
    assert all(a["nextShow"] is None for a in list_artists(artists, far))


def test_get_artist_uses_stats_for_total_and_cities_for_list(artists):
    r = get_artist(artists, "aurora", TODAY)
    assert r["totalCities"] == 26
    assert [c["cityCode"] for c in r["featuredCities"]] == ["LA", "SEO", "TYO"]
    assert r["featuredCities"][0]["daysUntil"] < 0  # 지난 공연은 음수
    assert r["totalTracks"] == 2  # stats.tracks
    assert r["featuredTracks"] == ["Dawn Chorus", "Glass Tide"]


def test_get_artist_total_tracks_differs_from_listed_tracks_in_real_response():
    raw = json.loads(GOLDEN.read_text(encoding="utf-8"))
    real = ArtistsResponse.model_validate(raw).artists
    r = get_artist(real, "aurora", TODAY)
    assert r["totalTracks"] == 8
    assert len(r["featuredTracks"]) == 4
    assert "tracks" not in r  # 목록은 "대표 곡"이라는 이름으로만 노출한다


def test_get_artist_unknown_slug(artists):
    with pytest.raises(ToolInputError):
        get_artist(artists, "nobody", TODAY)


def test_search_by_city_sorted_by_date(artists):
    r = search_shows(artists, TODAY, city="SEO")
    assert [(s["artistSlug"], s["date"]) for s in r] == [
        ("velvet", "2026-11-23"),
        ("aurora", "2026-12-15"),
    ]


def test_search_month_and_artist_filters(artists):
    assert [s["cityCode"] for s in search_shows(artists, TODAY, month=1)] == ["TYO"]
    assert search_shows(artists, TODAY, artist="velvet", city="SEO")[0]["artistSlug"] == "velvet"
    assert search_shows(artists, TODAY, artist="aurora", city="BUS") == []


def test_search_upcoming_only_flag(artists):
    past = search_shows(artists, TODAY, month=9, upcoming_only=False)
    assert [s["cityCode"] for s in past] == ["BUS"]
    assert search_shows(artists, TODAY, month=9) == []


def test_search_validates_inputs(artists):
    with pytest.raises(ToolInputError):
        search_shows(artists, TODAY, city="XXX")
    with pytest.raises(ToolInputError):
        search_shows(artists, TODAY, month=13)
    with pytest.raises(ToolInputError):
        search_shows(artists, TODAY, artist="nobody")
