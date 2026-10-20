from pathlib import Path

from benchmarks.incident_triage_benchmark import main


def test_incident_triage_benchmark(monkeypatch, tmp_path):
    project_root = Path(__file__).resolve().parents[1]

    # Use actual repository source files for evidence retrieval.
    monkeypatch.chdir(project_root)

    # Keep the generated benchmark report out of the source tree.
    original_write_text = Path.write_text

    def safe_write_text(path, data, *args, **kwargs):
        if path.name == "incident_triage_results.json":
            path = tmp_path / path.name
        return original_write_text(path, data, *args, **kwargs)

    monkeypatch.setattr(Path, "write_text", safe_write_text)

    main()
