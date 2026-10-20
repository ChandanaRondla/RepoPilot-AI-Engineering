"""Optional local API: pip install -e '.[api]' and uvicorn repopilot.api:app."""
from pathlib import Path
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from .core import analyze, retrieve

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
