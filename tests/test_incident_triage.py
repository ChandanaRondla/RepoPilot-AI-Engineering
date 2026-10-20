from pathlib import Path

import pytest

from repopilot.context import build_index
from repopilot.incident_triage import investigate_incident


@pytest.fixture
def repository(tmp_path):
    source = tmp_path / "sample_repo"
    source.mkdir()
    (source / "worker.py").write_text(
        "def process_job():\n"
        "    raise TimeoutError('worker timeout')\n"
    )
    index = tmp_path / "index"
    manifest = build_index(source, index, semantic=False)
    return index, manifest["snapshot"]


def test_empty_logs_rejected(repository):
    index, snapshot = repository
    with pytest.raises(ValueError):
        investigate_incident(index, snapshot, "")


def test_large_logs_rejected(repository):
    index, snapshot = repository
    with pytest.raises(ValueError):
        investigate_incident(index, snapshot, "x" * 20001)


def test_no_model_requires_review(repository):
    index, snapshot = repository
    result = investigate_incident(
        index, snapshot, "TimeoutError worker timeout"
    )
    assert result["status"] == "awaiting_model"
    assert result["requires_human_approval"] is True


def test_model_generates_cited_analysis(repository):
    index, snapshot = repository

    def fake_executor(role, task, evidence, previous):
        assert role == "review"
        assert "TimeoutError" in task
        return {
            "proposal": "The worker may be failing due to a timeout.",
            "actions": ["Inspect worker timeout configuration"],
            "citations": [evidence[0]["citation"]],
            "model": "mock-model",
        }

    result = investigate_incident(
        index,
        snapshot,
        "TimeoutError worker timeout",
        executor=fake_executor,
    )
    assert result["status"] == "awaiting_human_review"
    assert result["requires_human_approval"] is True
    assert result["analysis"]["citations"]


def test_invalid_citation_rejected(repository):
    index, snapshot = repository

    def fake_executor(role, task, evidence, previous):
        return {
            "proposal": "Possible timeout",
            "actions": [],
            "citations": ["invented.py#L1-L5"],
        }

    with pytest.raises(ValueError, match="Invalid source citations"):
        investigate_incident(
            index,
            snapshot,
            "TimeoutError worker timeout",
            executor=fake_executor,
        )


def test_model_failure_is_safe(repository):
    index, snapshot = repository

    def failing_executor(role, task, evidence, previous):
        raise RuntimeError("Provider unavailable")

    result = investigate_incident(
        index,
        snapshot,
        "TimeoutError worker timeout",
        executor=failing_executor,
    )
    assert result["status"] == "analysis_failed"
    assert result["requires_human_approval"] is True
