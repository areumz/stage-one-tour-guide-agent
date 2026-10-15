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


async def test_history_is_sent_as_message_list_before_current_question(monkeypatch):
    seen = _capture(monkeypatch, FakeResult([_text_ev("네")]))
    history = [("AURORA 공연 언제야?", "12월 서울이에요."), ("그리고?", "1월 도쿄예요.")]
    [e async for e in stream_guide(object(), _req(), history=history)]
    assert seen["input"] == [
        {"role": "user", "content": "AURORA 공연 언제야?"},
        {"role": "assistant", "content": "12월 서울이에요."},
        {"role": "user", "content": "그리고?"},
        {"role": "assistant", "content": "1월 도쿄예요."},
        {"role": "user", "content": "그럼 거기는?"},
    ]
    assert seen["context"].prev_question == "그리고?"


async def test_no_history_keeps_plain_string_input(monkeypatch):
    seen = _capture(monkeypatch, FakeResult([_text_ev("네")]))
    [e async for e in stream_guide(object(), _req("안녕"))]
    assert seen["input"] == "안녕"
    assert seen["context"].prev_question is None


async def test_output_check_allows_cities_from_history(monkeypatch):
    _capture(monkeypatch, FakeResult([_text_ev("도쿄 공연은 1월이에요.")]))
    history = [("AURORA 투어 도시?", "Tokyo, Seoul 공연이 있어요.")]
    events = [e async for e in stream_guide(object(), _req("거기 언제야?"), history=history)]
    assert events == [TextDelta(text="도쿄 공연은 1월이에요."), Done()]


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
