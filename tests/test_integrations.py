from pathlib import Path
import pytest
from repopilot.agents import orchestrate
from repopilot.github_integration import post_pr_comment, fetch_pr_diff
from repopilot.sandbox import run_isolated_pytest

@pytest.mark.parametrize('repo', ['bad','owner/repo/extra','../repo','owner/has space',''])
def test_bad_repos(repo):
    with pytest.raises(ValueError): post_pr_comment(repo,1,'hello')

@pytest.mark.parametrize('number', [0,-1])
def test_bad_pr_number(number):
    with pytest.raises(ValueError): post_pr_comment('owner/repo',number,'hello')

def test_dry_run_no_token():
    r = post_pr_comment('owner/repo',2,'hello')
    assert r['dry_run'] and r['body']=='hello'

def test_empty_comment():
    with pytest.raises(ValueError): post_pr_comment('owner/repo',2,' ')

def test_long_comment():
    with pytest.raises(ValueError): post_pr_comment('owner/repo',2,'a'*60001)

def test_fetch_requires_token(monkeypatch):
    monkeypatch.delenv('GITHUB_TOKEN', raising=False)
    with pytest.raises(PermissionError): fetch_pr_diff('owner/repo',2)

def test_orchestration_success(tmp_path):
    r = orchestrate(tmp_path,'', specialists={'tester':lambda root,diff:{'tests':3}})
    assert [s['role'] for s in r['steps']]==['reviewer','tester','gate']
    assert r['steps'][1]['output']['tests']==3

def test_orchestration_fail_closed(tmp_path):
    def fail(root,diff): raise RuntimeError('secret')
    r = orchestrate(tmp_path,'', specialists={'tester':fail})
    assert r['status']=='blocked' and r['steps'][1]['output']['error']=='RuntimeError'

def test_orchestration_invalid_role(tmp_path):
    with pytest.raises(ValueError): orchestrate(tmp_path,'', specialists={'gate':lambda r,d:{}})

def test_orchestration_bad_output(tmp_path):
    r = orchestrate(tmp_path,'', specialists={'tester':lambda r,d:None})
    assert r['status']=='blocked'

def test_sandbox_rejects_missing_root(tmp_path):
    with pytest.raises(ValueError): run_isolated_pytest(tmp_path/'missing')

def test_sandbox_rejects_traversal(tmp_path):
    (tmp_path/'tests').mkdir()
    with pytest.raises(ValueError): run_isolated_pytest(tmp_path,target='../')

def test_sandbox_rejects_image(tmp_path):
    (tmp_path/'tests').mkdir()
    with pytest.raises(ValueError): run_isolated_pytest(tmp_path,image='image;rm -rf /')

def test_sandbox_rejects_timeout(tmp_path):
    (tmp_path/'tests').mkdir()
    with pytest.raises(ValueError): run_isolated_pytest(tmp_path,timeout=0)
