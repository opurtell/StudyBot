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
from guidelines.markdown import has_icp_content, strip_icp_content

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

            # Very basic markdown splitting by headers
            # A more advanced logic would be to use MarkdownHeaderTextSplitter
            sections = cmg.content_markdown.split("\n# ")

            for section in sections:
                if not section.strip():
                    continue

                chunk_type = determine_chunk_type(section)
                max_tok = MAX_TOKENS[chunk_type]

                # Approximate token size using characters
                splitter = RecursiveCharacterTextSplitter(
                    chunk_size=max_tok * 4, chunk_overlap=50
                )

                chunks = splitter.split_text(section)

                for idx, chunk_text in enumerate(chunks):
                    chunk_has_icp = has_icp_content(chunk_text)

                    if cmg.is_icp_only:
                        # Whole guideline is ICP-only — single chunk
                        visibility = "icp"
                        chunk_id = f"{cmg.id}_{chunk_type}_{idx}"
                        metadata = {
                            "source_type": "cmg",
                            "source_file": os.path.basename(file_path),
                            "cmg_number": cmg.cmg_number,
                            "section": cmg.section,
                            "is_icp_only": True,
                            "visibility": visibility,
                            "chunk_type": chunk_type,
                            "last_modified": cmg.extraction_metadata.timestamp,
                        }
                        collection.add(
                            ids=[chunk_id], documents=[chunk_text], metadatas=[metadata]
                        )
                        total_chunks += 1
                    elif chunk_has_icp:
                        # Mixed chunk — store two versions
                        # ICP version (full content)
                        icp_id = f"{cmg.id}_{chunk_type}_{idx}_icp"
                        metadata_icp = {
                            "source_type": "cmg",
                            "source_file": os.path.basename(file_path),
                            "cmg_number": cmg.cmg_number,
                            "section": cmg.section,
                            "is_icp_only": False,
                            "visibility": "icp",
                            "chunk_type": chunk_type,
                            "last_modified": cmg.extraction_metadata.timestamp,
                        }
                        collection.add(
                            ids=[icp_id], documents=[chunk_text], metadatas=[metadata_icp]
                        )
                        total_chunks += 1

                        # AP version (stripped content)
                        ap_id = f"{cmg.id}_{chunk_type}_{idx}_ap"
                        stripped = strip_icp_content(chunk_text)
                        metadata_ap = {
                            "source_type": "cmg",
                            "source_file": os.path.basename(file_path),
                            "cmg_number": cmg.cmg_number,
                            "section": cmg.section,
                            "is_icp_only": False,
                            "visibility": "ap",
                            "chunk_type": chunk_type,
                            "last_modified": cmg.extraction_metadata.timestamp,
                        }
                        collection.add(
                            ids=[ap_id], documents=[stripped], metadatas=[metadata_ap]
                        )
                        total_chunks += 1
                    else:
                        # No ICP content — shared chunk
                        chunk_id = f"{cmg.id}_{chunk_type}_{idx}"
                        metadata = {
                            "source_type": "cmg",
                            "source_file": os.path.basename(file_path),
                            "cmg_number": cmg.cmg_number,
                            "section": cmg.section,
                            "is_icp_only": False,
                            "visibility": "both",
                            "chunk_type": chunk_type,
                            "last_modified": cmg.extraction_metadata.timestamp,
                        }
                        collection.add(
                            ids=[chunk_id], documents=[chunk_text], metadatas=[metadata]
                        )
                        total_chunks += 1

            if cmg.dose_lookup:
                dose_chunks = _dose_lookup_to_chunks(cmg.dose_lookup)
                for dose_idx, dose_text in enumerate(dose_chunks):
                    dose_has_icp = has_icp_content(dose_text)

                    if cmg.is_icp_only:
                        visibility = "icp"
                        chunk_id = f"{cmg.id}_dose_lookup_{dose_idx}"
                    elif dose_has_icp:
                        # ICP version
                        icp_id = f"{cmg.id}_dose_lookup_{dose_idx}_icp"
                        meta_icp = {
                            "source_type": "cmg",
                            "source_file": os.path.basename(file_path),
                            "cmg_number": cmg.cmg_number,
                            "section": cmg.section,
                            "is_icp_only": False,
                            "visibility": "icp",
                            "chunk_type": "dosage",
                            "last_modified": cmg.extraction_metadata.timestamp,
                        }
                        collection.add(
                            ids=[icp_id], documents=[dose_text], metadatas=[meta_icp]
                        )
                        total_chunks += 1

                        # AP version
                        ap_id = f"{cmg.id}_dose_lookup_{dose_idx}_ap"
                        stripped = strip_icp_content(dose_text)
                        meta_ap = {
                            "source_type": "cmg",
                            "source_file": os.path.basename(file_path),
                            "cmg_number": cmg.cmg_number,
                            "section": cmg.section,
                            "is_icp_only": False,
                            "visibility": "ap",
                            "chunk_type": "dosage",
                            "last_modified": cmg.extraction_metadata.timestamp,
                        }
                        collection.add(
                            ids=[ap_id], documents=[stripped], metadatas=[meta_ap]
                        )
                        total_chunks += 1
                        continue
                    else:
                        visibility = "both"
                        chunk_id = f"{cmg.id}_dose_lookup_{dose_idx}"

                    if not dose_has_icp or cmg.is_icp_only:
                        collection.add(
                            ids=[chunk_id],
                            documents=[dose_text],
                            metadatas=[
                                {
                                    "source_type": "cmg",
                                    "source_file": os.path.basename(file_path),
                                    "cmg_number": cmg.cmg_number,
                                    "section": cmg.section,
                                    "is_icp_only": cmg.is_icp_only,
                                    "visibility": visibility,
                                    "chunk_type": "dosage",
                                    "last_modified": cmg.extraction_metadata.timestamp,
                                }
                            ],
                        )
                        total_chunks += 1

        except Exception as e:
            logger.error(f"Failed to chunk and ingest {file_path}: {e}")

    logger.info(f"Ingested {total_chunks} chunks into ChromaDB.")
    return total_chunks
