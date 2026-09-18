"""Интеграционные проверки на PostgreSQL после alembic upgrade head.

Измерения тестов откатываются вместе с внешней транзакцией.
"""
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.database import engine, get_session
from app.main import app


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("AGENT_TOKEN", "test-agent-token")
    with engine.connect() as connection:
        transaction = connection.begin()

        def test_session():
            with Session(bind=connection, join_transaction_mode="create_savepoint") as session:
                yield session

        app.dependency_overrides[get_session] = test_session
        try:
            with TestClient(app) as test_client:
                yield test_client
        finally:
            app.dependency_overrides.clear()
            transaction.rollback()


@pytest.fixture
def payload():
    return {
        "agent_id": f"test-{uuid4().hex}",
        "collected_at": "2026-09-18T12:00:00Z",
        "cpu_percent": 24.5,
        "memory_used_bytes": 8589934592,
        "memory_total_bytes": 17179869184,
        "disk_used_bytes": 107374182400,
        "disk_total_bytes": 536870912000,
    }


HEADERS = {"X-Agent-Token": "test-agent-token"}


def test_round_trip_and_latest_order(client, payload):
    response = client.post("/api/v1/metrics", json=payload, headers=HEADERS)
    assert response.status_code == 201, response.text
    saved = response.json()
    assert saved["memory_used_bytes"] == payload["memory_used_bytes"]
    assert saved["received_at"]
    older = {**payload, "collected_at": "2026-09-18T11:00:00Z"}
    assert client.post("/api/v1/metrics", json=older, headers=HEADERS).status_code == 201
    url = f"/api/v1/agents/{payload['agent_id']}/metrics/latest"
    latest = client.get(url, headers=HEADERS)
    assert latest.status_code == 200
    assert latest.json() == saved
    tied = client.post("/api/v1/metrics", json=payload, headers=HEADERS).json()
    assert client.get(url, headers=HEADERS).json()["id"] == tied["id"]


@pytest.mark.parametrize("headers", [{}, {"X-Agent-Token": "wrong"}])
def test_authentication(client, payload, headers):
    assert client.post("/api/v1/metrics", json=payload, headers=headers).status_code == 401
    assert client.get(f"/api/v1/agents/{payload['agent_id']}/metrics/latest", headers=headers).status_code == 401
    assert client.get(f"/api/v1/agents/{payload['agent_id']}/metrics/latest", headers=HEADERS).status_code == 404


@pytest.mark.parametrize("changes", [
    {"cpu_percent": 101},
    {"cpu_percent": -1},
    {"memory_used_bytes": -1},
    {"memory_total_bytes": 0},
    {"memory_used_bytes": 17179869185},
    {"disk_used_bytes": 536870912001},
    {"disk_total_bytes": 0},
    {"disk_used_bytes": 1.5},
    {"memory_total_bytes": 9223372036854775808},
    {"collected_at": "2026-09-18T12:00:00"},
    {"agent_id": "bad agent"},
    {"extra": "unexpected"},
])
def test_validation(client, payload, changes):
    response = client.post("/api/v1/metrics", json={**payload, **changes}, headers=HEADERS)
    assert response.status_code == 422, response.text


def test_unknown_agent(client):
    assert client.get(f"/api/v1/agents/{uuid4().hex}/metrics/latest", headers=HEADERS).status_code == 404


def test_missing_server_token(client, payload, monkeypatch):
    monkeypatch.delenv("AGENT_TOKEN")
    assert client.post("/api/v1/metrics", json=payload, headers=HEADERS).status_code == 503


def test_health(client):
    assert client.get("/health").json() == {"status": "ok", "database": "ok"}
