import io
import json
from pathlib import Path
from unittest.mock import patch

from repopilot.context import build_index
from repopilot.incident_triage import investigate_incident
from repopilot.incident_llm import analyze_incident_with_llm


def test_incident_llm_end_to_end(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()

    (repo / "sandbox.py").write_text(
        "def run_sandbox():\n"
        "    raise RuntimeError('Docker daemon unavailable')\n"
    )

    index = tmp_path / "index"
    manifest = build_index(repo, index, semantic=False)

    def executor(role, task, evidence, state):
        assert role == "review"
        assert evidence

        citation = evidence[0]["citation"]

        model_result = {
            "proposal": "Docker daemon may be unavailable.",
            "actions": ["Verify Docker daemon availability."],
            "citations": [citation],
        }

        envelope = {
            "choices": [
                {"message": {"content": json.dumps(model_result)}}
            ]
        }

        response = io.BytesIO(
            json.dumps(envelope).encode("utf-8")
        )

        with patch(
            "repopilot.incident_llm.urllib.request.urlopen",
            return_value=response,
        ):
            return analyze_incident_with_llm(
                role,
                task,
                evidence,
                state,
                api_key="test-key",
            )

    result = investigate_incident(
        index,
        manifest["snapshot"],
        "Docker daemon unavailable",
        executor=executor,
    )

    assert result["status"] == "awaiting_human_review"
    assert result["requires_human_approval"] is True
    assert result["analysis"]["proposal"]
    assert result["analysis"]["recommended_actions"]
    assert result["analysis"]["citations"]
    assert result["analysis"]["citations"][0] in result["source_citations"]
