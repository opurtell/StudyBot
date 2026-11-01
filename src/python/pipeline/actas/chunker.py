"""
Stage 6: Semantic Chunking and ChromaDB Ingestion
"""

import glob
import json
import logging
import os
from typing import Dict, Any, List

import chromadb
from langchain_text_splitters import RecursiveCharacterTextSplitter

from paths import CHROMA_DB_DIR

from .models import CMGGuideline
from guidelines import actas_scope as scope

logger = logging.getLogger(__name__)

CHUNK_TYPES = {
    "dosage": ["dosage", "administration", "dose", "amount"],
    "safety": ["contraindications", "warnings", "precautions"],
    "protocol": ["procedure", "treatment", "management"],
    "reference": ["table", "appendix", "reference"],
    "assessment": ["indications", "presentation", "diagnosis"],
}  # Default to "general"

MAX_TOKENS = {
    "dosage": 500,
    "safety": 300,
    "protocol": 1000,
    "reference": 800,
    "assessment": 400,
    "general": 600,
}


def determine_chunk_type(text: str) -> str:
    """Determine chunk type based on headers or content keywords."""
    text_lower = text.lower()
    for ctype, triggers in CHUNK_TYPES.items():
        for trigger in triggers:
            if trigger in text_lower:
                return ctype
    return "general"


def _dose_lookup_to_chunks(
    dose_lookup: Dict[str, Any], max_chars: int = 1800
) -> List[str]:
    lines: List[str] = []
    for med_name, entries in dose_lookup.items():
        if not isinstance(entries, list):
            continue
        seen_texts: set[str] = set()
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            text = entry.get("text", "").strip()
            if not text or text in seen_texts:
                continue
            seen_texts.add(text)
            lines.append(f"- {text}")
        if lines:
            lines.append("")

    if not lines:
        return []

    full_text = "\n".join(lines)
    if len(full_text) <= max_chars:
        return [full_text]

    chunks: List[str] = []
    current_lines: List[str] = []
    current_len = 0
    for line in lines:
        line_len = len(line) + 1
        if current_len + line_len > max_chars and current_lines:
            chunks.append("\n".join(current_lines))
            current_lines = []
            current_len = 0
        current_lines.append(line)
        current_len += line_len
    if current_lines:
        chunks.append("\n".join(current_lines))
    return chunks


def chunk_and_ingest(
    structured_dir: str = "data/cmgs/structured/",
    db_path: str = str(CHROMA_DB_DIR),
    collection_name: str = "guidelines_actas",
):
    """Chunk the markdown content and ingest into ChromaDB."""
    json_files = [
        f
        for f in glob.glob(os.path.join(structured_dir, "*.json"))
        if "index" not in os.path.basename(f)
    ]
    json_files.extend(
        f
        for f in glob.glob(os.path.join(structured_dir, "med", "*.json"))
        if "index" not in os.path.basename(f)
    )
    json_files.extend(
        f
        for f in glob.glob(os.path.join(structured_dir, "csm", "*.json"))
        if "index" not in os.path.basename(f)
    )
    if not json_files:
        logger.warning(f"No structured JSON files found in {structured_dir}")
        return

    os.makedirs(db_path, exist_ok=True)
    client = chromadb.PersistentClient(path=db_path)
    collection = client.get_or_create_collection(name=collection_name)

    total_chunks = 0
    for file_path in json_files:
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            cmg = CMGGuideline(**data)
            source_file = os.path.basename(file_path)
            whole_scope = scope.document_scope(data)

            def add_chunk(chunk_id: str, text: str, visibility: str, chunk_type: str) -> None:
                collection.add(
                    ids=[chunk_id],
                    documents=[text],
                    metadatas=[
                        {
                            "source_type": "cmg",
                            "source_file": source_file,
                            "cmg_number": cmg.cmg_number,
                            "section": cmg.section,
                            "is_icp_only": whole_scope == scope.ICP,
                            "visibility": visibility,
                            "chunk_type": chunk_type,
                            "last_modified": cmg.extraction_metadata.timestamp,
                        }
                    ],
                )

            segments = scope.classify(data)
            full_text = scope.render(segments, {"AP", "ICP", "PACER"})
            ap_only = scope.render(segments, {"AP"})

            if whole_scope is not None:
                variants = [(full_text, whole_scope, "")]
            elif ap_only == full_text:
                variants = [(full_text, "both", "")]
            else:
                variants = [(full_text, "icp", "_icp"), (ap_only, "ap", "_ap")]

            for variant_text, visibility, suffix in variants:
                for sec_idx, section in enumerate(variant_text.split("\n# ")):
                    if not section.strip():
                        continue
                    chunk_type = determine_chunk_type(section)
                    splitter = RecursiveCharacterTextSplitter(
                        chunk_size=MAX_TOKENS[chunk_type] * 4, chunk_overlap=50
                    )
                    for idx, chunk_text in enumerate(splitter.split_text(section)):
                        add_chunk(
                            f"{cmg.id}_{sec_idx}_{chunk_type}_{idx}{suffix}",
                            chunk_text,
                            visibility,
                            chunk_type,
                        )
                        total_chunks += 1

            if cmg.dose_lookup:
                by_scope: Dict[str, Dict[str, Any]] = {}
                for med_name, entries in cmg.dose_lookup.items():
                    if not isinstance(entries, list):
                        continue
                    for entry in entries:
                        if not isinstance(entry, dict):
                            continue
                        entry_scope, _ = scope.dose_entry_scope(
                            med_name, entry.get("text", ""), whole_scope == scope.ICP
                        )
                        by_scope.setdefault(entry_scope, {}).setdefault(med_name, []).append(entry)
                for visibility, lookup in sorted(by_scope.items()):
                    for dose_idx, dose_text in enumerate(_dose_lookup_to_chunks(lookup)):
                        add_chunk(
                            f"{cmg.id}_dose_lookup_{visibility}_{dose_idx}",
                            dose_text,
                            visibility,
                            "dosage",
                        )
                        total_chunks += 1

        except Exception as e:
            logger.error(f"Failed to chunk and ingest {file_path}: {e}")

    logger.info(f"Ingested {total_chunks} chunks into ChromaDB.")
    return total_chunks
