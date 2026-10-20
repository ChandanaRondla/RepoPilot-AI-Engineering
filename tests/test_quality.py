import pytest
from repopilot.quality import evaluate

def case(code, rules):
    return {'diff': '+++ b/app.py\n@@ -0,0 +1 @@\n+'+code+'\n', 'expected_rules': rules}

def test_empty():
    result=evaluate([])
    assert result['cases']==0 and result['f1']==0

def test_perfect():
    result=evaluate([case('eval(x)', ['unsafe-eval']),case('x = 1',[])])
    assert result['precision']==1 and result['recall']==1 and result['exact_match_cases']==2

def test_false_positive():
    result=evaluate([case('eval(x)',[])])
    assert result['false_positives']==1 and result['precision']==0

def test_false_negative():
    result=evaluate([case('x=1',['unsafe-eval'])])
    assert result['false_negatives']==1 and result['recall']==0

@pytest.mark.parametrize('code,rule', [('eval(x)','unsafe-eval'),('except:','unbounded-except'),('print(1)','debug-print'),('os.system(x)','shell-execution')])
def test_individual_rules(code,rule):
    result=evaluate([case(code,[rule])])
    assert result['true_positives']==1

@pytest.mark.parametrize('code', ['x=1','value = 3','def add(a,b):','return 5','# eval(x)','printable = True'])
def test_clean_cases(code):
    result=evaluate([case(code,[])])
    assert result['exact_match_rate']==1
