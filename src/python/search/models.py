from pydantic import BaseModel


class SearchResult(BaseModel):
    content: str
    source_type: str
    source_file: str
    category: str | None = None
    cmg_number: str | None = None
    chunk_type: str | None = None
    relevance_score: float
