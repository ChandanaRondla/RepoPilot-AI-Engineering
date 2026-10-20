"""Optional local API: pip install -e '.[api]' and uvicorn repopilot.api:app."""
from pathlib import Path
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from .core import analyze, retrieve
from .context import build_index, query_index, grounded_context

app = FastAPI(title='RepoPilot AI Engineering Assistant', version='0.1.0')

class SearchRequest(BaseModel):
    repo: str
    question: str
    limit: int = 5

class ReviewRequest(BaseModel):
    repo: str
    diff: str

@app.post('/search')
def search(request: SearchRequest):
    try:
        return {'results': retrieve(Path(request.repo), request.question, request.limit)}
    except (ValueError, OSError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

@app.post('/review')
def review(request: ReviewRequest):
    try:
        return analyze(Path(request.repo), request.diff)
    except (ValueError, OSError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

class IndexRequest(BaseModel):
    repo: str
    index_dir: str
    semantic: bool = False

class ContextRequest(BaseModel):
    index_dir: str
    snapshot: str
    question: str
    limit: int = 5

@app.post('/context/index')
def context_index(request: IndexRequest):
    try:
        return build_index(Path(request.repo), Path(request.index_dir), semantic=request.semantic)
    except (ValueError, OSError, RuntimeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

@app.post('/context/query')
def context_query(request: ContextRequest):
    try:
        results = query_index(Path(request.index_dir), request.snapshot, request.question, request.limit)
        return {'results': results, 'grounded_context': grounded_context(results)}
    except (ValueError, OSError, RuntimeError, KeyError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
