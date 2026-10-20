# RepoPilot benchmark — updated

400 generated synthetic PR diffs, seed 42. Deterministic rules only; no live LLM evaluation.

| Metric | Previous | Updated |
|---|---:|---:|
| True positives | 300 | 300 |
| False positives | 66 | 0 |
| False negatives | 0 | 0 |
| Precision | 82.0% | 100% |
| Recall | 100% | 100% |
| p95 local latency | 0.157 ms | 0.5101 ms |

The updated result is specific to the five seeded patterns and six negative traps in the synthetic dataset. It is **not** evidence of perfect accuracy on real pull requests. The rules were tuned to the same benchmark; evaluation on a held-out, independently labeled dataset is needed.

## Executable tests

RepoPilot now derives executable pytest assertions for a constrained case: a zero-argument, undecorated Python function whose sole statement returns a literal. An integration test writes the generated file and invokes pytest in a subprocess, verifying it passes. Other functions produce explicit `pytest.skip` placeholders rather than invented assertions. In the 400-case synthetic review benchmark, none of the 134 proposals had an available source-file contract, so the benchmark's count of executable proposals remains zero. The integration test independently demonstrates executable generation.

Human time savings have not been measured. The benchmark measures local static review, not end-to-end PR review or live LLM performance.
