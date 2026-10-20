from pathlib import Path
import pytest
from repopilot.context import build_index
from repopilot.sdlc_agents import run_sdlc_workflow


def setup_repo(tmp_path):
    repo = tmp_path / 'repo'
    repo.mkdir()
    (repo / 'sandbox.py').write_text('def run_sandbox():\n    return "isolated"\n')
    index = tmp_path / 'index'
    snapshot = build_index(repo, index)['snapshot']
    return repo, index, snapshot


def test_full_workflow_requires_approval_and_preserves_source(tmp_path):
    repo, index, snapshot = setup_repo(tmp_path)
    before = (repo / 'sandbox.py').read_bytes()
    result = run_sdlc_workflow(index, snapshot, 'Improve sandbox isolation')
    assert result['status'] == 'awaiting_human_approval'
    assert result['approved'] is False and result['changes_applied'] is False
    assert [t['role'] for t in result['trace']] == ['implementation', 'testing', 'documentation', 'review']
    assert all(t['status'] == 'completed' for t in result['trace'])
    assert (repo / 'sandbox.py').read_bytes() == before


def test_failure_blocks_dependents_and_records_trace(tmp_path):
    _, index, snapshot = setup_repo(tmp_path)
    def fail_implementation(role, request, evidence, previous):
        if role == 'implementation':
            raise RuntimeError('model unavailable')
        return {'proposal': 'ok'}
    result = run_sdlc_workflow(index, snapshot, 'Improve sandbox', executor=fail_implementation, max_retries=2)
    assert result['status'] == 'blocked'
    assert result['trace'][0]['attempts'] == 3
    assert all(t['status'] == 'skipped' for t in result['trace'][1:])


def test_invalid_inputs(tmp_path):
    _, index, snapshot = setup_repo(tmp_path)
    with pytest.raises(ValueError):
        run_sdlc_workflow(index, snapshot, '')
    with pytest.raises(ValueError):
        run_sdlc_workflow(index, snapshot, 'task', max_retries=4)


def test_retry_recovers(tmp_path):
    _, index, snapshot = setup_repo(tmp_path)
    calls = {}
    def flaky(role, request, evidence, previous):
        calls[role] = calls.get(role, 0) + 1
        if role == 'implementation' and calls[role] == 1:
            raise TimeoutError('temporary')
        return {'proposal': role + ' plan'}
    result = run_sdlc_workflow(index, snapshot, 'Improve sandbox', executor=flaky)
    assert result['status'] == 'awaiting_human_approval'
    assert result['trace'][0]['attempts'] == 2
