import json
from unittest.mock import patch

from repopilot import context


def test_hybrid_prefers_implementation_for_location_question(tmp_path):
    snapshot = "a" * 20
    folder = tmp_path / snapshot
    folder.mkdir()

    docs = [
        {
            "path": "README.md",
            "start_line": 1,
            "end_line": 3,
            "content": "Docker sandbox execution implementation",
        },
        {
            "path": "tests/test_sandbox.py",
            "start_line": 1,
            "end_line": 3,
            "content": "Docker sandbox execution tests",
        },
        {
            "path": "repopilot/sandbox.py",
            "start_line": 1,
            "end_line": 3,
            "content": "Docker sandbox execution implementation",
        },
    ]

    (folder / "manifest.json").write_text(
        json.dumps({
            "schema_version": context.INDEX_VERSION,
            "snapshot": snapshot,
            "mode": "lexical",
        })
    )
    (folder / "chunks.json").write_text(json.dumps(docs))

    with patch.object(
        context,
        "_cosine",
        side_effect=[0.8, 0.8, 0.8],
    ):
        hits = context.hybrid_query_index(
            tmp_path,
            snapshot,
            "Where is Docker sandbox execution implemented?",
            limit=3,
        )

    assert hits[0]["path"] == "repopilot/sandbox.py"
    assert len({hit["path"] for hit in hits}) == len(hits)
    assert hits[0]["citation"] == "repopilot/sandbox.py#L1-L3"
