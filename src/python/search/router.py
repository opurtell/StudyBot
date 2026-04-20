from __future__ import annotations

from fastapi import APIRouter, HTTPException

from quiz.retriever import Retriever, get_retriever as get_shared_retriever
from seed import is_seeding_complete
from .models import SearchResult

router = APIRouter(prefix="/search", tags=["search"])

_retriever: Retriever | None = None


def _get_retriever() -> Retriever:
    global _retriever
    if _retriever is None:
        _retriever = get_shared_retriever()
    return _retriever


def reset_search_retriever() -> None:
    """Clear the local and shared retriever singletons."""
    global _retriever
    _retriever = None
    from quiz.retriever import reset_retriever
    reset_retriever()


def _check_seeding() -> None:
    if not is_seeding_complete():
        raise HTTPException(status_code=503, detail="CMG index is still seeding. Please try again in a moment.")


@router.get("")
def search(q: str = "") -> list[dict]:
    _check_seeding()
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
