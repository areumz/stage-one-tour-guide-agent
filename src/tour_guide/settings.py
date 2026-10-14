import os
from collections.abc import Mapping
from dataclasses import dataclass


def _int_env(e: Mapping[str, str], name: str, default: str) -> int:
    value = e.get(name, default)
    try:
        return int(value)
    except ValueError:
        raise ValueError(f"{name} 는 정수여야 한다: {value!r}") from None


@dataclass(frozen=True)
class Settings:
    onstage_url: str
    allowed_origins: tuple[str, ...] = ("http://localhost:3000",)
    allowed_origin_regex: str | None = None
    openai_model: str = "gpt-4.1-mini"
    # 임시로 정해둠. 배포 단계에서 확인 후 변경 할 수 있음
    trusted_proxy_hops: int = 1
    rate_per_minute: int = 5
    rate_per_ip_daily: int = 30
    global_daily: int = 1000
    tracing_enabled: bool = False

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "Settings":
        e = os.environ if env is None else env
        origins = tuple(
            o.strip() for o in e.get("ALLOWED_ORIGINS", "http://localhost:3000").split(",") if o.strip()
        )
        if "*" in origins:
            raise ValueError("ALLOWED_ORIGINS 에 와일드카드(*)는 쓸 수 없다")
        onstage_url = e.get("ONSTAGE_URL", "").strip()
        if not onstage_url:
            raise ValueError("ONSTAGE_URL 환경 변수가 필요하다 (예: https://on-stage-nine.vercel.app)")
        return cls(
            onstage_url=onstage_url.rstrip("/"),
            allowed_origins=origins,
            allowed_origin_regex=e.get("ALLOWED_ORIGIN_REGEX") or None,
            openai_model=e.get("OPENAI_MODEL", "gpt-4.1-mini"),
            trusted_proxy_hops=_int_env(e, "TRUSTED_PROXY_HOPS", "1"),
            rate_per_minute=_int_env(e, "RATE_PER_MINUTE", "5"),
            rate_per_ip_daily=_int_env(e, "RATE_PER_IP_DAILY", "30"),
            global_daily=_int_env(e, "GLOBAL_DAILY", "1000"),
            tracing_enabled=e.get("TRACING_ENABLED", "").lower() in ("1", "true", "yes"),
        )
