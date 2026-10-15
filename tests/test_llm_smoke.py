import pytest
from contracts.guide_events import (
    ActionEvent,
    Done,
    FocusArtist,
    GuideRequest,
    OpenTour,
    TextDelta,
    ToolStatus,
    ViewContext,
)

from tests.conftest import MINI_RAW, TODAY
from tour_guide.agent import build_agent, stream_guide
from tour_guide.data import ArtistsCache

pytestmark = [pytest.mark.llm, pytest.mark.asyncio(loop_scope="module")]

ORBIT = ViewContext(view="orbit")


def make_agent():
    async def fetch():
        return MINI_RAW

    return build_agent(ArtistsCache(fetch), lambda: TODAY, model="gpt-4.1-mini")


async def collect(message: str, locale: str, view: ViewContext | None = None):
    req = GuideRequest(requestId="t", sessionId="s", locale=locale, message=message, context=view)
    return [e async for e in stream_guide(make_agent(), req)]


def actions(events):
    return [e.action for e in events if isinstance(e, ActionEvent)]


async def test_korean_question_calls_tool_and_answers():
    events = await collect("AURORA 투어 일정 보여줘", "ko")
    tools_called = {e.tool for e in events if isinstance(e, ToolStatus)}
    assert "getArtist" in tools_called
    text = "".join(e.text for e in events if isinstance(e, TextDelta))
    assert "서울" in text or "도쿄" in text


async def test_english_question_answers_in_english():
    events = await collect("Who's playing in Seoul soon?", "en")
    assert "searchShows" in {e.tool for e in events if isinstance(e, ToolStatus)}
    text = "".join(e.text for e in events if isinstance(e, TextDelta))
    assert any(ch.isascii() and ch.isalpha() for ch in text)
    assert not any("가" <= ch <= "힣" for ch in text[:40])


async def test_show_artist_emits_focus_artist_before_done():
    events = await collect("AURORA 보여줘", "ko", ORBIT)
    assert actions(events) == [FocusArtist(slug="aurora")]
    assert isinstance(events[-1], Done) and isinstance(events[-2], ActionEvent)
    called = {e.tool for e in events if isinstance(e, ToolStatus)}
    assert not called & {"focusArtist", "openTour"}  # 액션 도구는 tool_status 로 나가지 않는다


@pytest.mark.parametrize(
    ("message", "locale"), [("AURORA 투어 열어줘", "ko"), ("Open the AURORA tour", "en")]
)
async def test_open_tour_request_emits_open_tour(message, locale):
    events = await collect(message, locale, ORBIT)
    assert actions(events) == [OpenTour(slug="aurora")]


@pytest.mark.parametrize(
    ("message", "expected"),
    [
        ("AURORA 투어 일정 알려줘", FocusArtist(slug="aurora")),
        ("AURORA 투어 일정 보여줘", OpenTour(slug="aurora")),
    ],
)
async def test_info_question_focuses_and_move_request_opens_tour(message, expected):
    events = await collect(message, "ko", ORBIT)
    assert actions(events) == [expected]


async def test_comparison_question_emits_no_action():
    events = await collect("AURORA랑 VELVET 중에 누가 먼저 서울에 와?", "ko", ORBIT)
    assert actions(events) == []
    text = "".join(e.text for e in events if isinstance(e, TextDelta))
    assert text  # 답변은 항상 표시된다


async def test_open_tour_from_other_section_scrolls_to_tour():
    view = ViewContext(view="tour", slug="aurora", section="album")
    events = await collect("AURORA 투어 일정 보여줘", "ko", view)
    assert actions(events) == [OpenTour(slug="aurora")]


async def test_open_tour_not_repeated_on_tour_section():
    view = ViewContext(view="tour", slug="aurora", section="tour")
    events = await collect("AURORA 투어 열어줘", "ko", view)
    assert actions(events) == []
