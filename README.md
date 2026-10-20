# RepoPilot — Repository-Aware PR Review & Test Proposal Assistant

A runnable, auditable **prototype** of an AI engineering productivity workflow. It indexes local source files into cited line-range chunks, retrieves relevant repository context, reviews unified diffs for a small set of deterministic risks, and proposes **review-required** pytest test skeletons for newly added Python functions.

> **Accuracy note:** By default it does **not** call an LLM. An **opt-in** model-assisted review adapter is included, but was not exercised against a live API here. The project does not run multi-agent orchestration, generate complete passing tests, or automatically review GitHub pull requests. It is a functional foundation for those features, not a claim of production agent deployment. The retrieval is lexical, not embedding-based. Generated test skeletons use `pytest.skip` until a developer adds real inputs and assertions.

## Quick start

Python 3.10+ required.

```bash
python -m pip install -e '.[test]'
pytest -q
repopilot --repo . search 'pull request review security'
repopilot --repo . review --diff-file examples/sample.patch --output report.json
```

Review current working-tree changes in a Git repository:

```bash
repopilot --repo /path/to/repo review --base HEAD
```

Optional local HTTP API:

```bash
python -m pip install -e '.[api]'
uvicorn repopilot.api:app --host 127.0.0.1 --port 8000
```

POST `/search` with `{"repo":"/absolute/path", "question":"where is authentication handled?"}`; POST `/review` with `{"repo":"/absolute/path", "diff":"<unified diff>"}`.

## Optional model-assisted review

Set `OPENAI_API_KEY` in your environment and explicitly enable the model adapter:

```bash
export OPENAI_API_KEY="your-api-key"  # do not commit this value
repopilot --repo . review --diff-file examples/sample.patch --llm --model gpt-4o-mini
```

This sends the diff and a bounded set of repository snippets to the configured model endpoint, so **do not enable it on confidential repositories without approval**. Model findings are advisory, never auto-applied. No API call was made during local verification.

## Architecture

```
Local repository -> safe file scanner -> line-numbered chunks -> lexical context retrieval
                                                        |
Unified diff -> added-line parser -> deterministic checks + new function detection
                                                        |
                                      JSON findings + context + skipped test proposals
                                                        |
                                        human review before any change is applied
```

## Guardrails

- Read-only review; no automated file writes except explicit CLI `--output` report.
- No shell interpolation; Git invocation uses argument lists and validates base ref.
- Ignores symlinks, build/cache/vendor folders, unsupported formats, and files >150 KB.
- Findings cite changed file and line, with severity and remediation.
- **No test claims are invented:** generated tests are intentionally skipped pending human assertions.
- Do not point the optional local API at untrusted repositories or expose it publicly; add authentication and workspace isolation first.

## Roadmap to a genuine agentic system

1. Strengthen the opt-in LLM adapter with schema validation, prompt-injection evaluations, cost accounting, model/version logging, and token budgets.
2. Add AST-aware retrieval, embedding-based ranking, and repository-scoped citations.
3. Add a test-authoring agent that proposes runnable assertions in a sandbox, with human approval before applying patches.
4. Add GitHub App integration for PR webhooks, least-privilege credentials, idempotent job queues, and review comment publishing.
5. Add a CI evaluation harness tracking finding precision, test validity, false positives, p95 latency, and cost per review.

## Suggested resume wording (accurate to this version)

**RepoPilot — Repository-Aware PR Review & Test Proposal Assistant** | Python, pytest, FastAPI (optional)
- Built a local repository context retrieval and PR diff analysis toolkit with file/line citations, deterministic risk checks, and JSON review reports.
- Implemented Python function detection and human-reviewed pytest test proposals, with automated tests validating retrieval, diff parsing, and review behavior.

## Reproducible benchmark (synthetic, October 2026)

Run from the project root:

```bash
PYTHONPATH=. python benchmarks/run_benchmark.py --cases 400 --seed 42
```

The benchmark generates 400 labeled **synthetic** unified diffs, including planted rule violations, clean code, and misleading comments/strings. It evaluates deterministic findings at the **rule-per-patch** level (not per-line or per real-world security vulnerability), validates Python syntax of generated pytest proposals, and measures local wall-clock analysis latency. The fixed cases are generated in code; no external GitHub PR corpus is used.

Measured on the local execution environment with seed 42:

| Metric | Result | Scope |
|---|---:|---|
| Precision | 81.97% | 300 true positives / (300 + 66 false positives) |
| Recall | 100% | 300 of 300 planted pattern labels found; not generalizable |
| p95 latency | 0.157 ms | In-process deterministic `analyze()` on tiny diffs; excludes git, network, model API, CI |
| Proposed pytest files | 134 | 134/134 syntax-valid; 0 contain runnable behavioral assertions |
| Human time saved | Not measured | Requires controlled human baseline |

Detailed outputs: `benchmarks/results/summary.json` and `benchmarks/results/case_results.csv`.

**Known limitations:** Generated positive examples match the tool's existing patterns and thus inflate recall. Some clean `eval` references in comments or strings, and safe subprocess calls, create false positives. The benchmark does not test LLM quality, live API latency, test pass rates, end-to-end GitHub PR integration, or production scale. A real-world held-out labeled PR dataset is required before claiming generalization.

## Updated benchmark and executable test generation

The 400-case synthetic benchmark now reports **300 TP, 0 FP, 0 FN**, with **0.5101 ms p95** local deterministic review latency. This is an in-sample, pattern-specific result and should not be presented as real-world accuracy. See `benchmarks/BENCHMARK_REPORT.md` and `benchmarks/results/summary.json`.

For a zero-argument function with a single literal return, RepoPilot generates an executable pytest assertion; an integration test writes and runs that generated test. For functions without a safely inferable contract, proposals explicitly skip pending developer review. Run `python -m pytest -q` to verify the suite.

## Expanded engineering platform (v0.2 prototype)

Additional tested modules:

- `repopilot/workflow.py`: configurable severity gates, approval-required status,
  deterministic review identifiers, and JSONL audit events.
- `repopilot/quality.py`: labeled-case precision, recall, F1, and per-rule confusion counts.
- `repopilot/test_runner.py`: explicit-trust pytest runner with path validation,
  timeout and captured output. **This is not a sandbox.** Never execute code
  from untrusted pull requests on a host machine; use an isolated CI worker.
- `.github/workflows/ci.yml`: test matrix for Python 3.10–3.13.

Example commands:

```bash
python -m pip install -e '.[test]'
python -m pytest -q tests
repopilot --repo . gate --diff-file examples/sample.patch --block-at high
repopilot --repo . test --trusted --target tests
repopilot --repo . evaluate benchmarks/labeled_cases.json
```

The `gate` command reports status; it does not deploy code or update a GitHub
check. Approval is recorded via the Python `approve()` API and does not provide
identity verification. The LLM integration remains optional and is not included
in the offline test suite. No claims are made about production deployments,
security guarantees, real-world review precision, or engineering time savings.

## Advanced integrations (October 2026)

- `repopilot.agents.orchestrate`: role-based review/specialist/gate orchestration, injectable specialist functions and fail-closed gate on failures. This is **not** autonomous multi-LLM orchestration.
- `repopilot.github_integration`: GitHub REST pull-request diff fetch and PR comment adapter; comments are **dry-run by default** and require an explicit token and `dry_run=False` to publish. Live GitHub API calls have not been tested.
- `repopilot.sandbox.run_isolated_pytest`: Docker-based runner with network disabled, read-only root, resource limits, and privilege restrictions. Requires Docker and an image with pytest installed; Docker was unavailable in the build environment, so execution was not end-to-end validated. Use disposable VMs for untrusted code.
- **85 local pytest tests passed**, including input validation, orchestration failure handling, and GitHub dry-run behavior.

The benchmark is synthetic and should not be represented as real-world PR detection accuracy.

## Versioned repository context (RepoPilot 2.0 — Phase 1)

The original `/search` endpoint remains available. A new context layer supports
content-addressed repository snapshots, file/line provenance, and optional
embedding-based semantic search using SentenceTransformers + FAISS.

Install the API and (optionally) semantic retrieval dependencies:

```bash
pip install -e '.[api,test]'
# For embeddings and FAISS (downloads a model on first use):
pip install -e '.[rag]'
uvicorn repopilot.api:app --reload
```

Index a trusted local repository using `POST /context/index`:

```json
{"repo":"/absolute/path/to/repo", "index_dir":"/absolute/path/to/indexes", "semantic":false}
```

The response contains a `snapshot` identifier. Set `semantic` to `true` to
build a FAISS vector index. Search it with `POST /context/query`:

```json
{"index_dir":"/absolute/path/to/indexes", "snapshot":"<snapshot from index response>", "question":"Where are retries handled?", "limit":5}
```

Each hit includes its source file, line range, score, and a citation suitable
for grounded LLM prompts. The index endpoint is intended for **trusted local
use only**: do not expose arbitrary filesystem paths to untrusted callers.
This release does not yet implement an LLM answer generator, authentication,
production deployment, or multi-agent orchestration over this index.


## Engineering evaluation and architecture

See [ENGINEERING_REPORT.md](ENGINEERING_REPORT.md) for architecture, benchmark results, testing, incident-analysis safeguards, and limitations.
