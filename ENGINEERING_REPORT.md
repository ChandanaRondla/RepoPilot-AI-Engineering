# RepoPilot — Engineering Report

## Overview

RepoPilot is a repository-aware AI engineering prototype for code review, automated test proposals, retrieval-augmented analysis, and incident investigation.

It combines versioned repository context, hybrid retrieval, structured model outputs, and human-review safeguards.

## Architecture

Repository / Pull Request / Incident Logs
    |
    v
Versioned Repository Context
    - AST-aware code chunking
    - Snapshot-based indexing
    - File and line-range provenance
    |
    v
Retrieval Layer
    - Lexical search
    - FAISS semantic search
    - Hybrid reciprocal rank fusion
    - Implementation-aware ranking
    - File diversity
    |
    v
Engineering Workflows
    - Pull request review
    - Test proposals
    - SDLC agent proposals
    - Incident investigation
    |
    v
Validation and Human Review
    - Structured response validation
    - Citation validation
    - Human approval before remediation

## Retrieval Evaluation

The benchmark contains 10 labeled repository questions with file-level relevance judgments.

| Retrieval method | Recall@3 | Recall@5 | MRR@5 |
|---|---:|---:|---:|
| Lexical baseline | 0.30 | 0.40 | 0.2083 |
| Semantic baseline | 0.50 | 0.60 | 0.4250 |
| Original hybrid | 0.40 | 0.40 | 0.4000 |
| Implementation-aware hybrid | 0.60 | 0.70 | 0.4533 |

Implementation-aware hybrid ranking increased Recall@5 from 40% to 70% relative to the recorded original hybrid benchmark.

The ranking approach retains reciprocal rank fusion and source citations while applying a modest source-code preference to implementation-location questions.

### Limitations

- The benchmark contains only 10 repository-specific questions.
- Relevance is measured at the file level, not the passage level.
- Benchmark artifacts were produced at different development stages.
- Ranking weights have not been validated on a separate held-out dataset.
- Results do not establish generalization to unseen repositories.
- Valid source citations do not guarantee factual correctness.

## Incident Investigation

RepoPilot retrieves repository evidence and generates structured incident-analysis proposals.

The optional OpenAI-compatible model adapter validates proposals, recommended actions, and source citations.

Incident analysis requires human review and does not automatically execute remediation.

The adapter and integration tests use mocked API responses; these tests do not establish live model accuracy.

## Testing

Run: python -m pytest -q

Latest local verification: 195 tests passed.

Tests cover retrieval behavior, citation restrictions, model response validation, and incident-workflow integration.

## Reproducibility

Benchmark inputs and recorded results:

- benchmarks/rag_eval_cases.json
- benchmarks/rag_eval_results.json
- benchmarks/rag_hybrid_results.json
- benchmarks/rag_hybrid_improved_results.json

Semantic retrieval requires the optional SentenceTransformers and FAISS dependencies.

## Engineering Boundaries

RepoPilot is an engineering prototype, not a production-deployed autonomous software development system.

Model suggestions require human review. Automated test success does not guarantee model-generated recommendations are correct or safe.
