from __future__ import annotations

import threading
from pathlib import Path

import chromadb

from paths import CHROMA_DB_DIR

from .models import RetrievedChunk

SOURCE_RANK = {
    "cmg": 0,
    "ref_doc": 1,
    "cpd_doc": 2,
    "notability_note": 3,
}
_shared_retriever: "Retriever | None" = None
_retriever_lock = threading.Lock()


def _matches_excluded_category(chunk: RetrievedChunk, exclude: list[str]) -> bool:
    cat_str = (chunk.category or "").lower()
    if not cat_str:
        return False
    cats = [c.strip().lower() for c in cat_str.split(",")]
    for ex in exclude:
        if ex.lower() in cats:
            return True
    return False


class Retriever:
    def __init__(
        self,
        db_path: str | Path | None = None,
        client: chromadb.ClientAPI | chromadb.PersistentClient | None = None,
    ):
        if client is not None:
            self._client = client
        else:
            self._client = chromadb.PersistentClient(path=str(db_path or CHROMA_DB_DIR))
        self._notes = self._client.get_or_create_collection(
            "paramedic_notes", metadata={"hnsw:space": "cosine"}
        )
        self._cmgs = self._client.get_or_create_collection("cmg_guidelines")

    def retrieve(
        self,
        query: str,
        n: int = 5,
        filters: dict | None = None,
        exclude_categories: list[str] | None = None,
        skill_level: str = "AP",
    ) -> list[RetrievedChunk]:
        all_chunks: list[RetrievedChunk] = []

        notes_where = self._build_where(
            filters, exclude_categories, collection="notes", skill_level=skill_level
        )
        cmgs_where = self._build_where(
            filters, exclude_categories, collection="cmgs", skill_level=skill_level
        )

        notes_results = self._safe_query(self._notes, query, n * 2, notes_where)
        all_chunks.extend(self._parse_results(notes_results, "notes"))

        cmgs_results = self._safe_query(self._cmgs, query, n, cmgs_where)
        all_chunks.extend(self._parse_results(cmgs_results, "cmgs"))

        if exclude_categories:
            all_chunks = [
                c
                for c in all_chunks
                if not _matches_excluded_category(c, exclude_categories)
            ]

        all_chunks.sort(key=lambda c: (c.source_rank, -c.relevance_score))
        return all_chunks[:n]

    def _build_where(
        self,
        base_filters: dict | None,
        exclude: list[str] | None,
        collection: str,
        skill_level: str = "AP",
    ) -> dict | None:
        conditions: list[dict] = []

        if base_filters:
            for key, value in base_filters.items():
                if collection == "notes" and key == "section":
                    continue
                conditions.append({key: value})

        if exclude:
            if collection == "notes":
                pass
            else:
                for cat in exclude:
                    conditions.append({"section": {"$nin": [cat]}})

        if collection in ("cmgs", "notes") and skill_level == "AP":
            conditions.append({"visibility": {"$in": ["both", "ap"]}})
        elif collection in ("cmgs", "notes") and skill_level == "ICP":
            conditions.append({"visibility": {"$in": ["both", "icp"]}})

        if not conditions:
            return None
        if len(conditions) == 1:
            return conditions[0]
        return {"$and": conditions}

    def _safe_query(self, collection, query: str, n: int, where: dict | None) -> dict:
        try:
            return collection.query(
                query_texts=[query], n_results=n, where=where or None
            )
        except Exception:
            return {"documents": [[]], "metadatas": [[]], "distances": [[]]}

    def _parse_results(self, raw: dict, collection: str) -> list[RetrievedChunk]:
        if not raw.get("documents") or not raw["documents"][0]:
            return []
        chunks: list[RetrievedChunk] = []
        for i, doc in enumerate(raw["documents"][0]):
            meta = raw["metadatas"][0][i]
            distance = (
                raw["distances"][0][i]
                if raw.get("distances") and raw["distances"][0]
                else 0.0
            )
            source_type = meta.get("source_type", "unknown")
            chunks.append(
                RetrievedChunk(
                    content=doc,
                    source_type=source_type,
                    source_file=meta.get("source_file", ""),
                    source_rank=SOURCE_RANK.get(source_type, 99),
                    category=meta.get("section") or meta.get("categories"),
                    cmg_number=meta.get("cmg_number"),
                    chunk_type=meta.get("chunk_type"),
                    relevance_score=-distance,
                )
            )
        return chunks


def get_retriever() -> Retriever:
    global _shared_retriever
    if _shared_retriever is None:
        with _retriever_lock:
            if _shared_retriever is None:
                _shared_retriever = Retriever()
    return _shared_retriever


def warm_retriever() -> Retriever:
    return get_retriever()
