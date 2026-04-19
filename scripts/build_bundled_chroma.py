#!/usr/bin/env python3
"""Build per-service ChromaDB trees for packaging.

For each registered service, creates a fresh ChromaDB instance and ingests
that service's structured data into a guidelines_<id> collection.

Run from the repo root. The output goes to build/resources/data/services/<id>/chroma/.

Usage:
    python3 scripts/build_bundled_chroma.py [--repo-root .]
"""

import argparse
import json
import logging
import os
import sys
from pathlib import Path

import chromadb

# Allow importing from src/python when run as a script
_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT / "src" / "python"))

from services.registry import REGISTRY, all_service_ids

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def _structured_source_dir(service_id: str, repo_root: Path) -> Path:
    """Locate the structured data source for a service.

    Checks data/services/<id>/structured/ first (new layout), then falls
    back to data/cmgs/structured/ for the legacy ACTAS layout.
    """
    new_path = repo_root / "data" / "services" / service_id / "structured"
    if new_path.is_dir() and any(new_path.glob("*.json")):
        return new_path

    # Legacy fallback: ACTAS data may still live under data/cmgs/structured/
    if service_id == "actas":
        legacy_path = repo_root / "data" / "cmgs" / "structured"
        if legacy_path.is_dir() and any(legacy_path.glob("*.json")):
            return legacy_path

    return new_path  # return anyway; will be empty


def _build_actas_chroma(structured_dir: Path, output_dir: Path) -> int:
    """Build ChromaDB for ACTAS using the ACTAS chunker.

    Returns the number of chunks ingested.
    """
    # The ACTAS chunker writes to a PersistentClient at db_path with
    # collection name "cmg_guidelines". We need to rename it to
    # "guidelines_actas", so we do the ingestion ourselves using the
    # same logic but with the correct collection name.
    from pipeline.actas.models import CMGGuideline
    from pipeline.actas.chunker import (
        determine_chunk_type,
        MAX_TOKENS,
        _dose_lookup_to_chunks,
    )
    from langchain_text_splitters import RecursiveCharacterTextSplitter
    from guidelines.markdown import has_icp_content, strip_icp_content

    output_dir.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(output_dir))

    collection_name = "guidelines_actas"
    try:
        client.delete_collection(collection_name)
    except Exception:
        pass

    collection = client.get_or_create_collection(
        collection_name, metadata={"hnsw:space": "cosine"}
    )

    # Collect JSON files (guidelines + med + csm subdirs)
    json_files = sorted(structured_dir.glob("*.json"))
    for subdir in ("med", "csm"):
        json_files.extend(sorted((structured_dir / subdir).glob("*.json")))
    json_files = [f for f in json_files if "index" not in f.name.lower()]

    total = 0
    for file_path in json_files:
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            cmg = CMGGuideline(**data)
        except Exception as e:
            logger.warning("Skipping %s: %s", file_path.name, e)
            continue

        sections = cmg.content_markdown.split("\n# ")
        for section in sections:
            if not section.strip():
                continue
            chunk_type = determine_chunk_type(section)
            max_tok = MAX_TOKENS[chunk_type]
            splitter = RecursiveCharacterTextSplitter(
                chunk_size=max_tok * 4, chunk_overlap=50
            )
            chunks = splitter.split_text(section)
            for idx, chunk_text in enumerate(chunks):
                chunk_has_icp = has_icp_content(chunk_text)

                if cmg.is_icp_only:
                    vis = "icp"
                    cid = f"{cmg.id}_{chunk_type}_{idx}"
                elif chunk_has_icp:
                    # ICP version
                    icp_id = f"{cmg.id}_{chunk_type}_{idx}_icp"
                    collection.add(
                        ids=[icp_id],
                        documents=[chunk_text],
                        metadatas=[{
                            "source_type": "cmg",
                            "source_file": file_path.name,
                            "cmg_number": cmg.cmg_number,
                            "section": cmg.section,
                            "is_icp_only": False,
                            "visibility": "icp",
                            "chunk_type": chunk_type,
                            "last_modified": cmg.extraction_metadata.timestamp,
                        }],
                    )
                    total += 1
                    # AP version
                    ap_id = f"{cmg.id}_{chunk_type}_{idx}_ap"
                    collection.add(
                        ids=[ap_id],
                        documents=[strip_icp_content(chunk_text)],
                        metadatas=[{
                            "source_type": "cmg",
                            "source_file": file_path.name,
                            "cmg_number": cmg.cmg_number,
                            "section": cmg.section,
                            "is_icp_only": False,
                            "visibility": "ap",
                            "chunk_type": chunk_type,
                            "last_modified": cmg.extraction_metadata.timestamp,
                        }],
                    )
                    total += 1
                    continue
                else:
                    vis = "both"
                    cid = f"{cmg.id}_{chunk_type}_{idx}"

                if not chunk_has_icp or cmg.is_icp_only:
                    collection.add(
                        ids=[cid],
                        documents=[chunk_text],
                        metadatas=[{
                            "source_type": "cmg",
                            "source_file": file_path.name,
                            "cmg_number": cmg.cmg_number,
                            "section": cmg.section,
                            "is_icp_only": cmg.is_icp_only,
                            "visibility": vis,
                            "chunk_type": chunk_type,
                            "last_modified": cmg.extraction_metadata.timestamp,
                        }],
                    )
                    total += 1

        # Dose lookup chunks
        if cmg.dose_lookup:
            dose_chunks = _dose_lookup_to_chunks(cmg.dose_lookup)
            for dose_idx, dose_text in enumerate(dose_chunks):
                dose_has_icp = has_icp_content(dose_text)

                if cmg.is_icp_only:
                    vis = "icp"
                    cid = f"{cmg.id}_dose_lookup_{dose_idx}"
                elif dose_has_icp:
                    icp_id = f"{cmg.id}_dose_lookup_{dose_idx}_icp"
                    collection.add(
                        ids=[icp_id],
                        documents=[dose_text],
                        metadatas=[{
                            "source_type": "cmg",
                            "source_file": file_path.name,
                            "cmg_number": cmg.cmg_number,
                            "section": cmg.section,
                            "is_icp_only": False,
                            "visibility": "icp",
                            "chunk_type": "dosage",
                            "last_modified": cmg.extraction_metadata.timestamp,
                        }],
                    )
                    total += 1
                    ap_id = f"{cmg.id}_dose_lookup_{dose_idx}_ap"
                    collection.add(
                        ids=[ap_id],
                        documents=[strip_icp_content(dose_text)],
                        metadatas=[{
                            "source_type": "cmg",
                            "source_file": file_path.name,
                            "cmg_number": cmg.cmg_number,
                            "section": cmg.section,
                            "is_icp_only": False,
                            "visibility": "ap",
                            "chunk_type": "dosage",
                            "last_modified": cmg.extraction_metadata.timestamp,
                        }],
                    )
                    total += 1
                    continue
                else:
                    vis = "both"
                    cid = f"{cmg.id}_dose_lookup_{dose_idx}"

                if not dose_has_icp or cmg.is_icp_only:
                    collection.add(
                        ids=[cid],
                        documents=[dose_text],
                        metadatas=[{
                            "source_type": "cmg",
                            "source_file": file_path.name,
                            "cmg_number": cmg.cmg_number,
                            "section": cmg.section,
                            "is_icp_only": cmg.is_icp_only,
                            "visibility": vis,
                            "chunk_type": "dosage",
                            "last_modified": cmg.extraction_metadata.timestamp,
                        }],
                    )
                    total += 1

    return total


def _build_empty_chroma(service_id: str, output_dir: Path) -> int:
    """Create an empty ChromaDB tree for a service with no data yet."""
    output_dir.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(output_dir))

    collection_name = f"guidelines_{service_id}"
    try:
        client.delete_collection(collection_name)
    except Exception:
        pass

    client.get_or_create_collection(
        collection_name, metadata={"hnsw:space": "cosine"}
    )
    return 0


def build_all(repo_root: Path) -> None:
    """Build ChromaDB trees for all registered services."""
    output_base = repo_root / "build" / "resources" / "data" / "services"

    for service in REGISTRY:
        service_id = service.id
        structured_dir = _structured_source_dir(service_id, repo_root)
        chroma_output = output_base / service_id / "chroma"

        # Clean previous build output for this service
        if chroma_output.exists():
            import shutil
            shutil.rmtree(chroma_output)

        if service_id == "actas" and structured_dir.exists() and any(structured_dir.glob("*.json")):
            count = _build_actas_chroma(structured_dir, chroma_output)
            logger.info("Service '%s': %d chunks ingested", service_id, count)
        else:
            count = _build_empty_chroma(service_id, chroma_output)
            logger.info("Service '%s': empty tree (no structured data)", service_id)

    # Summary
    logger.info("---")
    for service_id in all_service_ids():
        chroma_path = output_base / service_id / "chroma"
        if chroma_path.exists():
            client = chromadb.PersistentClient(path=str(chroma_path))
            for col in client.list_collections():
                logger.info("  %s: collection '%s' (%d chunks)", service_id, col.name, col.count())
        else:
            logger.info("  %s: no ChromaDB tree", service_id)


def main():
    parser = argparse.ArgumentParser(description="Build per-service ChromaDB trees for packaging")
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="Path to repo root (default: parent of scripts/)",
    )
    args = parser.parse_args()
    build_all(args.repo_root)


if __name__ == "__main__":
    main()
