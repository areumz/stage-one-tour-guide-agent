import logging

from tour_guide.main import build_app


def test_build_app_configures_app_logger_once(monkeypatch):
    monkeypatch.setenv("ONSTAGE_URL", "http://localhost:1")
    monkeypatch.setenv("OPENAI_API_KEY", "dummy")
    pkg = logging.getLogger("tour_guide")
    monkeypatch.setattr(pkg, "handlers", [])
    monkeypatch.setattr(pkg, "level", logging.NOTSET)
    build_app()
    build_app()
    assert pkg.level == logging.INFO
    assert len(pkg.handlers) == 1


def _tracing_calls(monkeypatch, tracing_env):
    calls = []
    monkeypatch.setattr("tour_guide.main.set_tracing_disabled", calls.append)
    monkeypatch.setenv("ONSTAGE_URL", "http://localhost:1")
    monkeypatch.setenv("OPENAI_API_KEY", "dummy")
    monkeypatch.delenv("TRACING_ENABLED", raising=False)
    if tracing_env is not None:
        monkeypatch.setenv("TRACING_ENABLED", tracing_env)
    build_app()
    return calls


def test_tracing_disabled_by_default(monkeypatch):
    assert _tracing_calls(monkeypatch, None) == [True]


def test_tracing_enabled_by_env(monkeypatch):
    assert _tracing_calls(monkeypatch, "true") == [False]
