"""Reproducible synthetic PR benchmark; no claims about real-world PR performance."""
from __future__ import annotations
import argparse, ast, csv, json, random, statistics, tempfile, time
from pathlib import Path
from repopilot.core import analyze, review_diff

RULES = {
 'hardcoded-secret': ('api_key = "sk_test_EXAMPLE_SECRET_123456"', 'token = os.environ.get("API_KEY")'),
 'unsafe-eval': ('result = eval(user_input)', 'result = ast.literal_eval(user_input)'),
 'shell-execution': ('result = subprocess.run(args, check=True)', 'result = execute_safe_command(args)'),
 'unbounded-except': ('except:', 'except ValueError:'),
 'debug-print': ('print("debug")', 'logger.debug("debug")'),
}
# This deliberately includes ambiguous code that will expose weaknesses in simplistic pattern matching.
NEGATIVE_TRAPS = [
 ('secret-env', 'password = ""'),
 ('eval-comment', '# never call eval(untrusted_input)'),
 ('eval-string', 'message = "avoid eval(x)"'),
 ('shell-comment', '# subprocess.run must be reviewed'),
 ('print-comment', '# print("debug") is discouraged'),
 ('shell-safe', 'subprocess.run(["echo", "ok"], shell=False, check=True)'),
]

def patch(path: str, lines: list[str]) -> str:
 return '\n'.join([f'diff --git a/{path} b/{path}', f'--- a/{path}', f'+++ b/{path}', f'@@ -0,0 +1,{len(lines)} @@', *('+'+line for line in lines)]) + '\n'

def cases(seed: int, n: int):
 rng = random.Random(seed)
 keys = list(RULES)
 for i in range(n):
  kind = i % 4
  rule = keys[(i // 4) % len(keys)]
  pos, neg = RULES[rule]
  if kind == 0: # single finding
   expected = {rule}; body = [pos]
  elif kind == 1: # clean code
   expected = set(); body = [neg]
  elif kind == 2: # multiple findings
   other = keys[(keys.index(rule)+1) % len(keys)]
   expected = {rule, other}; body = [pos, RULES[other][0]]
  else: # adversarial negatives, explicitly labeled as no *actionable* issue
   expected = set(); body = [NEGATIVE_TRAPS[(i//4) % len(NEGATIVE_TRAPS)][1]]
  rng.shuffle(body)
  path = f'src/module_{i:04d}.py'
  function = (i % 3 == 0)
  if function: body = [f'def feature_{i}(value):', '    return value'] + [('    '+s if not s.startswith(('except', '#')) else '    '+s) for s in body]
  yield {'id': f'SYN-{i:04d}', 'patch': patch(path, body), 'expected': expected, 'function': function, 'kind': kind}

def run(n=400, seed=42, output=None):
 if n < 20: raise ValueError('Use at least 20 cases')
 output = Path(output or Path(__file__).parent/'results')
 output.mkdir(parents=True, exist_ok=True)
 counts = {r: {'tp':0,'fp':0,'fn':0} for r in RULES}
 rows=[]; latency=[]; proposals_total=0; proposals_valid=0; proposal_executable=0
 with tempfile.TemporaryDirectory() as temp:
  root=Path(temp)
  for case in cases(seed,n):
   start=time.perf_counter_ns()
   report=analyze(root,case['patch'])
   ms=(time.perf_counter_ns()-start)/1e6
   latency.append(ms)
   predicted={f['rule'] for f in report['findings']}
   for r in RULES:
    counts[r]['tp']+=int(r in predicted and r in case['expected'])
    counts[r]['fp']+=int(r in predicted and r not in case['expected'])
    counts[r]['fn']+=int(r not in predicted and r in case['expected'])
   for p in report['test_proposals']:
    proposals_total+=1
    try:
     ast.parse(p['content'])
     proposals_valid+=1
     # Placeholder tests skip rather than test application behavior.
     if 'pytest.skip' not in p['content']: proposal_executable+=1
    except SyntaxError: pass
   rows.append({'id':case['id'],'type':case['kind'],'expected_rules':';'.join(sorted(case['expected'])), 'predicted_rules':';'.join(sorted(predicted)),'latency_ms':round(ms,5),'proposed_test_files':len(report['test_proposals'])})
 def metrics(c):
  tp,fp,fn=c['tp'],c['fp'],c['fn']
  return {'tp':tp,'fp':fp,'fn':fn,'precision':round(tp/(tp+fp),4) if tp+fp else None,'recall':round(tp/(tp+fn),4) if tp+fn else None}
 overall={k:sum(c[k] for c in counts.values()) for k in ('tp','fp','fn')}
 sorted_ms=sorted(latency)
 result={'benchmark':'RepoPilot deterministic rules on generated synthetic diffs','seed':seed,'cases':n,'note':'Synthetic labeled patches, not real-world GitHub PRs. Rule-level matching; no live LLM API.','overall':metrics(overall),'by_rule':{r:metrics(c) for r,c in counts.items()},'latency_ms':{'mean':round(statistics.mean(latency),4),'median':round(statistics.median(latency),4),'p95':round(sorted_ms[max(0,int(.95*n)-1)],4),'max':round(max(latency),4)},'test_proposals':{'files':proposals_total,'syntax_valid':proposals_valid,'with_real_assertions':proposal_executable,'note':'Proposed tests intentionally contain pytest.skip; syntax validity is not functional test success.'},'time_savings':{'measured':False,'note':'No paired human-review baseline was conducted; time saved cannot be responsibly quantified.'}}
 (output/'summary.json').write_text(json.dumps(result,indent=2)+'\n')
 with (output/'case_results.csv').open('w',newline='') as f:
  writer=csv.DictWriter(f,fieldnames=rows[0].keys());writer.writeheader();writer.writerows(rows)
 print(json.dumps(result,indent=2))
 return result

if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('--cases',type=int,default=400);parser.add_argument('--seed',type=int,default=42);parser.add_argument('--output'); args=parser.parse_args()
 run(args.cases,args.seed,args.output)
