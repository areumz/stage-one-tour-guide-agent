import pytest

from tour_guide.settings import Settings


def test_defaults_and_trailing_slash_removed():
    s = Settings.from_env({"ONSTAGE_URL": "https://example.com/"})
    assert s.onstage_url == "https://example.com"
    assert s.allowed_origins == ("http://localhost:3000",)
    assert s.allowed_origin_regex is None
    assert s.trusted_proxy_hops == 1
    assert (s.rate_per_minute, s.rate_per_ip_daily, s.global_daily) == (5, 30, 1000)
    assert s.tracing_enabled is False


def test_overrides():
    s = Settings.from_env(
        {
            "ONSTAGE_URL": "https://example.com",
            "ALLOWED_ORIGINS": "https://a.app, https://b.app",
            "RATE_PER_MINUTE": "2",
            "TRACING_ENABLED": "true",
        }
    )
    assert s.allowed_origins == ("https://a.app", "https://b.app")
    assert s.rate_per_minute == 2
    assert s.tracing_enabled is True


@pytest.mark.parametrize("env", [{}, {"ONSTAGE_URL": ""}])
def test_missing_or_empty_onstage_url_raises(env):
    with pytest.raises(ValueError, match="ONSTAGE_URL"):
        Settings.from_env(env)


@pytest.mark.parametrize("name", ["TRUSTED_PROXY_HOPS", "RATE_PER_MINUTE", "RATE_PER_IP_DAILY", "GLOBAL_DAILY"])
def test_non_integer_env_names_variable(name):
    with pytest.raises(ValueError, match=name):
        Settings.from_env({"ONSTAGE_URL": "https://example.com", name: "abc"})


def test_wildcard_origin_rejected():
    with pytest.raises(ValueError):
        Settings.from_env({"ONSTAGE_URL": "https://example.com", "ALLOWED_ORIGINS": "*"})
