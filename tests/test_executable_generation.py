from pathlib import Path
import subprocess, sys
from repopilot.core import test_proposals as generate_proposals, review_diff


def test_generates_and_executes_real_assertion(tmp_path):
    (tmp_path / 'calculator.py').write_text('def answer():\n    return 42\n')
    diff = '+++ b/calculator.py\n@@ -0,0 +1,2 @@\n+def answer():\n+    return 42\n'
    proposal = generate_proposals(tmp_path, diff)[0]
    assert proposal['kind'] == 'executable_literal'
    assert 'assert answer() == 42' in proposal['content']
    tests = tmp_path / 'tests'; tests.mkdir()
    (tests / 'test_calculator_answer.py').write_text(proposal['content'])
    result = subprocess.run([sys.executable, '-m', 'pytest', '-q', str(tests)], cwd=tmp_path, capture_output=True, text=True, timeout=15)
    assert result.returncode == 0, result.stdout + result.stderr


def test_does_not_invent_expectations(tmp_path):
    (tmp_path / 'calc.py').write_text('def add(x, y):\n    return x + y\n')
    diff = '+++ b/calc.py\n@@ -0,0 +1,2 @@\n+def add(x, y):\n+    return x + y\n'
    proposal = generate_proposals(tmp_path, diff)[0]
    assert proposal['kind'] == 'review_required'
    assert 'pytest.skip' in proposal['content']


def test_comment_string_safe_shell_not_flagged():
    diff = '''+++ b/app.py
@@ -0,0 +1,4 @@
+# eval(x) is unsafe
+message = "print('hello') and eval(x)"
+subprocess.run(["echo", "ok"], shell=False, check=True)
+password = ""
'''
    assert review_diff(diff) == []
