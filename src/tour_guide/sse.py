import json

from contracts.guide_events import ActionEvent, GuideEvent


def to_sse(event: GuideEvent) -> str:
    """계약 이벤트 SSE 프레임 -> 문자열"""
    if isinstance(event, ActionEvent):
        payload = event.action.model_dump(exclude_none=True)
    else:
        payload = event.model_dump(exclude={"event"})
    return f"event: {event.event}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"
