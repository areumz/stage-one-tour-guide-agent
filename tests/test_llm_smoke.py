import pytest
from contracts.guide_events import GuideRequest, TextDelta, ToolStatus

from tests.conftest import MINI_RAW, TODAY
from tour_guide.agent import build_agent, stream_guide
from tour_guide.data import ArtistsCache

pytestmark = [pytest.mark.llm, pytest.mark.asyncio(loop_scope="module")]


def make_agent():
    async def fetch():
        return MINI_RAW

    return build_agent(ArtistsCache(fetch), lambda: TODAY, model="gpt-4.1-mini")


async def collect(message: str, locale: str):
    req = GuideRequest(requestId="t", sessionId="s", locale=locale, message=message)
    return [e async for e in stream_guide(make_agent(), req)]


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
