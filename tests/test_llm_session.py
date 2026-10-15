"""실제 모델로 히스토리 후속 질문을 확인한다 (llm 마커, 기본 제외)."""

import pytest
from contracts.guide_events import (
    ActionEvent,
    Done,
    GuideRequest,
    HighlightCity,
    Retract,
    TextDelta,
    ToolStatus,
    ViewContext,
)

from tests.conftest import MINI_RAW, TODAY
from tour_guide.agent import build_agent, stream_guide
from tour_guide.data import ArtistsCache

pytestmark = [pytest.mark.llm, pytest.mark.asyncio(loop_scope="module")]
RUNS = 3


def _agent():
    async def fetch():
        return MINI_RAW

    return build_agent(ArtistsCache(fetch), lambda: TODAY, model="gpt-4.1-mini")


async def _ask(message, history, view=None, locale="ko"):
    req = GuideRequest(requestId="t", sessionId="s", locale=locale, message=message, context=view)
    return [e async for e in stream_guide(_agent(), req, history=history)]


async def test_follow_up_uses_previous_turn_without_retract():
    history = [("AURORA 공연 도시 알려줘", "AURORA는 로스앤젤레스, 서울, 도쿄에서 공연해요.")]
    good = 0
    for _ in range(RUNS):
        events = await _ask("그중에 제일 먼저 하는 곳은?", history)
        text = "".join(e.text for e in events if isinstance(e, TextDelta))
        good += isinstance(events[-1], Done) and not any(isinstance(e, Retract) for e in events) and bool(text)
    assert good >= 2


async def test_english_follow_up_answers_in_english():
    history = [("Where does AURORA play?", "AURORA plays Seoul and Tokyo.")]
    good = 0
    for _ in range(RUNS):
        events = await _ask("Which one is first?", history, locale="en")
        text = "".join(e.text for e in events if isinstance(e, TextDelta))
        good += bool(text) and not any("가" <= ch <= "힣" for ch in text[:40])
    assert good >= 2


TOUR = ViewContext(view="tour", slug="aurora")


async def test_city_question_on_tour_page_emits_highlight_city():
    good = 0
    for _ in range(RUNS):
        events = await _ask("도쿄 공연은 언제 해?", [], view=TOUR)
        actions = [e.action for e in events if isinstance(e, ActionEvent)]
        good += actions == [HighlightCity(slug="aurora", city="TYO")] and isinstance(events[-1], Done)
    assert good >= 2


async def test_city_question_in_orbit_never_emits_highlight_city():
    for _ in range(RUNS):
        events = await _ask("AURORA 도쿄 공연은 언제 해?", [], view=ViewContext(view="orbit"))
        assert not any(
            isinstance(e, ActionEvent) and isinstance(e.action, HighlightCity) for e in events
        )


async def test_follow_up_looks_up_data_instead_of_repeating_invented_dates():
    """이전 답에 도구 없이 쓴 날짜가 있어도, 후속 질문은 도구로 다시 조회해 실제 날짜로 답한다."""
    history = [
        ("AURORA 투어 일정 보여줘", "오로라 투어 페이지를 열었습니다. 궁금한 도시 일정이 있으면 알려주세요."),
        ("LA 공연 언제해?", "오로라의 LA 공연은 2027년 1월 10일입니다."),  # 도구 없이 지어낸 날짜
    ]
    good = 0
    for _ in range(RUNS):
        events = await _ask("서울 공연은?", history, view=ViewContext(view="tour", slug="aurora"))
        text = "".join(e.text for e in events if isinstance(e, TextDelta))
        looked_up = any(isinstance(e, ToolStatus) for e in events)
        real_date = "12월 15일" in text or "2026-12-15" in text
        clean = not any(isinstance(e, Retract) for e in events) and "2027" not in text
        good += looked_up and real_date and clean
    assert good >= 2
