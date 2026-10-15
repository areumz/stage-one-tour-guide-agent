import logging
import time
from collections.abc import AsyncIterator, Callable
from contextlib import aclosing

from contracts.guide_events import ErrorEvent, GuideEvent, GuideRequest
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from tour_guide.data import ArtistsCache, DataUnavailable
from tour_guide.guard import Verdict, build_vocab, check_length, classify
from tour_guide.limits import RateLimiter
from tour_guide.settings import Settings
from tour_guide.sse import to_sse

log = logging.getLogger("tour_guide.api")

# needs_classifier: L2 가 AMBIGUOUS 로 판정해 L3 분류기가 필요한지
RunGuide = Callable[[GuideRequest, bool], AsyncIterator[GuideEvent]]


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

    @app.post("/guide/stream")
    async def guide_stream(req: GuideRequest, request: Request) -> StreamingResponse:
        ip = client_ip(request, settings.trusted_proxy_hops)

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
            verdict = classify(req.message, build_vocab(artists))
            if verdict is Verdict.BLOCK:
                yield ErrorEvent(code="off_topic")
                return
            # AMBIGUOUS 만 L3 분류기로 보낸다. 분류기는 메인 에이전트의 입력 가드레일로 돈다
            needs_classifier = verdict is Verdict.AMBIGUOUS
            try:
                async with aclosing(run_guide(req, needs_classifier)) as stream:
                    async for event in stream:
                        yield event
            except Exception as exc:
                # 예외 메시지·트레이스백에 사용자 입력이 섞일 수 있어 타입명만 남김 (설계 §7.1)
                log.warning(
                    "guide failed requestId=%s error_type=%s", req.requestId, type(exc).__name__
                )
                yield ErrorEvent(code="upstream")

        async def body() -> AsyncIterator[str]:
            started = time.monotonic()
            last = "none"
            async with aclosing(events()) as stream:
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
