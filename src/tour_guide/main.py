import logging

from agents import set_tracing_disabled
from fastapi import FastAPI

from tour_guide.agent import build_agent, stream_guide
from tour_guide.api import create_app
from tour_guide.clock import today_kst
from tour_guide.data import ArtistsCache, make_http_fetcher
from tour_guide.limits import RateLimiter
from tour_guide.settings import Settings


def _configure_logging() -> None:
    # uvicorn 은 자기 로거만 설정함. 앱 로거(tour_guide.*)는 여기서 직접 INFO 로 오픈
    pkg = logging.getLogger("tour_guide")
    pkg.setLevel(logging.INFO)
    if not pkg.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
        pkg.addHandler(handler)


def build_app() -> FastAPI:
    _configure_logging()
    settings = Settings.from_env()
    # 운영 트레이싱 off
    set_tracing_disabled(not settings.tracing_enabled)
    cache = ArtistsCache(make_http_fetcher(settings.onstage_url))
    limiter = RateLimiter(settings.rate_per_minute, settings.rate_per_ip_daily, settings.global_daily)
    agent = build_agent(
        cache,
        today_kst,
        settings.openai_model,
        temperature=settings.openai_temperature,
        classifier_model=settings.classifier_model,
    )
    return create_app(
        settings=settings,
        cache=cache,
        limiter=limiter,
        run_guide=lambda req, needs_classifier=False: stream_guide(
            agent, req, cache, needs_classifier=needs_classifier
        ),
    )
