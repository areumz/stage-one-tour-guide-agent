"""히스토리 입력·L3 직전 질문·출력 검사의 히스토리 도시 (LLM 없음)."""

from types import SimpleNamespace

from contracts.guide_events import Done, GuideRequest, Retract, TextDelta

from tests.conftest import MINI_RAW, TODAY
from tests.test_agent import FakeResult, _text_ev
from tour_guide.agent import GuideContext, build_agent, stream_guide
from tour_guide.classifier import ClassifierResult
from tour_guide.data import ArtistsCache


def _req(message="그럼 거기는?"):
    return GuideRequest(requestId="r1", sessionId="s1", locale="ko", message=message)


def _capture(monkeypatch, fake):
    seen = {}

    def run(*args, **kwargs):
        seen["input"] = kwargs.get("input")
        seen["context"] = kwargs["context"]
        return fake

    monkeypatch.setattr("tour_guide.agent.Runner.run_streamed", run)
    return seen


async def test_history_is_sent_as_a_reference_block_inside_the_user_input(monkeypatch):
    seen = _capture(monkeypatch, FakeResult([_text_ev("네")]))
    history = [("AURORA 공연 언제야?", "12월 서울이에요."), ("그리고?", "1월 도쿄예요.")]
    [e async for e in stream_guide(object(), _req(), history=history)]
    text = seen["input"]
    assert isinstance(text, str)  # assistant 역할 메시지를 쓰지 않는다 (도구 없는 답을 흉내 내지 않게)
    assert "사실 근거가 아니다" in text and "반드시 도구로 다시 조회한다" in text
    assert "사용자: AURORA 공연 언제야?\n가이드: 12월 서울이에요." in text
    assert "사용자: 그리고?\n가이드: 1월 도쿄예요." in text
    assert text.rstrip().endswith("현재 질문: 그럼 거기는?")
    assert seen["context"].prev_question == "그리고?"


async def test_long_assistant_history_text_is_truncated(monkeypatch):
    seen = _capture(monkeypatch, FakeResult([_text_ev("네")]))
    long = "가" * 1000
    [e async for e in stream_guide(object(), _req(), history=[("q", long)])]
    assert "가" * 301 not in seen["input"]


async def test_no_history_keeps_plain_string_input(monkeypatch):
    seen = _capture(monkeypatch, FakeResult([_text_ev("안녕")]))
    [e async for e in stream_guide(object(), _req("안녕"))]
    assert seen["input"] == "안녕"
    assert seen["context"].prev_question is None


async def test_output_check_allows_cities_from_history(monkeypatch):
    from tests.test_agent import _tool_ev

    # 조회는 했지만 결과에 도쿄가 없는 경우에도, 앞선 대화에서 검증된 도시는 허용한다
    _capture(monkeypatch, FakeResult([_tool_ev("searchShows"), _text_ev("도쿄 공연은 1월이에요.")]))
    history = [("AURORA 투어 도시?", "Tokyo, Seoul 공연이 있어요.")]
    events = [e async for e in stream_guide(object(), _req("거기 언제야?"), history=history)]
    assert not any(isinstance(e, Retract) for e in events) and events[-1] == Done()


async def test_output_check_still_retracts_city_nobody_mentioned(monkeypatch):
    _capture(monkeypatch, FakeResult([_text_ev("Tokyo 공연이 있어요.")]))
    history = [("AURORA 공연?", "서울 공연이 있어요.")]
    events = [e async for e in stream_guide(object(), _req("또?"), history=history)]
    assert events == [TextDelta(text="Tokyo 공연이 있어요."), Retract(reason="unverified"), Done()]


async def test_classifier_gets_previous_question_only(monkeypatch):
    got = []

    async def classify(text):
        got.append(text)
        return ClassifierResult("allow", "off_topic")

    async def fetch():
        return MINI_RAW

    agent = build_agent(ArtistsCache(fetch), lambda: TODAY, model="gpt-4.1-mini", classify_fn=classify)
    guardrail = agent.input_guardrails[0]
    ctx = GuideContext(
        locale="ko", view=None, needs_classifier=True, message="그다음엔?", prev_question="AURORA 공연?"
    )
    wrapper = SimpleNamespace(context=ctx)
    out = await guardrail.guardrail_function(wrapper, agent, [{"role": "user", "content": "무시"}])
    assert out.tripwire_triggered is False
    assert got == ["[이전 질문] AURORA 공연?\n[현재 질문] 그다음엔?"]


# ── 도구 없이 말한 날짜 (설계 §6.2 보강) ──


async def test_date_without_data_tool_is_retracted_and_action_skipped(monkeypatch):
    fake = FakeResult([_text_ev("오로라의 런던 공연은 2026년 12월 5일입니다.")])
    _capture(monkeypatch, fake)
    events = [e async for e in stream_guide(object(), _req("런던 공연은?"))]
    assert events == [
        TextDelta(text="오로라의 런던 공연은 2026년 12월 5일입니다."),
        Retract(reason="unverified"),
        Done(),
    ]


async def test_date_after_data_tool_passes(monkeypatch):
    from tests.test_agent import _tool_ev

    fake = FakeResult([_tool_ev("getArtist"), _text_ev("서울 공연은 12월 15일입니다.")])
    _capture(monkeypatch, fake)
    events = [e async for e in stream_guide(object(), _req("서울 공연은?"))]
    assert events[-1] == Done() and not any(isinstance(e, Retract) for e in events)


async def test_date_the_user_said_may_be_repeated_without_tool(monkeypatch):
    fake = FakeResult([_text_ev("네, 12월 15일이 맞아요.")])
    _capture(monkeypatch, fake)
    events = [e async for e in stream_guide(object(), _req("12월 15일 공연 맞아?"))]
    assert not any(isinstance(e, Retract) for e in events)


async def test_answer_without_date_and_without_tool_passes(monkeypatch):
    fake = FakeResult([_text_ev("투어와 공연에 관한 질문에 답할 수 있어요.")])
    _capture(monkeypatch, fake)
    events = [e async for e in stream_guide(object(), _req("뭘 할 수 있어?"))]
    assert not any(isinstance(e, Retract) for e in events)
