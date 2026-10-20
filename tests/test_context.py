from pathlib import Path
import pytest
from repopilot.context import build_index, query_index, grounded_context


def test_versioned_context_and_citations(tmp_path):
    repo = tmp_path / 'repo'
    repo.mkdir()
    (repo / 'handler.py').write_text('def retry_request():\n    """Retry failed network calls."""\n    return True\n')
    index_dir = tmp_path / 'indexes'
    manifest = build_index(repo, index_dir)
    assert manifest['chunk_count'] == 1
    assert build_index(repo, index_dir)['snapshot'] == manifest['snapshot']
    results = query_index(index_dir, manifest['snapshot'], 'retry network')
    assert results and results[0]['path'] == 'handler.py'
    assert results[0]['citation'].startswith('handler.py#L1-')
    assert 'SOURCE handler.py#L1-' in grounded_context(results)
    (repo / 'handler.py').write_text('def other_function():\n    return False\n')
    assert build_index(repo, index_dir)['snapshot'] != manifest['snapshot']
    assert query_index(index_dir, manifest['snapshot'], 'retry')


def test_empty_and_invalid_queries(tmp_path):
    repo = tmp_path / 'repo'
    repo.mkdir()
    manifest = build_index(repo, tmp_path / 'indexes')
    assert query_index(tmp_path / 'indexes', manifest['snapshot'], 'anything') == []
    with pytest.raises(ValueError):
        query_index(tmp_path / 'indexes', '../bad', 'anything')
