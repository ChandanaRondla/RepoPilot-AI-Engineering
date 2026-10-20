# RepoPilot Phase 2: Auditable SDLC Role Orchestration

This upgrade adds `repopilot.sdlc_agents.run_sdlc_workflow`, a **proposal-only** coordinator for four roles: implementation, testing, documentation, and review. Roles share cited repository context from the Phase 1 index. Dependencies, bounded retries, per-role traces, and an explicit human approval gate are enforced. **It does not execute generated code, change files, deploy services, or call LLMs by default.**

## Local demo

```bash
python -m pytest -q
python - <<'PY'
from pathlib import Path
from repopilot.context import build_index
from repopilot.sdlc_agents import run_sdlc_workflow
index = Path('.repopilot-context')
manifest = build_index(Path('.'), index, semantic=False)
result = run_sdlc_workflow(index, manifest['snapshot'], 'Improve Docker sandbox error handling')
for step in result['trace']:
    print(step['role'], step['status'], step.get('attempts'))
print('Gate:', result['status'], 'Citations:', result['source_citations'][:3])
PY
```

For semantic retrieval, use `build_index(..., semantic=True)` after installing `.[rag]`. The executor injection point allows a future LLM adapter, but model outputs must be treated as untrusted and subjected to additional validation. The current workflow is sequential dependency-ordered coordination, **not parallel autonomous agents**.
