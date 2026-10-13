import json
from pathlib import Path

import pytest
from contracts.guide_events import (
    ActionEvent,
    Done,
    ErrorEvent,
    GuideRequest,
    Retract,
    TextDelta,
    ToolStatus,
    parse_event,
)
from pydantic import ValidationError

SAMPLE = Path(__file__).resolve().parents[2] / "contracts" / "fixtures" / "guide_events_sample.json"


def _parse_stream(name):
    samples = json.loads(SAMPLE.read_text(encoding="utf-8"))[name]
    return [parse_event(s["event"], s["data"]) for s in samples]


def test_success_stream_ends_with_done():
    parsed = _parse_stream("success")
    assert [type(p) for p in parsed] == [ToolStatus, TextDelta, ActionEvent, Done]
    assert not any(isinstance(p, ErrorEvent) for p in parsed)
    assert parsed[2].action.type == "focusArtist"


def test_error_stream_ends_with_error_and_no_done():
    parsed = _parse_stream("error")
    assert isinstance(parsed[-1], ErrorEvent)
    assert not any(isinstance(p, Done) for p in parsed)


def test_retract_parses():
    assert parse_event("retract", {"reason": "off_topic"}) == Retract(reason="off_topic")


def test_open_tour_parses_with_and_without_section():
    assert parse_event("action", {"type": "openTour", "slug": "aurora"}).action.section is None
    assert parse_event("action", {"type": "openTour", "slug": "aurora", "section": "news"}).action.section == "news"


def test_highlight_city_parses():
    a = parse_event("action", {"type": "highlightCity", "slug": "aurora", "city": "TYO"}).action
    assert (a.type, a.city) == ("highlightCity", "TYO")


def test_invalid_error_code_rejected():
    with pytest.raises(ValidationError):
        parse_event("error", {"code": "x"})


GOOD_IDS = ["r1", "123e4567-e89b-12d3-a456-426614174000", "a_b-C", "a" * 64]
BAD_IDS = ["a\nb", "a b", "a.b", "아이디", "", "a" * 65]


@pytest.mark.parametrize("field", ["requestId", "sessionId"])
def test_id_pattern(field):
    base = {"requestId": "r1", "sessionId": "s1", "locale": "ko", "message": "x"}
    for good in GOOD_IDS:
        GuideRequest(**{**base, field: good})
    for bad in BAD_IDS:
        with pytest.raises(ValidationError):
            GuideRequest(**{**base, field: bad})


def test_unknown_event_name_rejected():
    with pytest.raises(ValueError):
        parse_event("nope", {})


def test_request_strips_and_validates():
    r = GuideRequest(requestId="r1", sessionId="s1", locale="ko", message="  안녕  ")
    assert r.message == "안녕"
    with pytest.raises(ValidationError):
        GuideRequest(requestId="r1", sessionId="s1", locale="jp", message="x")
    with pytest.raises(ValidationError):
        GuideRequest(requestId="r1", sessionId="s1", locale="ko", message="   ")


def test_unknown_action_type_rejected():
    with pytest.raises(ValidationError):
        parse_event("action", {"type": "teleport", "slug": "aurora"})
