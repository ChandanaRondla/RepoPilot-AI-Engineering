# Phase 2B — Model-backed proposal agents

This is an **additive** upgrade for RepoPilot Phase 2. It does not modify existing files.

## Installation

From your existing `RepoPilot_AI_Engineering 2` directory:

```bash
unzip -n ~/Downloads/RepoPilot-Phase2B-Model-Agents-Additions.zip -d .
source .venv/bin/activate
python -m pytest -q
```

## Optional live LLM test

Set the API credentials for an OpenAI-compatible **HTTPS chat completions** provider. Do not commit API keys or put them into screenshots.

```bash
export REPOPILOT_MODEL='your-model-id'
export REPOPILOT_API_KEY='your-secret-key'
# Optional: export REPOPILOT_BASE_URL='https://your-provider.example/v1'
python - <<'PY'
from pathlib import Path
from repopilot.context import build_index
from repopilot.model_agents import ChatCompletionExecutor
from repopilot.sdlc_agents import run_sdlc_workflow
index = Path('.repopilot-context')
manifest = build_index(Path('.'), index, semantic=False)
result = run_sdlc_workflow(index, manifest['snapshot'], 'Improve Docker sandbox error handling',
                           executor=ChatCompletionExecutor.from_environment(), max_retries=1)
for item in result['trace']:
    print(item['role'], item['status'])
print(result['status'], 'approved:', result['approved'])
PY
```

**Safety and limitations:** This sends the task, retrieved repository snippets, and previous proposals to the configured provider. Use only code you are authorized to share. The model is not given write or execution tools; outputs are proposals requiring human approval. HTTP errors, invalid JSON, and invented citations fail closed. The live provider path is not verified by the mocked unit tests. This is not autonomous code implementation or a production deployment.
