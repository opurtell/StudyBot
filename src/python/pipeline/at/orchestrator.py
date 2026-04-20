"""Orchestrator for AT CPG Pipeline.

Chains all extraction stages for Ambulance Tasmania Clinical Practice Guidelines:
discovery, content extraction, dose tables, flowcharts, structuring, chunking,
and version tracking.

This adapter follows the same pattern as the ACTAS CMG orchestrator but
is adapted for the AT CPG site structure and schema.
"""

import logging
from typing import Any

from .discover import discover_site

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

    result: dict[str, Any] = {
        "stages": stages_to_run,
        "dry_run": dry_run,
        "investigation_dir": inv_dir,
    }

    logger.info(f"Starting AT CPG Pipeline. Stages: {stages_to_run}")

    # Stage 1: Discover site structure
    if "discover" in stages_to_run:
        logger.info("=== Stage 1: Site Discovery ===")
        discovery_result = discover_site(output_dir=inv_dir)
        result["discovery"] = discovery_result.model_dump()
        logger.info(
            f"Discovered {len(discovery_result.guidelines)} guidelines, "
            f"{len(discovery_result.medicines)} medicines"
        )

    # Stage 2: Extract JS bundles (no-op stub)
    if "extract" in stages_to_run:
        logger.info("=== Stage 2: JS Bundle Extraction ===")
        logger.info("Stage not yet implemented - no-op")

    # Stage 3: Extract guideline content (no-op stub)
    if "content" in stages_to_run:
        logger.info("=== Stage 3: Content Extraction ===")
        logger.info("Stage not yet implemented - no-op")

    # Stage 4: Extract dose tables (no-op stub)
    if "dose" in stages_to_run:
        logger.info("=== Stage 4: Dose Table Extraction ===")
        logger.info("Stage not yet implemented - no-op")

    # Stage 5: Extract flowcharts (no-op stub)
    if "flowcharts" in stages_to_run:
        logger.info("=== Stage 5: Flowchart Extraction ===")
        logger.info("Stage not yet implemented - no-op")

    # Stage 6: Structure guidelines (no-op stub)
    if "structure" in stages_to_run:
        logger.info("=== Stage 6: Structuring ===")
        logger.info("Stage not yet implemented - no-op")

    # Stage 7: Extract qualifications (no-op stub)
    if "qualifications" in stages_to_run:
        logger.info("=== Stage 7: Qualifications Extraction ===")
        logger.info("Stage not yet implemented - no-op")

    # Stage 8: Chunk and ingest (no-op stub)
    if "chunk" in stages_to_run:
        logger.info("=== Stage 8: Chunking & Ingestion ===")
        if dry_run:
            logger.info("Dry-run specified. Skipping ChromaDB ingestion.")
        else:
            logger.info("Stage not yet implemented - no-op")

    # Stage 9: Medication index (no-op stub)
    if "medications" in stages_to_run:
        logger.info("=== Stage 9: Medication Index ===")
        logger.info("Stage not yet implemented - no-op")

    # Stage 10: Version tracking (no-op stub)
    if "version" in stages_to_run:
        logger.info("=== Stage 10: Version Tracking ===")
        logger.info("Stage not yet implemented - no-op")

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
