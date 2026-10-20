import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path

from repopilot.context import build_index, query_index

ROOT = Path(__file__).resolve().parents[1]
CASES = json.loads(
    (ROOT / "benchmarks/rag_eval_cases.json").read_text()
)
OUTPUT = ROOT / "benchmarks/rag_eval_results.json"


def evaluate_mode(mode):
    semantic = mode == "semantic"
    index_dir = ROOT / ".repopilot-context" / f"benchmark-{mode}"

    start = time.perf_counter()
    manifest = build_index(ROOT, index_dir, semantic=semantic)
    indexing_seconds = round(time.perf_counter() - start, 3)

    results = []
    for case in CASES:
        start = time.perf_counter()
        hits = query_index(
            index_dir,
            manifest["snapshot"],
            case["question"],
            limit=5,
        )
        query_seconds = round(time.perf_counter() - start, 4)

        relevant = set(case["relevant_files"])
        ranked_files = [hit["path"] for hit in hits]

        first_rank = next(
            (
                rank
                for rank, path in enumerate(ranked_files, start=1)
                if path in relevant
            ),
            None,
        )

        citation_valid = all(
            hit.get("citation")
            == f"{hit['path']}#L{hit['start_line']}-L{hit['end_line']}"
            and (ROOT / hit["path"]).is_file()
            and isinstance(hit["start_line"], int)
            and isinstance(hit["end_line"], int)
            and 1 <= hit["start_line"] <= hit["end_line"]
            <= len((ROOT / hit["path"]).read_text().splitlines())
            for hit in hits
        )

        results.append({
            "id": case["id"],
            "question": case["question"],
            "relevant_files": sorted(relevant),
            "retrieved_files": ranked_files,
            "first_relevant_rank": first_rank,
            "recall_at_3": int(
                bool(relevant.intersection(ranked_files[:3]))
            ),
            "recall_at_5": int(
                bool(relevant.intersection(ranked_files[:5]))
            ),
            "reciprocal_rank_at_5": (
                round(1 / first_rank, 4) if first_rank else 0
            ),
            "citation_valid": citation_valid,
            "query_seconds": query_seconds,
        })

    count = len(results)
    metrics = {
        "recall_at_3": round(
            sum(r["recall_at_3"] for r in results) / count, 4
        ),
        "recall_at_5": round(
            sum(r["recall_at_5"] for r in results) / count, 4
        ),
        "mrr_at_5": round(
            sum(r["reciprocal_rank_at_5"] for r in results) / count, 4
        ),
        "citation_validity": round(
            sum(r["citation_valid"] for r in results) / count, 4
        ),
        "avg_query_seconds": round(
            sum(r["query_seconds"] for r in results) / count, 4
        ),
        "indexing_seconds": indexing_seconds,
    }
    return {"metrics": metrics, "cases": results}


def main():
    report = {
        "benchmark": "RepoPilot RAG retrieval evaluation",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "evaluation_cases": len(CASES),
        "relevance_granularity": "file",
        "modes": {},
    }

    for mode in ("lexical", "semantic"):
        print(f"\nEvaluating {mode.upper()} retrieval...", flush=True)
        report["modes"][mode] = evaluate_mode(mode)
        print(
            json.dumps(report["modes"][mode]["metrics"], indent=2),
            flush=True,
        )

    OUTPUT.write_text(json.dumps(report, indent=2))
    print(f"\nSaved report: {OUTPUT}")


if __name__ == "__main__":
    main()
