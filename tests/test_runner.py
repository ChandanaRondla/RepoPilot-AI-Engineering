from pathlib import Path
import pytest
from repopilot.test_runner import run_pytest

def test_requires_explicit_trust(tmp_path):
    with pytest.raises(PermissionError): run_pytest(tmp_path)

@pytest.mark.parametrize('timeout', [0,-1,601,999])
def test_invalid_timeout(tmp_path,timeout):
    with pytest.raises(ValueError): run_pytest(tmp_path, trusted=True,timeout=timeout)

def test_missing_root(tmp_path):
    with pytest.raises(ValueError): run_pytest(tmp_path/'missing',trusted=True)

def test_missing_target(tmp_path):
    with pytest.raises(ValueError): run_pytest(tmp_path,trusted=True)

def test_escape_target(tmp_path):
    with pytest.raises(ValueError): run_pytest(tmp_path,trusted=True,target='../')

def test_real_test_passes(tmp_path):
    tests=tmp_path/'tests';tests.mkdir()
    (tests/'test_example.py').write_text('def test_math():\n    assert 2 + 2 == 4\n')
    result=run_pytest(tmp_path,trusted=True)
    assert result['passed'] and result['exit_code']==0

def test_real_test_fails(tmp_path):
    tests=tmp_path/'tests';tests.mkdir()
    (tests/'test_example.py').write_text('def test_math():\n    assert 2 + 2 == 5\n')
    result=run_pytest(tmp_path,trusted=True)
    assert not result['passed'] and result['exit_code']!=0
