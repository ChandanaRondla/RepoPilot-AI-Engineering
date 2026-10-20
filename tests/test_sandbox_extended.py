import subprocess

import pytest

from repopilot import sandbox


@pytest.fixture
def repo(tmp_path):
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_sample.py").write_text(
        "def test_sample(): assert 1 + 1 == 2\n"
    )
    return tmp_path


def test_successful_execution(monkeypatch, repo):
    def fake_run(cmd, **kwargs):
        return subprocess.CompletedProcess(
            cmd, 0, stdout="1 passed", stderr=""
        )

    monkeypatch.setattr(sandbox.subprocess, "run", fake_run)

    result = sandbox.run_isolated_pytest(repo)

    assert result["passed"] is True
    assert result["exit_code"] == 0
    assert "1 passed" in result["stdout"]


@pytest.mark.parametrize("exit_code", [1, 2, 5, 137])
def test_failed_execution(monkeypatch, repo, exit_code):
    def fake_run(cmd, **kwargs):
        return subprocess.CompletedProcess(
            cmd, exit_code, stdout="", stderr="Test failure"
        )

    monkeypatch.setattr(sandbox.subprocess, "run", fake_run)

    result = sandbox.run_isolated_pytest(repo)

    assert result["passed"] is False
    assert result["exit_code"] == exit_code


def test_docker_unavailable(monkeypatch, repo):
    def fake_run(cmd, **kwargs):
        raise FileNotFoundError("docker not found")

    monkeypatch.setattr(sandbox.subprocess, "run", fake_run)

    result = sandbox.run_isolated_pytest(repo)

    assert result["passed"] is False
    assert result["error"] == "Docker unavailable"


def test_execution_timeout(monkeypatch, repo):
    def fake_run(cmd, **kwargs):
        raise subprocess.TimeoutExpired(cmd, 5)

    monkeypatch.setattr(sandbox.subprocess, "run", fake_run)

    result = sandbox.run_isolated_pytest(repo, timeout=5)

    assert result["passed"] is False
    assert result["error"] == "Timeout"


def test_docker_security_configuration(monkeypatch, repo):
    captured = {}

    def fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        captured["kwargs"] = kwargs
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(sandbox.subprocess, "run", fake_run)

    sandbox.run_isolated_pytest(repo)

    cmd = captured["cmd"]

    assert "--network" in cmd
    assert cmd[cmd.index("--network") + 1] == "none"
    assert "--read-only" in cmd
    assert "--cap-drop" in cmd
    assert cmd[cmd.index("--cap-drop") + 1] == "ALL"
    assert "--security-opt" in cmd
    assert "no-new-privileges" in cmd
    assert "--memory" in cmd
    assert "--cpus" in cmd
    assert "--pids-limit" in cmd
    assert "--rm" in cmd


@pytest.mark.parametrize("timeout", [0, -1, 601, 1000])
def test_invalid_timeout(repo, timeout):
    with pytest.raises(ValueError, match="timeout"):
        sandbox.run_isolated_pytest(repo, timeout=timeout)


@pytest.mark.parametrize("image", [
    "",
    "image with spaces",
    "image;rm",
    "image\nmalicious",
])
def test_invalid_image(repo, image):
    with pytest.raises(ValueError, match="image"):
        sandbox.run_isolated_pytest(repo, image=image)


def test_custom_image(monkeypatch, repo):
    captured = {}

    def fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(sandbox.subprocess, "run", fake_run)

    sandbox.run_isolated_pytest(
        repo, image="python:3.12-slim"
    )

    assert "python:3.12-slim" in captured["cmd"]


def test_timeout_forwarded(monkeypatch, repo):
    captured = {}

    def fake_run(cmd, **kwargs):
        captured["timeout"] = kwargs["timeout"]
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(sandbox.subprocess, "run", fake_run)

    sandbox.run_isolated_pytest(repo, timeout=30)

    assert captured["timeout"] == 30


def test_output_truncation(monkeypatch, repo):
    def fake_run(cmd, **kwargs):
        return subprocess.CompletedProcess(
            cmd, 0, stdout="x" * 20000, stderr="y" * 20000
        )

    monkeypatch.setattr(sandbox.subprocess, "run", fake_run)

    result = sandbox.run_isolated_pytest(repo)

    assert len(result["stdout"]) == 12000
    assert len(result["stderr"]) == 6000


def test_read_only_workspace(monkeypatch, repo):
    captured = {}

    def fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(sandbox.subprocess, "run", fake_run)

    sandbox.run_isolated_pytest(repo)

    cmd = captured["cmd"]
    mount = cmd[cmd.index("--mount") + 1]

    assert "readonly" in mount
    assert "dst=/workspace" in mount


def test_missing_repository(tmp_path):
    with pytest.raises(ValueError, match="Root"):
        sandbox.run_isolated_pytest(tmp_path / "missing")


def test_missing_test_directory(tmp_path):
    with pytest.raises(ValueError, match="Target"):
        sandbox.run_isolated_pytest(tmp_path)


def test_nested_test_directory(monkeypatch, repo):
    (repo / "tests" / "unit").mkdir()

    captured = {}

    def fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(sandbox.subprocess, "run", fake_run)

    sandbox.run_isolated_pytest(repo, target="tests/unit")

    assert "tests/unit" in captured["cmd"]
