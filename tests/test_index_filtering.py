from pathlib import Path

from repopilot.core import chunks


def test_index_excludes_generated_artifacts(tmp_path: Path):
    (tmp_path / "repopilot").mkdir()
    (tmp_path / "repopilot" / "sandbox.py").write_text(
        "def execute_sandbox():\n    return True\n"
    )

    generated = tmp_path / ".repopilot-context" / "snapshot"
    generated.mkdir(parents=True)
    (generated / "manifest.json").write_text('{"generated": true}')

    benchmarks = tmp_path / "benchmarks"
    benchmarks.mkdir()
    (benchmarks / "rag_eval_results.json").write_text("{}")
    (benchmarks / "run_benchmark.py").write_text(
        "def benchmark():\n    pass\n"
    )

    (tmp_path / "config.json").write_text('{"test": true}')

    paths = {item["path"] for item in chunks(tmp_path)}

    assert "repopilot/sandbox.py" in paths
    assert not any(path.startswith(".repopilot-context/") for path in paths)
    assert not any(path.startswith("benchmarks/") for path in paths)
    assert not any(path.endswith(".json") for path in paths)
