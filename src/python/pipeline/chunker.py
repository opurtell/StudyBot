"""Chunk cleaned markdown and ingest into ChromaDB.

Uses RecursiveCharacterTextSplitter (800 chars, 100 overlap) and
ChromaDB PersistentClient with collection 'paramedic_notes'.
"""

import re
from pathlib import Path

import chromadb
import yaml
from langchain_text_splitters import RecursiveCharacterTextSplitter

CHUNK_SIZE = 800
CHUNK_OVERLAP = 100
COLLECTION_NAME = "paramedic_notes"

_splitter = RecursiveCharacterTextSplitter(
    chunk_size=CHUNK_SIZE,
    chunk_overlap=CHUNK_OVERLAP,
    separators=["\n\n", "\n", ". ", " ", ""],
)


def sanitise_id(source_file: str) -> str:
    """Convert source_file path to a safe ChromaDB ID prefix."""
    return source_file.replace("/", "__").replace(" ", "_")


def chunk_and_ingest(md_path: Path, db_path: Path) -> dict:
    """Chunk a single cleaned .md file and ingest into ChromaDB.

    Deletes any existing chunks for this source_file before inserting
    (idempotent re-ingestion).

    Returns a result dict with chunk count and metadata.
    """
    content = md_path.read_text()
    parts = content.split("---\n", 2)
    meta = yaml.safe_load(parts[1])
    body = parts[2].strip()

    source_file = meta["source_file"]
    categories = meta.get("categories", [])
    review_flags = meta.get("review_flags", [])
    last_modified = meta.get("last_modified", "")

    # Chunk the body text
    chunks = _splitter.split_text(body)
    if not chunks:
        return {
            "success": True,
            "source_file": source_file,
            "chunk_count": 0,
        }

    # Connect to ChromaDB
    client = chromadb.PersistentClient(path=str(db_path))
    collection = client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )

    # Delete existing chunks for this source file (idempotent re-ingestion)
    id_prefix = sanitise_id(source_file)
    existing = collection.get(where={"source_file": source_file})
    if existing["ids"]:
        collection.delete(ids=existing["ids"])

    # Prepare chunk data
    ids = [f"{id_prefix}_chunk_{i:04d}" for i in range(len(chunks))]
    metadatas = [
        {
            "source_type": "notability_note",
            "source_file": source_file,
            "categories": ",".join(categories),
            "chunk_index": i,
            "last_modified": last_modified,
            "has_review_flag": bool(review_flags),
        }
        for i in range(len(chunks))
    ]

    collection.add(documents=chunks, ids=ids, metadatas=metadatas)

    return {
        "success": True,
        "source_file": source_file,
        "chunk_count": len(chunks),
        "categories": categories,
        "has_review_flag": bool(review_flags),
    }
