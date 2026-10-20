import sys
import pytest
from repopilot import cli


def run_cli(monkeypatch, capsys, args):
    monkeypatch.setattr(sys, "argv", ["repopilot", *args])
    cli.main()
    return capsys.readouterr()


@pytest.mark.parametrize("args", [
    [],
    ["--help"],
    ["search", "--help"],
    ["review", "--help"],
    ["gate", "--help"],
    ["evaluate", "--help"],
    ["test", "--help"],
])
def test_cli_help_and_usage(monkeypatch, capsys, args):
    monkeypatch.setattr(sys, "argv", ["repopilot", *args])

    with pytest.raises(SystemExit) as exc:
        cli.main()

    assert exc.value.code in (0, 2)


@pytest.mark.parametrize("args", [
    ["search"],
    ["review", "--unknown-option"],
    ["gate"],
    ["evaluate"],
    ["test", "--timeout", "not-a-number"],
])
def test_cli_invalid_arguments(monkeypatch, capsys, args):
    monkeypatch.setattr(sys, "argv", ["repopilot", *args])

    with pytest.raises(SystemExit) as exc:
        cli.main()

    assert exc.value.code == 2


def test_cli_search(monkeypatch, capsys):
    expected = [{"file": "sample.py", "score": 1.0}]

    monkeypatch.setattr(
        cli, "retrieve", lambda *args, **kwargs: expected
    )

    result = run_cli(
        monkeypatch, capsys, ["search", "example"]
    )

    assert "sample.py" in result.out


def test_cli_review(monkeypatch, capsys, tmp_path):
    diff = tmp_path / "sample.diff"
    diff.write_text("sample diff")

    monkeypatch.setattr(
        cli, "analyze",
        lambda *args, **kwargs: {"findings": []}
    )

    result = run_cli(
        monkeypatch,
        capsys,
        ["review", "--diff-file", str(diff)],
    )

    assert '"findings"' in result.out
