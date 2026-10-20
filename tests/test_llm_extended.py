import json
import urllib.error

import pytest

from repopilot import llm


class FakeResponse:
    def __init__(self, data):
        self.data = json.dumps(data).encode("utf-8")

    def read(self):
        return self.data

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def mock_model(monkeypatch, model_result):
    def fake_urlopen(request, timeout=25):
        return FakeResponse({
            "choices": [{
                "message": {
                    "content": json.dumps(model_result)
                }
            }]
        })

    monkeypatch.setattr(
        llm.urllib.request, "urlopen", fake_urlopen
    )


@pytest.mark.parametrize("findings", [
    [],
    [{"severity": "high", "message": "Unsafe code"}],
    [{"severity": "low", "message": "Missing validation"}],
])
def test_valid_model_response(monkeypatch, findings):
    mock_model(monkeypatch, {
        "findings": findings,
        "test_ideas": ["Add regression test"]
    })

    result = llm.review_with_llm(
        "sample diff",
        [],
        api_key="fake-test-key",
    )

    assert result["findings"] == findings
    assert result["model"] == "gpt-4o-mini"
    assert "human review" in result["warning"].lower()


@pytest.mark.parametrize("model_result", [
    {},
    {"findings": []},
    {"test_ideas": []},
    {"findings": "invalid", "test_ideas": []},
    {"findings": [], "test_ideas": "invalid"},
    {"findings": None, "test_ideas": []},
])
def test_invalid_model_structure(monkeypatch, model_result):
    mock_model(monkeypatch, model_result)

    with pytest.raises(ValueError, match="invalid review"):
        llm.review_with_llm(
            "sample diff",
            [],
            api_key="fake-test-key",
        )


@pytest.mark.parametrize("status", [400, 401, 403, 429, 500, 503])
def test_model_http_errors(monkeypatch, status):
    def fail(request, timeout=25):
        raise urllib.error.HTTPError(
            request.full_url,
            status,
            "API error",
            {},
            None,
        )

    monkeypatch.setattr(llm.urllib.request, "urlopen", fail)

    with pytest.raises(urllib.error.HTTPError) as exc:
        llm.review_with_llm(
            "sample diff",
            [],
            api_key="fake-test-key",
        )

    assert exc.value.code == status


@pytest.mark.parametrize("endpoint", [
    "http://example.com",
    "http://localhost:8000",
    "ftp://example.com",
])
def test_reject_insecure_endpoint(endpoint):
    with pytest.raises(ValueError, match="HTTPS"):
        llm.review_with_llm(
            "sample diff",
            [],
            api_key="fake-test-key",
            endpoint=endpoint,
        )


def test_missing_api_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    with pytest.raises(ValueError, match="OPENAI_API_KEY"):
        llm.review_with_llm("sample diff", [])


def test_request_payload_limits(monkeypatch):
    captured = {}

    def fake_urlopen(request, timeout=25):
        captured["payload"] = json.loads(
            request.data.decode("utf-8")
        )
        return FakeResponse({
            "choices": [{
                "message": {
                    "content": json.dumps({
                        "findings": [],
                        "test_ideas": []
                    })
                }
            }]
        })

    monkeypatch.setattr(llm.urllib.request, "urlopen", fake_urlopen)

    context = [
        {
            "path": f"file_{i}.py",
            "start_line": 1,
            "end_line": 10,
            "content": "x" * 10000,
        }
        for i in range(20)
    ]

    llm.review_with_llm(
        "x" * 50000,
        context,
        api_key="fake-test-key",
    )

    user_content = json.loads(
        captured["payload"]["messages"][1]["content"]
    )

    assert len(user_content["diff"]) == 30000
    assert len(user_content["repository_context"]) == 5
