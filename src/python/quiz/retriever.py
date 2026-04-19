from __future__ import annotations

import random
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
        service_id: str | None = None,
    ):
        if client is not None:
            self._client = client
        else:
            self._client = chromadb.PersistentClient(path=str(db_path or CHROMA_DB_DIR))
        if service_id is None:
            from services.active import active_service
            service_id = active_service().id
        self._service_id = service_id
        self._notes = self._client.get_or_create_collection(
            f"personal_{service_id}", metadata={"hnsw:space": "cosine"}
        )
        self._cmgs = self._client.get_or_create_collection(f"guidelines_{service_id}")

    def retrieve(
        self,
        query: str,
        n: int = 5,
        filters: dict | None = None,
        exclude_categories: list[str] | None = None,
        effective_qualifications: frozenset[str] | None = None,
        exclude_content_keys: set[str] | None = None,
        source_restriction: str | None = None,
        tracker=None,
    ) -> list[RetrievedChunk]:
        all_chunks: list[RetrievedChunk] = []

        # Only query notes collection when NOT restricted to CMGs
        if source_restriction != "cmg":
            notes_where = self._build_where(
                filters, exclude_categories, collection="notes",
                effective_qualifications=effective_qualifications,
            )
            notes_results = self._safe_query(self._notes, query, n * 4, notes_where)
            all_chunks.extend(self._parse_results(notes_results, "notes"))

        # Always query CMGs collection unless restricted to notes only
        if source_restriction is None or source_restriction == "cmg":
            cmgs_where = self._build_where(
                filters, exclude_categories, collection="cmgs",
                effective_qualifications=effective_qualifications,
            )
            cmgs_results = self._safe_query(self._cmgs, query, n * 4, cmgs_where)
            all_chunks.extend(self._parse_results(cmgs_results, "cmgs"))

        if exclude_categories:
            all_chunks = [
                c
                for c in all_chunks
                if not _matches_excluded_category(c, exclude_categories)
            ]

        # Filter out recently-used chunks (cross-session dedup)
        if exclude_content_keys:
            all_chunks = [
                c for c in all_chunks if c.content_key not in exclude_content_keys
            ]

        if tracker is not None:
            candidate_keys = {c.content_key for c in all_chunks}
            scores = tracker.get_chunk_scores(candidate_keys)
            scored = [
                (
                    c.relevance_score
                    + random.uniform(0, 0.05) * scores.get(c.content_key, 1.0),
                    c,
                )
                for c in all_chunks
            ]
            scored.sort(key=lambda t: t[0], reverse=True)
            all_chunks = [c for _, c in scored]
        else:
            random.shuffle(all_chunks)
        return all_chunks[:n]

    def _build_where(
        self,
        base_filters: dict | None,
        exclude: list[str] | None,
        collection: str,
        effective_qualifications: frozenset[str] | None = None,
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

        # Derive visibility filter from effective qualifications.
        # ICP users see all content; AP-only users see AP and shared content.
        if effective_qualifications is not None and collection in ("cmgs", "notes"):
            if "ICP" in effective_qualifications:
                conditions.append({"visibility": {"$in": ["both", "icp", "ap"]}})
            else:
                conditions.append({"visibility": {"$in": ["both", "ap"]}})

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

    def get_random_chunk(
        self,
        exclude_content_keys: set[str] | None = None,
        effective_qualifications: frozenset[str] | None = None,
    ) -> "RetrievedChunk | None":
        """Return a single uniformly random chunk from the combined corpus."""
        where_vis: dict | None = None
        if effective_qualifications is not None:
            if "ICP" in effective_qualifications:
                where_vis = {"visibility": {"$in": ["both", "icp", "ap"]}}
            else:
                where_vis = {"visibility": {"$in": ["both", "ap"]}}

        collections = [self._notes, self._cmgs]
        random.shuffle(collections)
        for col in collections:
            try:
                all_ids = col.get(where=where_vis, include=[])["ids"]
                if not all_ids:
                    continue
                chosen_id = random.choice(all_ids)
                result = col.get(ids=[chosen_id], include=["documents", "metadatas"])
                chunks = self._parse_results(
                    {
                        "documents": [result["documents"]],
                        "metadatas": [result["metadatas"]],
                        "distances": [[0.0]],
                    },
                    col.name,
                )
                if not chunks:
                    continue
                chunk = chunks[0]
                if exclude_content_keys and chunk.content_key in exclude_content_keys:
                    continue
                return chunk
            except Exception:
                continue
        return None

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
