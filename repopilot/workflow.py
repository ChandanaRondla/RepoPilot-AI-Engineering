"""Deterministic, auditable human-in-the-loop review orchestration."""
from __future__ import annotations
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
import json
from typing import Any
from .core import analyze

SEVERITY = {'low': 1, 'medium': 2, 'high': 3, 'critical': 4}

@dataclass(frozen=True)
class ReviewPolicy:
    block_at: str = 'high'
    require_approval: bool = True
    max_changed_files: int = 200
    max_diff_bytes: int = 2_000_000

    def __post_init__(self):
        if self.block_at not in SEVERITY or self.max_changed_files < 1 or self.max_diff_bytes < 1:
            raise ValueError('Invalid review policy')


def run_review(root: Path, diff: str, policy: ReviewPolicy | None = None) -> dict[str, Any]:
    policy = policy or ReviewPolicy()
    if len(diff.encode('utf-8')) > policy.max_diff_bytes:
        raise ValueError('Diff exceeds configured size limit')
    report = analyze(root, diff)
    if len(report['changed_files']) > policy.max_changed_files:
        raise ValueError('Too many changed files')
    blockers = [f for f in report['findings'] if SEVERITY.get(f['severity'], 0) >= SEVERITY[policy.block_at]]
    report['policy'] = asdict(policy)
    report['blocking_findings'] = len(blockers)
    report['review_id'] = sha256(diff.encode('utf-8')).hexdigest()[:20]
    report['status'] = 'blocked' if blockers else ('approval_required' if policy.require_approval else 'passed')
    return report


def approve(report: dict[str, Any], reviewer: str, reason: str = '') -> dict[str, Any]:
    if report.get('status') != 'approval_required':
        raise ValueError('Only reviews awaiting approval can be approved')
    if not reviewer.strip():
        raise ValueError('Reviewer identity is required')
    approved = dict(report)
    approved['status'] = 'approved'
    approved['approval'] = {'reviewer': reviewer.strip(), 'reason': reason, 'timestamp_utc': datetime.now(timezone.utc).isoformat()}
    return approved


def write_audit_event(path: Path, report: dict[str, Any], action: str) -> None:
    """Append one JSONL event; caller controls destination; no secrets in event."""
    event = {'review_id': report.get('review_id'), 'action': action, 'status': report.get('status'),
             'timestamp_utc': datetime.now(timezone.utc).isoformat(), 'blocking_findings': report.get('blocking_findings', 0)}
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a', encoding='utf-8') as f:
        f.write(json.dumps(event, sort_keys=True) + '\n')
