import pytest

fastapi = pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from fastapi.testclient import TestClient
from repopilot import api

client = TestClient(api.app)


@pytest.mark.parametrize("error", [
    ValueError("invalid repository"),
    OSError("repository unavailable"),
])
def test_review_returns_400(monkeypatch, error):
    def fail(*args, **kwargs):
        raise error

    monkeypatch.setattr(api, "analyze", fail)

    response = client.post(
        "/review",
        json={"repo": ".", "diff": ""}
    )

    assert response.status_code == 400
    assert response.json()["detail"] == str(error)


def test_review_success(monkeypatch):
    expected = {"findings": [], "context": []}

    monkeypatch.setattr(
        api,
        "analyze",
        lambda *args, **kwargs: expected
    )

    response = client.post(
        "/review",
        json={"repo": ".", "diff": ""}
    )

    assert response.status_code == 200
    assert response.json() == expected


@pytest.mark.parametrize("payload", [
    {},
    {"repo": "."},
    {"diff": ""},
    {"repo": 123, "diff": ""},
    {"repo": ".", "diff": None},
])
def test_review_invalid_payload(payload):
    response = client.post("/review", json=payload)
    assert response.status_code == 422
