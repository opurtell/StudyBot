"""CLI entrypoint for the Notability notes pipeline.

Commands:
    extract [--limit N]                     Extract .note files to raw markdown
    ingest [--dry-run]                      Chunk and ingest cleaned files to ChromaDB
    status                                  Report pipeline state

All paths default to the project's standard locations but can be overridden
with flags for testing.
"""

import argparse
import json
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from paths import APP_ROOT, CHROMA_DB_DIR, DATA_DIR

DEFAULT_SOURCE_DIR = APP_ROOT / "docs" / "notabilityNotes" / "noteDocs"
DEFAULT_RAW_DIR = DATA_DIR / "notes_md" / "raw"
DEFAULT_CLEANED_DIR = DATA_DIR / "notes_md" / "cleaned"
DEFAULT_DB_PATH = CHROMA_DB_DIR


def cmd_extract(args):
    from pipeline.extractor import extract_all

    source_dir = Path(args.source_dir)
    raw_dir = Path(args.raw_dir)
    raw_dir.mkdir(parents=True, exist_ok=True)

    results = extract_all(source_dir, raw_dir, limit=args.limit)
    successes = sum(1 for r in results if r["success"])
    failures = sum(1 for r in results if not r["success"])
    print(f"\nDone. {successes} extracted, {failures} failed.")
    if failures:
        print(f"See {raw_dir / 'extraction_log.json'} for failure details.")


def cmd_ingest(args):
    from pipeline.structurer import validate_and_normalise
    from pipeline.chunker import chunk_and_ingest

    cleaned_dir = Path(args.cleaned_dir)
    db_path = Path(args.db_path)

    md_files = sorted(cleaned_dir.rglob("*.md"))
    if not md_files:
        print(f"No cleaned .md files found in {cleaned_dir}")
        return

    results = []
    for md_path in md_files:
        # Validate first
        val = validate_and_normalise(md_path)
        if not val["valid"]:
            print(f"  SKIP (invalid): {md_path.name} — {val['error']}")
            results.append(
                {"source_file": str(md_path), "success": False, "error": val["error"]}
            )
            continue

        if args.dry_run:
            print(
                f"  DRY RUN: {val['source_file']} — valid, {len(val['categories'])} categories"
            )
            results.append(
                {
                    "source_file": val["source_file"],
                    "success": True,
                    "chunk_count": 0,
                    "dry_run": True,
                }
            )
            continue

        # Chunk and ingest
        result = chunk_and_ingest(md_path, db_path)
        print(f"  OK: {result['source_file']} — {result['chunk_count']} chunks")
        results.append(result)

    # Write ingestion log to parent of cleaned/ (i.e. data/notes_md/)
    log_path = cleaned_dir.parent / "ingestion_log.json"
    log_path.write_text(json.dumps(results, indent=2, default=str))

    total = len(results)
    ok = sum(1 for r in results if r.get("success"))
    total_chunks = sum(r.get("chunk_count", 0) for r in results)
    flagged = sum(1 for r in results if r.get("has_review_flag"))

    # Category distribution
    cat_counts: dict[str, int] = {}
    for r in results:
        for cat in r.get("categories", []):
            cat_counts[cat] = cat_counts.get(cat, 0) + 1

    print(
        f"\nIngested {ok}/{total} files, {total_chunks} total chunks, {flagged} with review flags."
    )
    if cat_counts:
        print("Category distribution:")
        for cat, count in sorted(cat_counts.items()):
            print(f"  {cat}: {count}")


def cmd_status(args):
    raw_dir = Path(args.raw_dir)
    cleaned_dir = Path(args.cleaned_dir)
    db_path = Path(args.db_path)

    raw_count = len(list(raw_dir.rglob("*.md"))) if raw_dir.exists() else 0
    cleaned_count = len(list(cleaned_dir.rglob("*.md"))) if cleaned_dir.exists() else 0
    pending = raw_count - cleaned_count

    # Check extraction failures (log is at data/notes_md/ level)
    log_path = raw_dir.parent / "extraction_log.json"
    extraction_failures = 0
    if log_path.exists():
        log = json.loads(log_path.read_text())
        extraction_failures = log.get("failed", 0)

    # Check ChromaDB
    ingested = 0
    if db_path.exists():
        try:
            import chromadb

            client = chromadb.PersistentClient(path=str(db_path))
            collection = client.get_collection("paramedic_notes")
            ingested = collection.count()
        except Exception:
            pass

    print(f"Raw extracted:       {raw_count}")
    print(f"Extraction failures: {extraction_failures}")
    print(f"Cleaned:             {cleaned_count}")
    print(f"Pending cleaning:    {pending}")
    print(f"ChromaDB chunks:     {ingested}")


def main():
    parser = argparse.ArgumentParser(description="Notability notes pipeline")
    sub = parser.add_subparsers(dest="command", required=True)

    # extract
    p_extract = sub.add_parser("extract", help="Extract .note files to raw markdown")
    p_extract.add_argument(
        "--limit", type=int, default=None, help="Max files to process"
    )
    p_extract.add_argument("--source-dir", default=str(DEFAULT_SOURCE_DIR))
    p_extract.add_argument("--raw-dir", default=str(DEFAULT_RAW_DIR))

    # ingest
    p_ingest = sub.add_parser(
        "ingest", help="Chunk and ingest cleaned files to ChromaDB"
    )
    p_ingest.add_argument(
        "--dry-run", action="store_true", help="Validate without writing to ChromaDB"
    )
    p_ingest.add_argument("--cleaned-dir", default=str(DEFAULT_CLEANED_DIR))
    p_ingest.add_argument("--db-path", default=str(DEFAULT_DB_PATH))

    # status
    p_status = sub.add_parser("status", help="Report pipeline state")
    p_status.add_argument("--raw-dir", default=str(DEFAULT_RAW_DIR))
    p_status.add_argument("--cleaned-dir", default=str(DEFAULT_CLEANED_DIR))
    p_status.add_argument("--db-path", default=str(DEFAULT_DB_PATH))

    args = parser.parse_args()
    if args.command == "extract":
        cmd_extract(args)
    elif args.command == "ingest":
        cmd_ingest(args)
    elif args.command == "status":
        cmd_status(args)


if __name__ == "__main__":
    main()
