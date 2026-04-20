"""Stage 7: Semantic Chunking and ChromaDB Ingestion for AT pipeline.

This module chunks AT guideline content and ingests into the service-scoped
guidelines_at ChromaDB collection.
"""

import glob
import json
import logging
import os
from typing import Any, Dict, List

import chromadb
from langchain_text_splitters import RecursiveCharacterTextSplitter

from src.python.services.schema import GuidelineDocument

logger = logging.getLogger(__name__)

# Chunk type detection based on content keywords
CHUNK_TYPES = {
    "dosage": ["dosage", "administration", "dose", "amount"],
    "safety": ["contraindications", "warnings", "precautions"],
    "protocol": ["procedure", "treatment", "management"],
    "reference": ["table", "appendix", "reference"],
    "assessment": ["indications", "presentation", "diagnosis"],
}  # Default to "general"

# Character limits per chunk type (approximate tokens * 4)
MAX_CHARS = {
    "dosage": 500 * 4,
    "safety": 300 * 4,
    "protocol": 1000 * 4,
    "reference": 800 * 4,
    "assessment": 400 * 4,
    "general": 600 * 4,
}


def determine_chunk_type(text: str) -> str:
    """Determine chunk type based on headers or content keywords.

    Args:
        text: The text content to analyze

    Returns:
        The chunk type (dosage, safety, protocol, reference, assessment, or general)
    """
    text_lower = text.lower()
    for ctype, triggers in CHUNK_TYPES.items():
        for trigger in triggers:
            if trigger in text_lower:
                return ctype
    return "general"


def _medications_to_chunks(medications: List[Dict[str, Any]], max_chars: int = 1800) -> List[str]:
    """Convert medication dose list to chunkable text blocks.

    Args:
        medications: List of MedicationDose dicts
        max_chars: Maximum characters per chunk

    Returns:
        List of medication text chunks
    """
    lines: List[str] = []
    for med in medications:
        if not isinstance(med, dict):
            continue
        med_name = med.get("medication", "Unknown")
        indication = med.get("indication", "")
        dose = med.get("dose", "")
        route = med.get("route", "")
        qualifications = med.get("qualifications_required", [])

        # Build medication entry
        parts = [f"- {med_name}"]
        if indication:
            parts.append(f"  Indication: {indication}")
        if dose:
            parts.append(f"  Dose: {dose}")
        if route:
            parts.append(f"  Route: {route}")
        if qualifications:
            parts.append(f"  Qualifications: {', '.join(qualifications)}")

        lines.append("\n".join(parts))

    if not lines:
        return []

    full_text = "\n".join(lines)
    if len(full_text) <= max_chars:
        return [full_text]

    # Split into smaller chunks if needed
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
    structured_dir: str,
    db_path: str,
    collection_name: str = "guidelines_at",
) -> Dict[str, int]:
    """Chunk AT guideline content and ingest into ChromaDB.

    Args:
        structured_dir: Directory containing AT_CPG_*.json structured files
        db_path: Path to ChromaDB storage
        collection_name: Name of the ChromaDB collection (default: "guidelines_at")

    Returns:
        Dictionary with ingestion stats (total_chunks, files_processed)
    """
    # Find all AT_CPG_*.json files
    json_files = [
        f
        for f in glob.glob(os.path.join(structured_dir, "AT_CPG_*.json"))
        if "index" not in os.path.basename(f)
    ]

    if not json_files:
        logger.warning(f"No AT structured JSON files found in {structured_dir}")
        return {"total_chunks": 0, "files_processed": 0}

    # Create ChromaDB client and collection
    os.makedirs(db_path, exist_ok=True)
    client = chromadb.PersistentClient(path=db_path)
    collection = client.get_or_create_collection(name=collection_name)

    total_chunks = 0
    files_processed = 0

    for file_path in json_files:
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            guideline = GuidelineDocument(**data)

            # Get last_modified timestamp for metadata
            if guideline.last_modified:
                last_modified = guideline.last_modified.isoformat()
            else:
                last_modified = ""

            # Get primary category for section metadata
            section = guideline.categories[0] if guideline.categories else "Uncategorized"

            # Chunk each content section
            for content_section in guideline.content_sections:
                # Build section text with heading
                section_text = f"# {content_section.heading}\n\n{content_section.body}"

                # Determine chunk type
                chunk_type = determine_chunk_type(section_text)
                max_chars = MAX_CHARS[chunk_type]

                # Split section into chunks
                splitter = RecursiveCharacterTextSplitter(
                    chunk_size=max_chars, chunk_overlap=100
                )
                chunks = splitter.split_text(section_text)

                for idx, chunk_text in enumerate(chunks):
                    chunk_id = f"{guideline.guideline_id}_{chunk_type}_{idx}"

                    # Serialize qualifications_required as JSON string
                    qualifications_json = json.dumps(
                        content_section.qualifications_required
                    )

                    metadata = {
                        "source_type": "cmg",
                        "source_file": os.path.basename(file_path),
                        "guideline_id": guideline.guideline_id,
                        "section": section,
                        "qualifications_required": qualifications_json,
                        "chunk_type": chunk_type,
                        "last_modified": last_modified,
                    }

                    collection.add(
                        ids=[chunk_id], documents=[chunk_text], metadatas=[metadata]
                    )
                    total_chunks += 1

            # Chunk medications if present
            if guideline.medications:
                med_dicts = [med.model_dump() for med in guideline.medications]
                med_chunks = _medications_to_chunks(med_dicts)

                for med_idx, med_text in enumerate(med_chunks):
                    med_id = f"{guideline.guideline_id}_medications_{med_idx}"

                    # Aggregate qualifications from all medications in this chunk
                    qualifications_in_chunk = set()
                    for med in med_dicts:
                        qualifications_in_chunk.update(med.get("qualifications_required", []))

                    qualifications_json = json.dumps(list(qualifications_in_chunk))

                    metadata = {
                        "source_type": "cmg",
                        "source_file": os.path.basename(file_path),
                        "guideline_id": guideline.guideline_id,
                        "section": section,
                        "qualifications_required": qualifications_json,
                        "chunk_type": "dosage",
                        "last_modified": last_modified,
                    }

                    collection.add(
                        ids=[med_id], documents=[med_text], metadatas=[metadata]
                    )
                    total_chunks += 1

            files_processed += 1

        except Exception as e:
            logger.error(f"Failed to chunk and ingest {file_path}: {e}")

    logger.info(
        f"Ingested {total_chunks} chunks from {files_processed} AT guidelines "
        f"into ChromaDB collection '{collection_name}'."
    )

    return {"total_chunks": total_chunks, "files_processed": files_processed}
