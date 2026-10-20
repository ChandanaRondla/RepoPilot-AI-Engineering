from pathlib import Path
from repopilot.core import safe_files, chunks, retrieve, parse_added_lines, review_diff, changed_python_functions, test_proposals as propose_tests, analyze

DIFF = '''diff --git a/app.py b/app.py
--- a/app.py
+++ b/app.py
@@ -1,2 +1,5 @@
 old = 1
+def calculate_total(items):
+    print(items)
+    return sum(items)
+password = "secret_value_123"
'''

def test_file_filtering(tmp_path):
    (tmp_path / 'app.py').write_text('def hello():\n    return 1\n')
    (tmp_path / 'ignored.exe').write_text('bad')
    (tmp_path / '.git').mkdir()
    (tmp_path / '.git' / 'hidden.py').write_text('bad')
    assert [p.name for p in safe_files(tmp_path)] == ['app.py']

def test_chunks(tmp_path):
    (tmp_path / 'x.py').write_text('a\n' * 65)
    assert [(x['start_line'], x['end_line']) for x in chunks(tmp_path)] == [(1,60),(61,65)]

def test_retrieve(tmp_path):
    (tmp_path / 'auth.py').write_text('def validate_password():\n    return True\n')
    (tmp_path / 'other.py').write_text('nothing relevant')
    result = retrieve(tmp_path, 'password validation')
    assert result and result[0]['path'] == 'auth.py'

def test_retrieve_empty_query(tmp_path):
    assert retrieve(tmp_path, '!?') == []

def test_added_line_numbers():
    assert parse_added_lines(DIFF)[0] == ('app.py', 2, 'def calculate_total(items):')

def test_review_findings():
    rules = {x.rule for x in review_diff(DIFF)}
    assert 'hardcoded-secret' in rules and 'debug-print' in rules

def test_removed_lines_not_flagged():
    assert review_diff('--- a/a.py\n+++ b/a.py\n@@ -1 +1 @@\n-password = "secret_value_123"\n+pass\n') == []

def test_functions():
    assert changed_python_functions(DIFF) == [('app.py','calculate_total')]

def test_proposals_are_explicitly_skipped(tmp_path):
    proposal = propose_tests(tmp_path, DIFF)[0]
    assert 'pytest.skip' in proposal['content']
    assert 'assert False' not in proposal['content']

def test_analyze(tmp_path):
    (tmp_path / 'app.py').write_text('def calculate_total(items):\n    return sum(items)\n')
    result = analyze(tmp_path, DIFF)
    assert result['summary']['changed_files'] == 1
    assert result['summary']['proposed_test_files'] == 1

def test_unsafe_ref(tmp_path):
    from repopilot.core import diff_from_git
    import pytest
    with pytest.raises(ValueError):
        diff_from_git(tmp_path, '--output=/tmp/a')

def test_large_file_skipped(tmp_path):
    (tmp_path / 'huge.py').write_text('x' * 150001)
    assert safe_files(tmp_path) == []

def test_bare_except():
    diff = '+++ b/a.py\n@@ -0,0 +1 @@\n+except:\n'
    assert review_diff(diff)[0].rule == 'unbounded-except'

def test_duplicate_function_once():
    diff = '+++ b/a.py\n@@ -0,0 +1,2 @@\n+def x():\n+def x():\n'
    assert changed_python_functions(diff) == [('a.py','x')]

def test_llm_requires_key(monkeypatch):
    from repopilot.llm import review_with_llm
    import pytest
    monkeypatch.delenv('OPENAI_API_KEY', raising=False)
    with pytest.raises(ValueError, match='OPENAI_API_KEY'):
        review_with_llm('diff', [])

def test_llm_endpoint_requires_https():
    from repopilot.llm import review_with_llm
    import pytest
    with pytest.raises(ValueError, match='HTTPS'):
        review_with_llm('diff', [], api_key='fake', endpoint='http://example.com')
