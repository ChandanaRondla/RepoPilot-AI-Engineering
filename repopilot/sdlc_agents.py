"""Auditable, proposal-only SDLC agent workflow with explicit approval gates.

Agents here are deterministic role executors, not autonomous LLM agents.
They never write to the repository or execute generated code.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable
import hashlib
import json
import time

from .context import query_index


@dataclass(frozen=True)
class AgentTask:
    role: str
    instructions: str
    depends_on: tuple[str, ...] = ()


TASKS = (
    AgentTask('implementation', 'Produce an implementation plan with grounded source references'),
    AgentTask('testing', 'Propose positive, negative, and regression tests', ('implementation',)),
    AgentTask('documentation', 'Propose documentation updates', ('implementation',)),
    AgentTask('review', 'Review proposals for evidence and missing checks', ('testing', 'documentation')),
)


def _default_executor(role: str, request: str, evidence: list[dict[str, Any]], previous: dict[str, Any]) -> dict[str, Any]:
    citations = [item['citation'] for item in evidence]
    if role == 'implementation':
        return {'proposal': f'Plan changes for: {request}', 'citations': citations, 'actions': ['Inspect cited code', 'Implement minimal change', 'Review compatibility']}
    if role == 'testing':
        return {'proposal': 'Add positive, negative, and regression test cases', 'citations': citations, 'actions': ['Unit tests', 'Failure-path tests', 'Regression tests']}
    if role == 'documentation':
        return {'proposal': 'Update developer documentation and examples', 'citations': citations, 'actions': ['Document behavior', 'Add usage example']}
    return {'proposal': 'Human review required before any code changes', 'citations': citations, 'actions': ['Check source grounding', 'Review tests', 'Approve or reject']}


def run_sdlc_workflow(index_dir: Path, snapshot: str, request: str, *,
                      executor: Callable[[str, str, list[dict[str, Any]], dict[str, Any]], dict[str, Any]] | None = None,
                      max_retries: int = 1, limit: int = 4) -> dict[str, Any]:
    """Execute dependency-ordered role proposals; never change repository files.

    A supplied executor can connect an external model, but all outputs remain
    untrusted proposals and require explicit human approval outside this function.
    """
    if not isinstance(request, str) or not request.strip():
        raise ValueError('A nonempty request is required')
    if max_retries < 0 or max_retries > 3:
        raise ValueError('max_retries must be between 0 and 3')
    if limit < 1 or limit > 20:
        raise ValueError('limit must be between 1 and 20')
    evidence = query_index(index_dir, snapshot, request, limit=limit)
    task_id = hashlib.sha256(json.dumps({'snapshot': snapshot, 'request': request}, sort_keys=True).encode()).hexdigest()[:16]
    previous: dict[str, Any] = {}
    traces: list[dict[str, Any]] = []
    execute = executor or _default_executor
    for task in TASKS:
        if any(dep not in previous for dep in task.depends_on):
            traces.append({'role': task.role, 'status': 'skipped', 'reason': 'dependency_failed', 'attempts': 0})
            continue
        output = None
        last_error = None
        for attempt in range(1, max_retries + 2):
            started = time.monotonic()
            try:
                candidate = execute(task.role, request, evidence, dict(previous))
                if not isinstance(candidate, dict) or not isinstance(candidate.get('proposal'), str) or not candidate['proposal'].strip():
                    raise ValueError('Agent output must contain a nonempty proposal')
                output = candidate
                traces.append({'role': task.role, 'status': 'completed', 'attempts': attempt,
                               'duration_ms': round((time.monotonic() - started) * 1000, 3)})
                break
            except Exception as exc:
                last_error = type(exc).__name__
        if output is None:
            traces.append({'role': task.role, 'status': 'failed', 'attempts': max_retries + 1, 'error': last_error})
        else:
            previous[task.role] = output
    complete = len(previous) == len(TASKS)
    return {'workflow_id': task_id, 'snapshot': snapshot, 'status': 'awaiting_human_approval' if complete else 'blocked',
            'approval_required': True, 'approved': False, 'changes_applied': False,
            'source_citations': [item['citation'] for item in evidence],
            'proposals': previous, 'trace': traces}
