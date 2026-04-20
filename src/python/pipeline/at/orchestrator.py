"""Orchestrator for AT CPG Pipeline.

Chains all extraction stages for Ambulance Tasmania Clinical Practice Guidelines:
discovery, content extraction, dose tables, flowcharts, structuring, chunking,
and version tracking.

This adapter follows the same pattern as the ACTAS CMG orchestrator but
is adapted for the AT CPG site structure and schema.
"""

import logging
import os
from pathlib import Path
from typing import Any

from .discover import discover_site
from .extractor import extract_all_metadata
from .content_extractor import extract_all_guidelines
from .dose_extractor import extract_dose_sections
from .flowcharts import process_all_flowcharts
from .structurer import structure_all_guidelines
from .qualifications_tagger import tag_guideline_qualifications
from .chunker import chunk_and_ingest
from .medications_index import build_medications_index
from .version_tracker import update_version_tracking

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

ALL_STAGES = [
    "discover",
    "extract",
    "content",
    "dose",
    "flowcharts",
    "structure",
    "qualifications",
    "chunk",
    "medications",
    "version",
]

INVESTIGATION_DIR = "data/at/investigation/"
RAW_DIR = "data/at/raw/"
STRUCTURED_DIR = "data/at/structured/"


def run_pipeline(
    stages: str = "all",
    dry_run: bool = False,
    investigation_dir: str = INVESTIGATION_DIR,
) -> dict[str, Any]:
    """Run the AT CPG extraction pipeline.

    Args:
        stages: Comma-separated stage names or "all" to run all stages
        dry_run: If True, skip writes to ChromaDB and other external stores
        investigation_dir: Directory containing downloaded JS bundles

    Returns:
        dict with pipeline results including:
        - stages: List of stages that were run
        - dry_run: Whether dry_run mode was active
        - investigation_dir: Directory used for investigation files
    """
    stages_to_run = ALL_STAGES if stages.lower() == "all" else stages.lower().split(",")
    inv_dir = investigation_dir
    raw_dir = RAW_DIR
    structured_dir = STRUCTURED_DIR

    # Ensure directories exist
    os.makedirs(inv_dir, exist_ok=True)
    os.makedirs(raw_dir, exist_ok=True)
    os.makedirs(structured_dir, exist_ok=True)

    result: dict[str, Any] = {
        "stages": stages_to_run,
        "dry_run": dry_run,
        "investigation_dir": inv_dir,
        "raw_dir": raw_dir,
        "structured_dir": structured_dir,
    }

    logger.info(f"Starting AT CPG Pipeline. Stages: {stages_to_run}")

    # Stage 1: Discover site structure
    if "discover" in stages_to_run:
        logger.info("=== Stage 1: Site Discovery ===")
        try:
            discovery_result = discover_site(output_dir=inv_dir)
            result["discovery"] = discovery_result.model_dump()
            logger.info(
                f"Discovered {len(discovery_result.guidelines)} guidelines, "
                f"{len(discovery_result.medicines)} medicines"
            )
        except Exception as e:
            logger.error(f"Discovery stage failed: {e}")
            result["discovery_error"] = str(e)

    # Stage 2: Extract JS bundles and metadata
    if "extract" in stages_to_run:
        logger.info("=== Stage 2: JS Bundle Extraction ===")
        try:
            metadata = extract_all_metadata(investigation_dir=inv_dir)
            result["extract"] = metadata
            logger.info(
                f"Extracted {len(metadata.get('cpg_codes', []))} CPG codes, "
                f"{len(metadata.get('medicines', []))} medicines"
            )
        except Exception as e:
            logger.error(f"Extraction stage failed: {e}")
            result["extract_error"] = str(e)

    # Stage 3: Extract guideline content
    if "content" in stages_to_run:
        logger.info("=== Stage 3: Content Extraction ===")
        discovery_path = os.path.join(inv_dir, "discovery.json")
        if os.path.exists(discovery_path):
            try:
                guidelines = extract_all_guidelines(
                    discovery_path=discovery_path,
                    output_dir=raw_dir,
                    bundles_dir=inv_dir,
                )
                result["content"] = {"count": len(guidelines)}
                logger.info(f"Extracted content for {len(guidelines)} guidelines")
            except Exception as e:
                logger.error(f"Content extraction failed: {e}")
                result["content_error"] = str(e)
        else:
            logger.warning(f"Discovery file not found: {discovery_path}")
            result["content_error"] = "Discovery file not found"

    # Stage 4: Extract dose tables (integrated into content extraction)
    if "dose" in stages_to_run:
        logger.info("=== Stage 4: Dose Table Extraction ===")
        logger.info("Dose extraction is integrated into content extraction stage")
        result["dose"] = {"status": "integrated"}

    # Stage 5: Extract flowcharts
    if "flowcharts" in stages_to_run:
        logger.info("=== Stage 5: Flowchart Extraction ===")
        discovery_path = os.path.join(inv_dir, "discovery.json")
        flowcharts_dir = os.path.join(raw_dir, "flowcharts")
        if os.path.exists(discovery_path):
            try:
                flowcharts = process_all_flowcharts(
                    discovery_path=discovery_path,
                    output_dir=flowcharts_dir,
                )
                result["flowcharts"] = {"count": len(flowcharts)}
                logger.info(f"Processed {len(flowcharts)} flowcharts")
            except Exception as e:
                logger.error(f"Flowchart extraction failed: {e}")
                result["flowcharts_error"] = str(e)
        else:
            logger.warning(f"Discovery file not found: {discovery_path}")
            result["flowcharts_error"] = "Discovery file not found"

    # Stage 6: Structure guidelines
    if "structure" in stages_to_run:
        logger.info("=== Stage 6: Structuring ===")
        if os.path.exists(raw_dir):
            try:
                count = structure_all_guidelines(raw_dir=raw_dir, output_dir=structured_dir)
                result["structure"] = {"count": count}
                logger.info(f"Structured {count} guidelines")
            except Exception as e:
                logger.error(f"Structuring failed: {e}")
                result["structure_error"] = str(e)
        else:
            logger.warning(f"Raw directory not found: {raw_dir}")
            result["structure_error"] = "Raw directory not found"

    # Stage 7: Tag qualifications
    if "qualifications" in stages_to_run:
        logger.info("=== Stage 7: Qualifications Tagging ===")
        logger.info("Qualification tagging is integrated into structurer stage")
        result["qualifications"] = {"status": "integrated"}

    # Stage 8: Chunk and ingest
    if "chunk" in stages_to_run:
        logger.info("=== Stage 8: Chunking & Ingestion ===")
        if dry_run:
            logger.info("Dry-run specified. Skipping ChromaDB ingestion.")
            result["chunk"] = {"status": "skipped (dry_run)"}
        elif os.path.exists(structured_dir):
            try:
                db_path = "data/at/chroma_db"
                chunk_and_ingest(structured_dir=structured_dir, db_path=db_path)
                result["chunk"] = {"status": "completed"}
                logger.info("Chunking and ingestion completed")
            except Exception as e:
                logger.error(f"Chunking failed: {e}")
                result["chunk_error"] = str(e)
        else:
            logger.warning(f"Structured directory not found: {structured_dir}")
            result["chunk_error"] = "Structured directory not found"

    # Stage 9: Medication index
    if "medications" in stages_to_run:
        logger.info("=== Stage 9: Medication Index ===")
        if os.path.exists(structured_dir):
            try:
                med_output_dir = os.path.join(structured_dir, "medications")
                count = build_medications_index(
                    structured_dir=structured_dir,
                    output_dir=med_output_dir,
                )
                result["medications"] = {"count": count}
                logger.info(f"Built medication index for {count} medicines")
            except Exception as e:
                logger.error(f"Medication index failed: {e}")
                result["medications_error"] = str(e)
        else:
            logger.warning(f"Structured directory not found: {structured_dir}")
            result["medications_error"] = "Structured directory not found"

    # Stage 10: Version tracking
    if "version" in stages_to_run:
        logger.info("=== Stage 10: Version Tracking ===")
        if os.path.exists(structured_dir):
            try:
                tracker_path = os.path.join(structured_dir, "version_tracker.json")
                version_summary = update_version_tracking(
                    structured_dir=structured_dir,
                    tracker_path=tracker_path,
                )
                result["version"] = version_summary
                logger.info(
                    f"Version tracking: {version_summary.get('total_count', 0)} total, "
                    f"{version_summary.get('new_count', 0)} new, "
                    f"{version_summary.get('modified_count', 0)} modified"
                )
            except Exception as e:
                logger.error(f"Version tracking failed: {e}")
                result["version_error"] = str(e)
        else:
            logger.warning(f"Structured directory not found: {structured_dir}")
            result["version_error"] = "Structured directory not found"

    logger.info("Pipeline completed successfully.")
    return result


def main() -> None:
    """CLI entry point for the AT CPG pipeline."""
    import argparse

    parser = argparse.ArgumentParser(description="AT CPG Extraction Pipeline")
    parser.add_argument(
        "--stages",
        type=str,
        help="Comma-separated stages or 'all'",
        default="all",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Dry run mode (no ChromaDB writes)",
    )
    parser.add_argument(
        "--investigation-dir",
        type=str,
        default=INVESTIGATION_DIR,
        help="Directory containing downloaded JS bundles",
    )
    args = parser.parse_args()

    try:
        run_pipeline(
            stages=args.stages,
            dry_run=args.dry_run,
            investigation_dir=args.investigation_dir,
        )
    except Exception as e:
        logger.error(f"Pipeline error: {e}")
        import sys

        sys.exit(1)


if __name__ == "__main__":
    main()
