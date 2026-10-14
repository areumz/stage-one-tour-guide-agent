"""[요구사항] POST /guide/stream 의 요청·SSE 이벤트·UI 액션. 설계 문서 §4.

이 모듈이 계약의 소유자다. on-stage 는 fixtures/guide_events_sample.json 에 맞춰 zod 를 쓴다.
`error` 는 종료 이벤트이고 `done` 은 정상 종료에만 보낸다.
"""

from typing import Annotated, Literal

from pydantic import BaseModel, Field, StringConstraints

MAX_MESSAGE_CHARS = 200
# 영숫자, -, _ 만 허용 (클라이언트 UUID 형식). 로그 주입(개행 등)을 막는다.
ID_PATTERN = r"^[A-Za-z0-9_-]{1,64}$"

Locale = Literal["ko", "en"]
ErrorCode = Literal["rate_limited", "off_topic", "too_long", "busy", "upstream", "internal"]


class ViewContext(BaseModel):
    view: Literal["orbit", "tour"]
    slug: str | None = None


class GuideRequest(BaseModel):
    requestId: Annotated[str, StringConstraints(pattern=ID_PATTERN)]
    sessionId: Annotated[str, StringConstraints(pattern=ID_PATTERN)]
    locale: Locale
    # 길이 상한(200자)은 모델이 아니라 L0 가 검사해 `too_long` 이벤트로 알림. 여기서는 본문 폭주만 막음.
    message: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]
    context: ViewContext | None = None


# ── UI 액션 ──


class FocusArtist(BaseModel):
    type: Literal["focusArtist"] = "focusArtist"
    slug: str


class OpenTour(BaseModel):
    type: Literal["openTour"] = "openTour"
    slug: str
    section: str | None = None


class HighlightCity(BaseModel):
    type: Literal["highlightCity"] = "highlightCity"
    slug: str
    city: str


UiAction = Annotated[FocusArtist | OpenTour | HighlightCity, Field(discriminator="type")]


# ── SSE 이벤트 ──


class ToolStatus(BaseModel):
    event: Literal["tool_status"] = "tool_status"
    tool: str
    key: str


class TextDelta(BaseModel):
    event: Literal["text_delta"] = "text_delta"
    text: str


class ActionEvent(BaseModel):
    event: Literal["action"] = "action"
    action: UiAction


class Retract(BaseModel):
    event: Literal["retract"] = "retract"
    reason: str


class ErrorEvent(BaseModel):
    event: Literal["error"] = "error"
    code: ErrorCode


class Done(BaseModel):
    event: Literal["done"] = "done"


GuideEvent = ToolStatus | TextDelta | ActionEvent | Retract | ErrorEvent | Done

_PLAIN = {
    "tool_status": ToolStatus,
    "text_delta": TextDelta,
    "retract": Retract,
    "error": ErrorEvent,
    "done": Done,
}


def parse_event(name: str, data: dict) -> GuideEvent:
    """SSE 의 (event 이름, data) 쌍을 모델로 되돌린다. fixture 검증용."""
    if name == "action":
        return ActionEvent.model_validate({"action": data})
    if name not in _PLAIN:
        raise ValueError(f"unknown event: {name}")
    return _PLAIN[name].model_validate({"event": name, **data})
