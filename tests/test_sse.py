import json

from contracts.guide_events import ActionEvent, Done, ErrorEvent, TextDelta, ToolStatus

from tour_guide.sse import to_sse


def parse(frame: str):
    lines = frame.strip().split("\n")
    assert lines[0].startswith("event: ") and lines[1].startswith("data: ")
    assert frame.endswith("\n\n")
    return lines[0][7:], json.loads(lines[1][6:])


def test_text_delta_keeps_korean_unescaped():
    frame = to_sse(TextDelta(text="안녕"))
    assert "안녕" in frame
    assert parse(frame) == ("text_delta", {"text": "안녕"})


def test_other_events():
    assert parse(to_sse(ToolStatus(tool="searchShows", key="tool.searchShows"))) == (
        "tool_status",
        {"tool": "searchShows", "key": "tool.searchShows"},
    )
    assert parse(to_sse(ErrorEvent(code="off_topic"))) == ("error", {"code": "off_topic"})
    assert parse(to_sse(Done())) == ("done", {})


def test_action_is_flattened():
    ev = ActionEvent(action={"type": "openTour", "slug": "aurora"})
    assert parse(to_sse(ev)) == ("action", {"type": "openTour", "slug": "aurora"})
