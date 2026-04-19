"""Header-aware chunking and ChromaDB ingestion for personal docs."""

import logging
from pathlib import Path

import chromadb
import yaml
from guidelines.markdown import has_icp_content, strip_icp_content
from langchain_text_splitters import (
    MarkdownHeaderTextSplitter,
    RecursiveCharacterTextSplitter,
)

COLLECTION_NAME = "paramedic_notes"
CHUNK_SIZE = 800
CHUNK_OVERLAP = 100

_HEADERS = [
    ("#", "h1"),
    ("##", "h2"),
    ("###", "h3"),
]

_md_header_splitter = MarkdownHeaderTextSplitter(
    headers_to_split_on=_HEADERS,
    return_each_line=False,
)

_text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=CHUNK_SIZE,
    chunk_overlap=CHUNK_OVERLAP,
    separators=["\n\n", "\n", ". ", " ", ""],
)


def _parse_front_matter(content: str) -> tuple[dict, str]:
    parts = content.split("---\n", 2)
    if len(parts) < 3:
        raise ValueError(
            f"Expected YAML front matter delimited by '---': got {len(parts) - 1} parts"
        )
    meta = yaml.safe_load(parts[1])
    body = parts[2].strip()
    return meta, body


def _sanitise_id(source_file: str) -> str:
    return source_file.replace("/", "__").replace(" ", "_")


def chunk_and_ingest(md_path: Path, db_path: Path, collection_name: str = COLLECTION_NAME) -> dict:
    content = md_path.read_text(encoding="utf-8")
    meta, body = _parse_front_matter(content)

    source_file = meta["source_file"]
    source_type = meta["source_type"]
    categories = meta.get("categories", [])
    last_modified = meta.get("last_modified", "")
    service = meta.get("service", "")
    scope = meta.get("scope", "")

    md_docs = _md_header_splitter.split_text(body)
    if not md_docs:
        chunks = _text_splitter.split_text(body)
        header_contexts = [""] * len(chunks)
    else:
        chunks = []
        header_contexts = []
        for doc in md_docs:
            header_parts = [v for v in doc.metadata.values() if v]
            header_ctx = " > ".join(header_parts)
            sub_chunks = _text_splitter.split_text(doc.page_content)
            for sc in sub_chunks:
                chunks.append(f"{header_ctx}\n\n{sc}" if header_ctx else sc)
                header_contexts.append(header_ctx)

    if not chunks:
        return {
            "success": True,
            "source_file": source_file,
            "chunk_count": 0,
            "source_type": source_type,
            "categories": categories,
        }

    client = chromadb.PersistentClient(path=str(db_path))
    collection = client.get_or_create_collection(
        name=collection_name,
        metadata={"hnsw:space": "cosine"},
    )

    id_prefix = _sanitise_id(source_file)
    existing = collection.get(where={"source_file": source_file})
    if existing["ids"]:
        collection.delete(ids=existing["ids"])

    ids = []
    documents = []
    metadatas = []
    for i, chunk_text in enumerate(chunks):
        chunk_has_icp = has_icp_content(chunk_text)
        if chunk_has_icp:
            ids.append(f"{id_prefix}_chunk_{i:04d}_icp")
            documents.append(chunk_text)
            metadatas.append(
                {
                    "source_type": source_type,
                    "source_file": source_file,
                    "categories": ",".join(categories)
                    if isinstance(categories, list)
                    else str(categories),
                    "chunk_index": i,
                    "last_modified": last_modified,
                    "header_context": header_contexts[i],
                    "visibility": "icp",
                    "service": service,
                    "scope": scope,
                }
            )
            stripped = strip_icp_content(chunk_text)
            if stripped:
                ids.append(f"{id_prefix}_chunk_{i:04d}_ap")
                documents.append(stripped)
                metadatas.append(
                    {
                        "source_type": source_type,
                        "source_file": source_file,
                        "categories": ",".join(categories)
                        if isinstance(categories, list)
                        else str(categories),
                        "chunk_index": i,
                        "last_modified": last_modified,
                        "header_context": header_contexts[i],
                        "visibility": "ap",
                        "service": service,
                        "scope": scope,
                    }
                )
        else:
            ids.append(f"{id_prefix}_chunk_{i:04d}")
            documents.append(chunk_text)
            metadatas.append(
                {
                    "source_type": source_type,
                    "source_file": source_file,
                    "categories": ",".join(categories)
                    if isinstance(categories, list)
                    else str(categories),
                    "chunk_index": i,
                    "last_modified": last_modified,
                    "header_context": header_contexts[i],
                    "visibility": "both",
                    "service": service,
                    "scope": scope,
                }
            )

    collection.add(documents=documents, ids=ids, metadatas=metadatas)

    return {
        "success": True,
        "source_file": source_file,
        "chunk_count": len(documents),
        "source_type": source_type,
        "categories": categories,
    }


def chunk_and_ingest_directory(structured_dir: Path, db_path: Path) -> dict:
    processed = 0
    errors = 0
    total_chunks = 0
    results = []

    for subdir in ["REFdocs", "CPDdocs"]:
        dir_path = structured_dir / subdir
        if not dir_path.exists():
            continue
        for md_file in sorted(dir_path.glob("*.md")):
            try:
                result = chunk_and_ingest(md_file, db_path)
                results.append(result)
                processed += 1
                total_chunks += result.get("chunk_count", 0)
                logging.getLogger(__name__).info(
                    f"Ingested: {result['source_file']} ({result.get('chunk_count', 0)} chunks)"
                )
            except Exception as e:
                logging.getLogger(__name__).error(f"Failed to ingest {md_file}: {e}")
                errors += 1

    return {
        "processed": processed,
        "errors": errors,
        "total_chunks": total_chunks,
        "results": results,
    }
