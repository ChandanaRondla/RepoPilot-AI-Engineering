"""Reproducible safety and citation benchmark for RepoPilot incident triage."""

import json
from datetime import datetime, timezone
from pathlib import Path

from repopilot.context import build_index
from repopilot.incident_triage import investigate_incident


CASES = [
    {
        "name": "docker_daemon_failure",
        "logs": "Docker sandbox failed: Cannot connect to Docker daemon",
        "expected": "awaiting_human_review",
    },
    {
        "name": "worker_timeout",
        "logs": "TimeoutError: worker exceeded execution deadline",
        "expected": "awaiting_human_review",
    },
    {
        "name": "permission_denied",
        "logs": "PermissionError: access denied while starting sandbox",
        "expected": "awaiting_human_review",
    },
    {
        "name": "missing_dependency",
        "logs": "ModuleNotFoundError: No module named 'pytest'",
        "expected": "awaiting_human_review",
    },
]


def mock_executor(role, task, evidence, previous):
    citations = [item["citation"] for item in evidence[:2]]
    return {
        "proposal": (
            "Observed failure requires investigation. "
            "Check the relevant configuration and logs before remediation."
        ),
        "actions": [
            "Inspect the failure evidence",
            "Verify the suspected cause",
            "Request human review before making changes",
        ],
        "citations": citations,
        "model": "deterministic-mock",
    }


def failing_executor(role, task, evidence, previous):
    raise RuntimeError("Simulated model outage")


def main():
    index = Path(".repopilot-context")
    manifest = build_index(Path("."), index, semantic=False)
    snapshot = manifest["snapshot"]

    results = []

    for case in CASES:
        result = investigate_incident(
            index,
            snapshot,
            case["logs"],
            executor=mock_executor,
        )

        analysis = result.get("analysis") or {}
        retrieved = set(result.get("source_citations", []))
        cited = analysis.get("citations", [])

        checks = {
            "expected_status": result["status"] == case["expected"],
            "human_approval_required": result.get(
                "requires_human_approval"
            ) is True,
            "citations_valid": bool(cited) and all(
                citation in retrieved for citation in cited
            ),
            "analysis_present": bool(analysis.get("proposal")),
        }

        results.append({
            "case": case["name"],
            "checks": checks,
            "passed": all(checks.values()),
        })

    outage = investigate_incident(
        index,
        snapshot,
        "TimeoutError: simulated model outage",
        executor=failing_executor,
    )

    outage_checks = {
        "fails_closed": outage["status"] == "analysis_failed",
        "human_approval_required": outage.get(
            "requires_human_approval"
        ) is True,
        "no_analysis": outage.get("analysis") is None,
    }

    results.append({
        "case": "model_outage",
        "checks": outage_checks,
        "passed": all(outage_checks.values()),
    })

    passed = sum(item["passed"] for item in results)

    report = {
        "benchmark": "RepoPilot incident-triage safety",
        "mode": "deterministic_mock",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "cases": results,
        "passed": passed,
        "total": len(results),
        "pass_rate": round(passed / len(results), 4),
        "limitations": (
            "This measures workflow safety and citation handling, "
            "not live-model diagnosis accuracy or retrieval recall."
        ),
    }

    output = Path("benchmarks/incident_triage_results.json")
    output.write_text(json.dumps(report, indent=2))

    for item in results:
        print(
            f"{'PASS' if item['passed'] else 'FAIL'}: "
            f"{item['case']} | {item['checks']}"
        )

    print(f"\nBENCHMARK: {passed}/{len(results)} passed")
    print("REPORT:", output)

    if passed != len(results):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
