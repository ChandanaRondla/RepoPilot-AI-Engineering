import io
import json
from unittest.mock import patch

import pytest

from repopilot.incident_llm import analyze_incident_with_llm


EVIDENCE = [
    {
        "path": "repopilot/sandbox.py",
        "start_line": 1,
        "end_line": 30,
        "content": "Docker sandbox implementation",
    }
]

CITATION = "repopilot/sandbox.py#L1-L30"


def fake_response(result):
    envelope = {
        "choices": [
            {"message": {"content": json.dumps(result)}}
        ]
    }

    return io.BytesIO(json.dumps(envelope).encode("utf-8"))


def test_valid_incident_analysis():
    result = {
        "proposal": "Docker daemon may be unavailable.",
        "actions": ["Verify Docker daemon availability."],
        "citations": [CITATION],
    }

    with patch(
        "repopilot.incident_llm.urllib.request.urlopen",
        return_value=fake_response(result),
    ):
        output = analyze_incident_with_llm(
            "review",
            "Investigate Docker failure",
            EVIDENCE,
            {},
            api_key="test-key",
        )

    assert output["proposal"] == result["proposal"]
    assert output["actions"] == result["actions"]
    assert output["citations"] == [CITATION]
    assert output["model"] == "gpt-4o-mini"


def test_rejects_fabricated_citations():
    result = {
        "proposal": "Possible Docker failure.",
        "actions": ["Inspect logs."],
        "citations": ["fake.py#L1-L10"],
    }

    with patch(
        "repopilot.incident_llm.urllib.request.urlopen",
        return_value=fake_response(result),
    ):
        with pytest.raises(ValueError, match="Invalid source citations"):
            analyze_incident_with_llm(
                "review",
                "Investigate failure",
                EVIDENCE,
                {},
                api_key="test-key",
            )


def test_rejects_missing_proposal():
    result = {
        "proposal": "",
        "actions": ["Inspect logs."],
        "citations": [CITATION],
    }

    with patch(
        "repopilot.incident_llm.urllib.request.urlopen",
        return_value=fake_response(result),
    ):
        with pytest.raises(ValueError, match="Missing incident proposal"):
            analyze_incident_with_llm(
                "review",
                "Investigate failure",
                EVIDENCE,
                {},
                api_key="test-key",
            )


def test_requires_api_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    with pytest.raises(ValueError, match="OPENAI_API_KEY"):
        analyze_incident_with_llm(
            "review",
            "Investigate failure",
            EVIDENCE,
            {},
        )


def test_rejects_insecure_endpoint():
    with pytest.raises(ValueError, match="HTTPS"):
        analyze_incident_with_llm(
            "review",
            "Investigate failure",
            EVIDENCE,
            {},
            api_key="test-key",
            endpoint="http://example.com/api",
        )
