import logging
import time
from collections.abc import AsyncIterator, Callable, Sequence
from contextlib import aclosing

from contracts.guide_events import Done, ErrorEvent, GuideEvent, GuideRequest, Retract, TextDelta
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from tour_guide.data import ArtistsCache, DataUnavailable
from tour_guide.guard import Verdict, build_vocab, check_length, classify
from tour_guide.limits import RateLimiter, SessionStore
from tour_guide.settings import Settings
from tour_guide.sse import to_sse

log = logging.getLogger("tour_guide.api")

# needs_classifier: L2 가 AMBIGUOUS 로 판정해 L3 분류기가 필요한지
RunGuide = Callable[[GuideRequest, bool, Sequence[tuple[str, str]]], AsyncIterator[GuideEvent]]


def client_ip(request: Request, hops: int) -> str:
    """X-Forwarded-For 의 오른쪽에서 hops 번째 값."""
    xff = request.headers.get("x-forwarded-for")
    if xff:
        parts = [p.strip() for p in xff.split(",") if p.strip()]
        if hops >= 1 and len(parts) >= hops:
            return parts[-hops]
    return request.client.host if request.client else "unknown"


def create_app(
    *,
    settings: Settings,
    cache: ArtistsCache,
    limiter: RateLimiter,
    sessions: SessionStore,
    run_guide: RunGuide,
) -> FastAPI:
    app = FastAPI(title="tour-guide-agent")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.allowed_origins),
        allow_origin_regex=settings.allowed_origin_regex,
        allow_methods=["GET", "POST"],
        allow_headers=["content-type"],
    )

    @app.get("/health")
    async def health() -> dict:
        # 콜드 스타트 미리 깨우는 용도. 외부 호출·LLM 호출 x
        return {"status": "ok"}

    def make_events(req: GuideRequest, ip: str) -> AsyncIterator[GuideEvent]:
        async def events() -> AsyncIterator[GuideEvent]:
            if not check_length(req.message):
                yield ErrorEvent(code="too_long")
                return
            if not limiter.check(ip):
                yield ErrorEvent(code="rate_limited")
                return
            try:
                artists = await cache.get()
            except DataUnavailable:
                yield ErrorEvent(code="upstream")
                return
            # 커밋된 턴이 상한이면 에이전트·분류기를 부르지 않는다 (설계 §7.3)
            if sessions.turn_limit_reached(req.sessionId):
                yield ErrorEvent(code="session_limit")
                return
            verdict = classify(req.message, build_vocab(artists))
            if verdict is Verdict.BLOCK:
                yield ErrorEvent(code="off_topic")
                return
            # 확인과 표시 사이에 await 가 없다. 표시는 아래 finally 에서만 해제한다
            token = sessions.try_acquire(req.sessionId)
            if token is None:
                yield ErrorEvent(code="busy")
                return
            try:
                text_parts: list[str] = []
                retracted = False
                history = sessions.history(req.sessionId)
                # AMBIGUOUS 만 L3 분류기로 보낸다. 분류기는 메인 에이전트의 입력 가드레일로 돈다
                needs_classifier = verdict is Verdict.AMBIGUOUS
                async with aclosing(run_guide(req, needs_classifier, history)) as stream:
                    async for event in stream:
                        if isinstance(event, TextDelta):
                            text_parts.append(event.text)
                        elif isinstance(event, Retract):
                            retracted = True
                        elif isinstance(event, Done) and not retracted:
                            # done 을 내보내기 전에 커밋한다. 비어 있는 답변은 저장하지 않는다
                            answer = "".join(text_parts)
                            if answer:
                                sessions.commit(req.sessionId, req.message, answer)
                        yield event
            except Exception as exc:
                # 예외 메시지·트레이스백에 사용자 입력이 섞일 수 있어 타입명만 남김 (설계 §7.1)
                log.warning(
                    "guide failed requestId=%s error_type=%s", req.requestId, type(exc).__name__
                )
                yield ErrorEvent(code="upstream")
            finally:
                sessions.release(req.sessionId, token)

        return events()

    @app.post("/guide/stream")
    async def guide_stream(req: GuideRequest, request: Request) -> StreamingResponse:
        ip = client_ip(request, settings.trusted_proxy_hops)

        async def body() -> AsyncIterator[str]:
            started = time.monotonic()
            last = "none"
            async with aclosing(make_events(req, ip)) as stream:
                async for event in stream:
                    last = event.event
                    yield to_sse(event)
            # 본문은 남기지 않는다 (설계 §7.1)
            log.info(
                "guide request requestId=%s outcome=%s ms=%d",
                req.requestId,
                last,
                (time.monotonic() - started) * 1000,
            )

        return StreamingResponse(
            body(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    return app
