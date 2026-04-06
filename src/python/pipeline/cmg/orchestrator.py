"""
Orchestrator for CMG Pipeline
Chains all extraction stages: navigation, content, dose tables,
structuring, chunking, and version tracking.
"""

import argparse
import logging
import sys
from typing import Any

from .extractor import extract_navigation, extract_route_mappings, extract_guidelines
from .content_extractor import extract_content, merge_navigation_and_content
from .dose_tables import extract_dose_tables, extract_dose_tables_segmented
from .flowcharts import process_flowcharts
from .structurer import structure_guidelines
from .chunker import chunk_and_ingest
from .version_tracker import update_version_tracking

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)

ALL_STAGES = [
    "navigation",
    "routes",
    "content",
    "dose",
    "segment-dose",
    "merge",
    "flowcharts",
    "structure",
    "chunk",
    "version",
]

INVESTIGATION_DIR = "data/cmgs/investigation/"
RAW_DIR = "data/cmgs/raw/"


def run_pipeline(
    stages: str = "all",
    dry_run: bool = False,
    investigation_dir: str = INVESTIGATION_DIR,
) -> dict[str, Any]:
    stages_to_run = ALL_STAGES if stages.lower() == "all" else stages.lower().split(",")
    inv_dir = investigation_dir
    result: dict[str, Any] = {
        "stages": stages_to_run,
        "dry_run": dry_run,
        "investigation_dir": inv_dir,
        "version_summary": None,
    }
    logger.info(f"Starting CMG Pipeline. Stages: {stages_to_run}")

    if "navigation" in stages_to_run:
        logger.info("=== Stage 1a: Navigation Extraction ===")
        extract_navigation(investigation_dir=inv_dir)

    if "routes" in stages_to_run:
        logger.info("=== Stage 1b: Route Mapping ===")
        extract_route_mappings(investigation_dir=inv_dir)

    if "content" in stages_to_run:
        logger.info("=== Stage 2: Content Extraction ===")
        extract_content(investigation_dir=inv_dir)

    if "dose" in stages_to_run:
        logger.info("=== Stage 3: Dose Tables ===")
        extract_dose_tables(investigation_dir=inv_dir)

    if "segment-dose" in stages_to_run:
        logger.info("=== Stage 3b: Segmented Dose Tables ===")
        extract_dose_tables_segmented(investigation_dir=inv_dir)

    if "merge" in stages_to_run:
        logger.info("=== Stage 4: Merge Navigation + Content ===")
        merge_navigation_and_content(
            nav_path=f"{RAW_DIR}cmg_navigation.json",
            content_path=f"{RAW_DIR}cmg_content.json",
            output_path=f"{RAW_DIR}guidelines.json",
        )

    if "flowcharts" in stages_to_run:
        logger.info("=== Stage 5: Flowcharts ===")
        process_flowcharts()

    if "structure" in stages_to_run:
        logger.info("=== Stage 6: Structuring ===")
        structure_guidelines()

    if "chunk" in stages_to_run:
        logger.info("=== Stage 7: Chunking & Ingestion ===")
        if dry_run:
            logger.info("Dry-run specified. Skipping ChromaDB ingestion.")
        else:
            chunk_and_ingest()

    if "version" in stages_to_run:
        logger.info("=== Stage 8: Version Tracking ===")
        result["version_summary"] = update_version_tracking()

    logger.info("Pipeline completed successfully.")
    return result


def main():
    parser = argparse.ArgumentParser(description="ACTAS CMG Extraction Pipeline")
    parser.add_argument(
        "--stages", type=str, help="Comma-separated stages or 'all'", default="all"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Dry run mode (no ChromaDB writes)"
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
        sys.exit(1)


if __name__ == "__main__":
    main()
