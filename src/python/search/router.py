from __future__ import annotations

from fastapi import APIRouter, HTTPException

from quiz.retriever import Retriever, get_retriever as get_shared_retriever
from .models import SearchResult

router = APIRouter(prefix="/search", tags=["search"])

_retriever: Retriever | None = None


def _get_retriever() -> Retriever:
    global _retriever
    if _retriever is None:
        _retriever = get_shared_retriever()
    return _retriever


@router.get("")
def search(q: str = "") -> list[dict]:
    if not q.strip():
        raise HTTPException(status_code=400, detail="Query parameter 'q' is required")

    retriever = _get_retriever()
    chunks = retriever.retrieve(query=q, n=10)
    results = [
        SearchResult(
            content=c.content,
            source_type=c.source_type,
            source_file=c.source_file,
            category=c.category,
            cmg_number=c.cmg_number,
            chunk_type=c.chunk_type,
            relevance_score=c.relevance_score,
        )
        for c in chunks
    ]
    return [r.model_dump() for r in results]
