"""Deterministic evaluation of labeled PR review examples."""
from __future__ import annotations
from collections import Counter
from statistics import mean
from typing import Any
from .core import review_diff


def evaluate(cases: list[dict[str, Any]]) -> dict[str, Any]:
    """Each case has diff and expected_rules (list of rule names)."""
    tp = fp = fn = 0
    per_rule: dict[str, Counter] = {}
    cases_correct = 0
    for case in cases:
        actual = {finding.rule for finding in review_diff(case['diff'])}
        expected = set(case['expected_rules'])
        cases_correct += actual == expected
        for rule in actual | expected:
            count = per_rule.setdefault(rule, Counter())
            if rule in actual and rule in expected:
                tp += 1; count['tp'] += 1
            elif rule in actual:
                fp += 1; count['fp'] += 1
            else:
                fn += 1; count['fn'] += 1
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    return {'cases': len(cases), 'exact_match_cases': cases_correct, 'exact_match_rate': cases_correct / len(cases) if cases else 0.0,
            'true_positives': tp, 'false_positives': fp, 'false_negatives': fn,
            'precision': precision, 'recall': recall,
            'f1': 2 * precision * recall / (precision + recall) if precision + recall else 0.0,
            'by_rule': {k: dict(v) for k, v in sorted(per_rule.items())}}
