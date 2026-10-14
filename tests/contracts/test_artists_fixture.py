import json
from pathlib import Path

from contracts.artists import ArtistsResponse

FIXTURE = Path(__file__).resolve().parents[2] / "contracts" / "fixtures" / "artists_response.json"


def test_golden_response_parses():
    raw = json.loads(FIXTURE.read_text(encoding="utf-8"))
    parsed = ArtistsResponse.model_validate(raw)
    assert len(parsed.artists) >= 1
    for a in parsed.artists:
        assert a.slug
        assert a.stats.cities >= len(a.cities)
