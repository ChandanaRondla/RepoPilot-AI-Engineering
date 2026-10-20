"""Composable role-based review orchestration; no claim of autonomous LLM agents."""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Any
from .workflow import ReviewPolicy, run_review

@dataclass(frozen=True)
class AgentResult:
    role: str
    status: str
    output: dict[str, Any]


def orchestrate(root: Path, diff: str, *, policy: ReviewPolicy | None = None,
                specialists: dict[str, Callable[[Path, str], dict[str, Any]]] | None = None) -> dict[str, Any]:
    """Run reviewer, optional independently supplied specialist functions, then a gate.

    Specialists are injected explicitly; no external model calls are implied.
    """
    review = run_review(root, diff, policy)
    results = [AgentResult('reviewer', 'completed', {'findings': review['findings']})]
    for role, fn in (specialists or {}).items():
        if not role or role in {'reviewer', 'gate'}:
            raise ValueError('Invalid specialist role')
        try:
            output = fn(root, diff)
            if not isinstance(output, dict):
                raise TypeError('Specialist must return a dictionary')
            results.append(AgentResult(role, 'completed', output))
        except Exception as exc:
            results.append(AgentResult(role, 'failed', {'error': type(exc).__name__}))
    failed = any(result.status == 'failed' for result in results)
    status = 'blocked' if failed else review['status']
    results.append(AgentResult('gate', status, {'blocking_findings': review['blocking_findings']}))
    return {'review_id': review['review_id'], 'status': status,
            'steps': [{'role': r.role, 'status': r.status, 'output': r.output} for r in results]}
