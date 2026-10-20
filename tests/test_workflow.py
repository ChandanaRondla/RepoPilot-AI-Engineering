import json
import pytest
from repopilot.workflow import ReviewPolicy, run_review, approve, write_audit_event

@pytest.mark.parametrize('severity', ['low','medium','high','critical'])
def test_valid_policy(severity):
    assert ReviewPolicy(block_at=severity).block_at == severity

@pytest.mark.parametrize('severity', ['', 'unknown', 'HIGH'])
def test_invalid_policy(severity):
    with pytest.raises(ValueError): ReviewPolicy(block_at=severity)

@pytest.mark.parametrize('value', [0,-1])
def test_invalid_file_limit(value):
    with pytest.raises(ValueError): ReviewPolicy(max_changed_files=value)

@pytest.mark.parametrize('value', [0,-1])
def test_invalid_byte_limit(value):
    with pytest.raises(ValueError): ReviewPolicy(max_diff_bytes=value)

@pytest.mark.parametrize('rule,code', [('high','+eval(user_input)'), ('medium','+except:'), ('low','+print(1)')])
def test_blocking_by_threshold(tmp_path, rule, code):
    diff='+++ b/app.py\n@@ -0,0 +1 @@\n'+code+'\n'
    assert run_review(tmp_path, diff, ReviewPolicy(block_at=rule))['status']=='blocked'

def test_clean_requires_approval(tmp_path):
    result=run_review(tmp_path, '+++ b/app.py\n@@ -0,0 +1 @@\n+x = 1\n')
    assert result['status']=='approval_required'

def test_clean_can_pass(tmp_path):
    result=run_review(tmp_path, '+++ b/app.py\n@@ -0,0 +1 @@\n+x = 1\n', ReviewPolicy(require_approval=False))
    assert result['status']=='passed'

def test_approval_records_reviewer(tmp_path):
    report=run_review(tmp_path,'+++ b/a.py\n@@ -0,0 +1 @@\n+x = 1\n')
    approved=approve(report,'engineer@example.com','Reviewed')
    assert approved['status']=='approved' and approved['approval']['reviewer']=='engineer@example.com'
    assert report['status']=='approval_required'

def test_empty_reviewer_rejected(tmp_path):
    with pytest.raises(ValueError): approve(run_review(tmp_path,''),' ')

def test_blocked_cannot_be_approved(tmp_path):
    with pytest.raises(ValueError): approve(run_review(tmp_path,'+++ b/a.py\n@@ -0,0 +1 @@\n+eval(x)\n'),'reviewer')

def test_diff_limit(tmp_path):
    with pytest.raises(ValueError): run_review(tmp_path,'long',ReviewPolicy(max_diff_bytes=3))

def test_file_limit(tmp_path):
    diff='+++ b/a.py\n@@ -0,0 +1 @@\n+x=1\n+++ b/b.py\n@@ -0,0 +1 @@\n+y=2\n'
    with pytest.raises(ValueError): run_review(tmp_path,diff,ReviewPolicy(max_changed_files=1))

def test_review_id_deterministic(tmp_path):
    assert run_review(tmp_path,'')['review_id']==run_review(tmp_path,'')['review_id']

def test_audit_log_append(tmp_path):
    report=run_review(tmp_path,'')
    path=tmp_path/'audit'/'events.jsonl'
    write_audit_event(path,report,'reviewed')
    write_audit_event(path,report,'reviewed')
    rows=[json.loads(x) for x in path.read_text().splitlines()]
    assert len(rows)==2 and all(x['review_id']==report['review_id'] for x in rows)
