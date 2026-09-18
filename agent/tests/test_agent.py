import json
from datetime import datetime
from types import SimpleNamespace

import httpx
import pytest

from agent import collector
from agent.__main__ import run_cycle
from agent.config import load_settings
from agent.sender import send_metrics


@pytest.fixture
def settings(tmp_path, monkeypatch):
    values = {
        "SERVER_URL": "http://127.0.0.1:8000",
        "AGENT_ID": "test-pc",
        "AGENT_TOKEN": "test-secret",
        "DISK_PATH": str(tmp_path),
        "AGENT_INTERVAL_SECONDS": "60",
        "AGENT_TIMEOUT_SECONDS": "5",
    }
    for key, value in values.items():
        monkeypatch.setenv(key, value)
    return load_settings(tmp_path / ".env")


def test_collected_payload_matches_api(settings, monkeypatch):
    def cpu_percent(interval):
        assert interval == 1
        return 42.5

    monkeypatch.setattr(collector.psutil, "cpu_percent", cpu_percent)
    monkeypatch.setattr(collector.psutil, "virtual_memory", lambda: SimpleNamespace(used=8_000_000_000, total=16_000_000_000))
    monkeypatch.setattr(collector.psutil, "disk_usage", lambda path: SimpleNamespace(used=50_000_000_000, total=100_000_000_000))
    payload = collector.collect_metrics(settings)
    assert payload["cpu_percent"] == 42.5
    assert payload["memory_used_bytes"] == 8_000_000_000
    assert datetime.fromisoformat(payload["collected_at"]).utcoffset().total_seconds() == 0
    # Контракт с бэкендом проверяется здесь; сам агент не импортирует его код.
    from app.schemas import MetricCreate
    MetricCreate.model_validate(payload)


@pytest.mark.parametrize("key,value", [
    ("AGENT_INTERVAL_SECONDS", "0"), ("AGENT_INTERVAL_SECONDS", "nan"),
    ("AGENT_TIMEOUT_SECONDS", "inf"), ("AGENT_TIMEOUT_SECONDS", "abc"),
    ("AGENT_TOKEN", ""), ("AGENT_TOKEN", "bad\nheader"),
    ("AGENT_ID", "bad id"), ("AGENT_ID", "a" * 129),
    ("SERVER_URL", "ftp://localhost"), ("SERVER_URL", "http://user:pass@localhost"),
    ("SERVER_URL", "http://localhost:bad"), ("SERVER_URL", "http://localhost?token=secret"),
    ("DISK_PATH", "relative-folder"),
])
def test_invalid_settings(settings, monkeypatch, tmp_path, key, value):
    monkeypatch.setenv(key, value)
    with pytest.raises(ValueError, match=key):
        load_settings(tmp_path / ".env")


def test_environment_overrides_file(settings, tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("AGENT_ID=from-file\nAGENT_TOKEN=file-secret\n", encoding="utf-8")
    loaded = load_settings(env_file)
    assert loaded.agent_id == "test-pc"
    assert loaded.token == "test-secret"
    assert "test-secret" not in repr(loaded)


@pytest.mark.parametrize("status", [201, 401, 422, 500, 307])
def test_http_statuses_and_request(settings, caplog, status):
    payload = {"agent_id": settings.agent_id, "cpu_percent": 25.0}

    def handler(request):
        assert str(request.url) == "http://localhost/api/v1/metrics"
        assert request.headers["X-Agent-Token"] == settings.token
        assert json.loads(request.content) == payload
        return httpx.Response(status, text="test-secret", headers={"Location": "http://other-host/"})

    with httpx.Client(base_url="http://localhost/", headers={"X-Agent-Token": settings.token}, transport=httpx.MockTransport(handler)) as client:
        assert send_metrics(client, payload) is (status == 201)
    assert settings.token not in caplog.text


def test_connection_failure_then_recovery(settings, monkeypatch, caplog):
    monkeypatch.setattr("agent.__main__.collect_metrics", lambda _: {"agent_id": settings.agent_id, "cpu_percent": 25.0})
    calls = 0

    def handler(request):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise httpx.ConnectError("test-secret", request=request)
        return httpx.Response(201)

    with httpx.Client(base_url="http://localhost/", transport=httpx.MockTransport(handler)) as client:
        assert run_cycle(settings, client) is False
        assert run_cycle(settings, client) is True
    assert settings.token not in caplog.text


def test_collection_error_does_not_send(settings, monkeypatch):
    def fail(_):
        raise OSError("disk disconnected")

    def unexpected_request(request):
        pytest.fail("При ошибке сбора отправки быть не должно")

    monkeypatch.setattr("agent.__main__.collect_metrics", fail)
    with httpx.Client(transport=httpx.MockTransport(unexpected_request)) as client:
        assert run_cycle(settings, client) is False
