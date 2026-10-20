from pathlib import Path

from repopilot.context import build_index, query_index


def test_rag_excludes_generated_artifacts(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()

    (repo / "repopilot").mkdir()
    (repo / "benchmarks").mkdir()

    (repo / "repopilot" / "sandbox.py").write_text(
        "def execute_docker_sandbox():\n"
        "    return 'Docker sandbox execution'\n"
    )

    (repo / "benchmarks" / "rag_eval_cases.json").write_text(
        '{"question": "Docker sandbox execution"}'
    )

    (repo / "repopilot-incident-report.json").write_text(
        '{"incident": "Docker sandbox execution"}'
    )

    index = tmp_path / "index"
    manifest = build_index(repo, index)

    results = query_index(
        index,
        manifest["snapshot"],
        "Docker sandbox execution",
        limit=10,
    )

    paths = {result["path"] for result in results}

    assert "repopilot/sandbox.py" in paths
    assert "benchmarks/rag_eval_cases.json" not in paths
    assert "repopilot-incident-report.json" not in paths
