"""L3 분류기 가드레일 (LLM 없음). 메인 모델은 호출 횟수를 세는 가짜다."""

import logging

import pytest
from agents import Model
from contracts.guide_events import Done, ErrorEvent, GuideRequest
from openai.types.responses import (
    Response,
    ResponseCompletedEvent,
    ResponseOutputMessage,
    ResponseOutputText,
)

from tests.conftest import MINI_RAW, TODAY
from tour_guide.agent import build_agent, stream_guide
from tour_guide.classifier import ClassifierResult
from tour_guide.data import ArtistsCache


class FakeMain(Model):
    def __init__(self):
        self.calls = 0

    async def get_response(self, *a, **k):
        raise AssertionError("streaming only")

    async def stream_response(self, *a, **k):
        self.calls += 1
        msg = ResponseOutputMessage(
            id="m1",
            type="message",
            role="assistant",
            status="completed",
            content=[ResponseOutputText(type="output_text", text="안녕하세요", annotations=[])],
        )
        yield ResponseCompletedEvent(
            type="response.completed",
            sequence_number=0,
            response=Response(
                id="r1",
                created_at=0,
                model="fake",
                object="response",
                output=[msg],
                parallel_tool_calls=False,
                tool_choice="auto",
                tools=[],
            ),
        )


def _setup(classify_fn):
    async def fetch():
        return MINI_RAW

    main = FakeMain()
    agent = build_agent(ArtistsCache(fetch), lambda: TODAY, model=main, classify_fn=classify_fn)
    return agent, main


def _req():
    return GuideRequest(requestId="r1", sessionId="s1", locale="ko", message="비밀질문본문")


async def _run(agent, needs):
    return [e async for e in stream_guide(agent, _req(), needs_classifier=needs)]


async def test_flag_off_never_calls_classifier():
    calls = []

    async def classify(msg):
        calls.append(msg)
        return ClassifierResult("block", "off_topic")

    agent, main = _setup(classify)
    events = await _run(agent, False)
    assert calls == [] and main.calls == 1
    assert events[-1] == Done()


async def test_block_yields_only_off_topic_and_zero_main_calls():
    async def classify(msg):
        return ClassifierResult("block", "off_topic", 300, 10)

    agent, main = _setup(classify)
    events = await _run(agent, True)
    assert events == [ErrorEvent(code="off_topic")]
    assert main.calls == 0


async def test_allow_runs_main_normally_and_logs_without_body(caplog):
    caplog.set_level(logging.INFO)

    async def classify(msg):
        return ClassifierResult("allow", "off_topic", 300, 10)

    agent, main = _setup(classify)
    events = await _run(agent, True)
    assert main.calls == 1
    assert events == [Done()]
    text = "\n".join(r.getMessage() for r in caplog.records)
    assert "input_tokens=300" in text and "비밀질문본문" not in text


async def test_classifier_error_propagates_for_upstream():
    async def classify(msg):
        raise TimeoutError

    agent, main = _setup(classify)
    with pytest.raises(TimeoutError):
        await _run(agent, True)
    assert main.calls == 0
