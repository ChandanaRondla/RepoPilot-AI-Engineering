"""Versioned repository context index with optional semantic FAISS retrieval.

Install `pip install -e '.[rag]'` for sentence-transformer embeddings and FAISS.
No model weights or arbitrary pickle files are stored in the index.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from collections import Counter
from pathlib import Path
from typing import Any

from .core import chunks

TOKEN_RE = re.compile(r"[a-zA-Z_][a-zA-Z_0-9]{1,}")
INDEX_VERSION = 1
MODEL_NAME = 'sentence-transformers/all-MiniLM-L6-v2'


def _tokens(s: str) -> Counter[str]:
    return Counter(TOKEN_RE.findall(s.lower()))


def _cosine(a: Counter[str], b: Counter[str]) -> float:
    dot = sum(v * b.get(k, 0) for k, v in a.items())
    norm = math.sqrt(sum(v*v for v in a.values()) * sum(v*v for v in b.values()))
    return dot / norm if norm else 0.0


def _embed(texts: list[str]):
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError as exc:
        raise RuntimeError("Semantic indexing requires: pip install -e '.[rag]'") from exc
    model = SentenceTransformer(MODEL_NAME)
    return model.encode(texts, normalize_embeddings=True, convert_to_numpy=True)



def _rag_indexable(path: str) -> bool:
    """Exclude generated artifacts and benchmark data from repository RAG."""
    from pathlib import PurePosixPath

    relative = PurePosixPath(path)
    parts = relative.parts
    name = relative.name

    excluded_directories = {
        ".repopilot-context",
        ".git",
        ".venv",
        "__pycache__",
        ".pytest_cache",
        "dist",
        "build",
    }

    if any(part in excluded_directories for part in parts):
        return False

    if name in {
        "rag_eval_cases.json",
        "rag_eval_results.json",
        "incident_triage_results.json",
    }:
        return False

    if name.startswith("repopilot-") and name.endswith("-report.json"):
        return False

    if "benchmarks" in parts and relative.suffix == ".json":
        return False

    if "benchmarks" in parts and "results" in parts:
        return False

    return True


def build_index(repo: Path, destination: Path, *, semantic: bool = False) -> dict[str, Any]:
    """Build an immutable content-addressed snapshot under destination/<digest>."""
    repo = repo.resolve()
    docs = [
        doc for doc in chunks(repo)
        if _rag_indexable(doc["path"])
    ]
    payload = json.dumps(docs, sort_keys=True, ensure_ascii=False).encode('utf-8')
    digest = hashlib.sha256(payload).hexdigest()[:20]
    destination = destination.resolve()
    snapshot = destination / digest
    snapshot.mkdir(parents=True, exist_ok=True)
    manifest = {'schema_version': INDEX_VERSION, 'snapshot': digest,
                'mode': 'semantic' if semantic else 'lexical',
                'model': MODEL_NAME if semantic else None, 'chunk_count': len(docs)}
    if semantic and docs:
        try:
            import faiss
        except ImportError as exc:
            raise RuntimeError("FAISS indexing requires: pip install -e '.[rag]'") from exc
        vectors = _embed([d['content'] for d in docs])
        index = faiss.IndexFlatIP(vectors.shape[1])
        index.add(vectors)
        faiss.write_index(index, str(snapshot / 'vectors.faiss'))
    (snapshot / 'chunks.json').write_text(json.dumps(docs, ensure_ascii=False), encoding='utf-8')
    (snapshot / 'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    return manifest


def query_index(destination: Path, snapshot: str, question: str, limit: int = 5) -> list[dict[str, Any]]:
    """Return ranked context with source path and line-range provenance."""
    if not re.fullmatch(r'[a-f0-9]{20}', snapshot):
        raise ValueError('Invalid snapshot identifier')
    folder = destination.resolve() / snapshot
    manifest = json.loads((folder / 'manifest.json').read_text(encoding='utf-8'))
    docs = json.loads((folder / 'chunks.json').read_text(encoding='utf-8'))
    if manifest.get('schema_version') != INDEX_VERSION or manifest.get('snapshot') != snapshot:
        raise ValueError('Unsupported or inconsistent index manifest')
    limit = min(max(limit, 0), 50)
    if not question.strip() or not docs or not limit:
        return []
    if manifest['mode'] == 'semantic':
        try:
            import faiss
        except ImportError as exc:
            raise RuntimeError("FAISS search requires: pip install -e '.[rag]'") from exc
        index = faiss.read_index(str(folder / 'vectors.faiss'))
        distances, indices = index.search(_embed([question]), min(limit, len(docs)))
        hits = [(float(score), docs[int(idx)]) for score, idx in zip(distances[0], indices[0]) if idx >= 0]
    else:
        query_tokens = _tokens(question)
        hits = [(_cosine(query_tokens, _tokens(d['path'] + ' ' + d['content'])), d) for d in docs]
        hits = sorted((hit for hit in hits if hit[0] > 0), key=lambda x: (-x[0], x[1]['path'], x[1]['start_line']))[:limit]
    return [dict(doc, score=round(score, 6), snapshot=snapshot,
                 citation=f"{doc['path']}#L{doc['start_line']}-L{doc['end_line']}") for score, doc in hits]


def grounded_context(results: list[dict[str, Any]]) -> str:
    """Build cited context for an LLM; no unsupported answer generation."""
    return '\n\n'.join(f"SOURCE {r['citation']}\n{r['content']}" for r in results)


def hybrid_query_index(
    destination: Path,
    snapshot: str,
    question: str,
    limit: int = 5,
) -> list[dict[str, Any]]:
    """Hybrid lexical/semantic retrieval with implementation-aware ranking."""
    import faiss

    if not re.fullmatch(r"[a-f0-9]{20}", snapshot):
        raise ValueError("Invalid snapshot identifier")

    folder = destination.resolve() / snapshot
    manifest = json.loads(
        (folder / "manifest.json").read_text(encoding="utf-8")
    )
    docs = json.loads(
        (folder / "chunks.json").read_text(encoding="utf-8")
    )

    if manifest.get("schema_version") != INDEX_VERSION:
        raise ValueError("Unsupported index schema")
    if manifest.get("snapshot") != snapshot:
        raise ValueError("Inconsistent index manifest")

    limit = min(max(limit, 0), 50)
    if not question.strip() or not docs or not limit:
        return []

    tokens = _tokens(question)

    lexical = [
        (
            _cosine(tokens, _tokens(d["path"] + " " + d["content"])),
            i,
        )
        for i, d in enumerate(docs)
    ]
    lexical.sort(key=lambda item: (-item[0], item[1]))

    lexical_ranks = {
        i: rank
        for rank, (score, i) in enumerate(lexical, start=1)
        if score > 0
    }

    semantic_ranks = {}

    if manifest.get("mode") == "semantic":
        index = faiss.read_index(str(folder / "vectors.faiss"))
        _, indices = index.search(_embed([question]), len(docs))

        semantic_ranks = {
            int(i): rank
            for rank, i in enumerate(indices[0], start=1)
            if i >= 0
        }

    # Prefer implementation files only for implementation-location questions.
    question_lower = question.lower()
    implementation_query = any(
        phrase in question_lower
        for phrase in (
            "where is",
            "where are",
            "which module",
            "which file",
            "implemented",
            "implementation",
            "defined",
            "source code",
        )
    )

    ranked = []

    for i, doc in enumerate(docs):
        score = 0.0

        if i in lexical_ranks:
            score += 1.0 / (60 + lexical_ranks[i])

        if i in semantic_ranks:
            score += 1.0 / (60 + semantic_ranks[i])

        path = doc["path"].lower()

        if implementation_query:
            if path.startswith("repopilot/") and path.endswith(".py"):
                score *= 1.35
            elif path.startswith("tests/"):
                score *= 0.70
            elif path.endswith(".md"):
                score *= 0.65

        ranked.append((score, i, doc))

    ranked.sort(
        key=lambda item: (
            -item[0],
            item[2]["path"],
            item[2]["start_line"],
        )
    )

    results = []
    seen_files = set()

    for score, _, doc in ranked:
        if score <= 0 or doc["path"] in seen_files:
            continue

        seen_files.add(doc["path"])

        results.append(
            dict(
                doc,
                score=round(score, 6),
                snapshot=snapshot,
                citation=(
                    f"{doc['path']}#L"
                    f"{doc['start_line']}-L{doc['end_line']}"
                ),
            )
        )

        if len(results) >= limit:
            break

    return results
