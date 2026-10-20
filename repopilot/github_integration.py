"""GitHub pull request adapter using stdlib; posting is explicitly opt-in."""
from __future__ import annotations
import json
import os
import re
from urllib.request import Request, urlopen
from urllib.error import HTTPError

_REPO = re.compile(r'^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$')

def _validate(repo: str, number: int) -> None:
    if not _REPO.fullmatch(repo) or any(part in {'.', '..'} for part in repo.split('/')) or number < 1:
        raise ValueError('Expected owner/repo and positive PR number')

def _request(url: str, token: str, *, method: str = 'GET', payload: dict | None = None) -> str:
    if not token:
        raise PermissionError('GITHUB_TOKEN is required')
    headers = {'Authorization': f'Bearer {token}', 'Accept': 'application/vnd.github+json',
               'X-GitHub-Api-Version': '2022-11-28', 'User-Agent': 'RepoPilot'}
    if payload is not None:
        headers['Content-Type'] = 'application/json'
    request = Request(url, headers=headers, method=method,
                      data=json.dumps(payload).encode() if payload is not None else None)
    with urlopen(request, timeout=20) as response:
        return response.read().decode('utf-8')

def fetch_pr_diff(repo: str, number: int, *, token: str | None = None) -> str:
    _validate(repo, number)
    # PR diff via GitHub REST endpoint; media type switches response to unified diff.
    token = token or os.environ.get('GITHUB_TOKEN', '')
    if not token:
        raise PermissionError('GITHUB_TOKEN is required')
    url = f'https://api.github.com/repos/{repo}/pulls/{number}'
    request = Request(url, headers={'Authorization': f'Bearer {token}',
        'Accept': 'application/vnd.github.v3.diff', 'User-Agent': 'RepoPilot'})
    with urlopen(request, timeout=20) as response:
        return response.read().decode('utf-8')

def post_pr_comment(repo: str, number: int, body: str, *, token: str | None = None,
                    dry_run: bool = True) -> dict:
    _validate(repo, number)
    if not body.strip() or len(body) > 60000:
        raise ValueError('Comment must contain 1-60000 characters')
    url = f'https://api.github.com/repos/{repo}/issues/{number}/comments'
    if dry_run:
        return {'dry_run': True, 'url': url, 'body': body}
    response = _request(url, token or os.environ.get('GITHUB_TOKEN', ''), method='POST', payload={'body': body})
    result = json.loads(response)
    return {'dry_run': False, 'id': result['id'], 'html_url': result['html_url']}
