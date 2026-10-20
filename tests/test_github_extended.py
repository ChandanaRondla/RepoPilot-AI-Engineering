import json
import urllib.error

import pytest
from repopilot import github_integration as gh


class FakeResponse:
    def __init__(self, body):
        self.body = body.encode("utf-8")

    def read(self):
        return self.body

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


@pytest.mark.parametrize("number", [1, 2, 10, 100, 999])
def test_fetch_pr_diff_success(monkeypatch, number):
    monkeypatch.setenv("GITHUB_TOKEN", "test-token")

    def fake_urlopen(request, timeout=20):
        assert f"/pulls/{number}" in request.full_url
        assert request.get_header("Authorization") == "Bearer test-token"
        assert request.get_header("Accept") == "application/vnd.github.v3.diff"
        return FakeResponse("diff --git a/a.py b/a.py")

    monkeypatch.setattr(gh, "urlopen", fake_urlopen)

    result = gh.fetch_pr_diff("owner/repo", number)

    assert "diff --git" in result


@pytest.mark.parametrize("status", [401, 403, 404, 422, 500])
def test_github_http_errors(monkeypatch, status):
    monkeypatch.setenv("GITHUB_TOKEN", "test-token")

    def fake_urlopen(request, timeout=20):
        raise urllib.error.HTTPError(
            request.full_url,
            status,
            "GitHub API error",
            {},
            None,
        )

    monkeypatch.setattr(gh, "urlopen", fake_urlopen)

    with pytest.raises(urllib.error.HTTPError) as exc:
        gh.fetch_pr_diff("owner/repo", 1)

    assert exc.value.code == status


@pytest.mark.parametrize("number", [1, 2, 5, 10])
def test_post_pr_comment_success(monkeypatch, number):
    monkeypatch.setenv("GITHUB_TOKEN", "test-token")

    def fake_request(url, token, **kwargs):
        assert f"/issues/{number}/comments" in url
        assert token == "test-token"
        assert kwargs["method"] == "POST"
        assert kwargs["payload"]["body"] == "Review complete"
        return json.dumps({
            "id": 12345,
            "html_url": "https://github.com/owner/repo/issues/1#issuecomment-12345",
        })

    monkeypatch.setattr(gh, "_request", fake_request)

    result = gh.post_pr_comment(
        "owner/repo",
        number,
        "Review complete",
        dry_run=False,
    )

    assert result["dry_run"] is False
    assert result["id"] == 12345


@pytest.mark.parametrize("message", [
    "Review complete",
    "Potential security issue",
    "Tests passed",
    "Human approval required",
])
def test_comment_dry_run(monkeypatch, message):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)

    result = gh.post_pr_comment("owner/repo", 1, message)

    assert result["dry_run"] is True
    assert result["body"] == message
