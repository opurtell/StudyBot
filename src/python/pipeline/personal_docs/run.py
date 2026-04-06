"""CLI entrypoint for the personal docs pipeline."""

import logging
import sys
from pathlib import Path

import click

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from paths import APP_ROOT, CHROMA_DB_DIR, DATA_DIR

from .chunker import chunk_and_ingest_directory
from .structurer import structure_directory

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

DEFAULT_SOURCE_ROOT = APP_ROOT / "docs"
DEFAULT_OUTPUT_DIR = DATA_DIR / "personal_docs" / "structured"
DEFAULT_DB_PATH = CHROMA_DB_DIR


@click.group()
def cli():
    """Personal Docs Pipeline — structure and ingest REFdocs/CPDdocs."""
    pass


@cli.command()
@click.option(
    "--source-root", default=str(DEFAULT_SOURCE_ROOT), help="Root docs directory"
)
@click.option(
    "--output-dir", default=str(DEFAULT_OUTPUT_DIR), help="Structured output directory"
)
@click.option("--dry-run", is_flag=True, help="Preview without writing files")
def structure(source_root, output_dir, dry_run):
    """Add YAML front matter to REFdocs and CPDdocs markdown files."""
    source_root = Path(source_root)
    output_dir = Path(output_dir)

    if dry_run:
        click.echo(
            f"[DRY RUN] Would structure files from {source_root} -> {output_dir}"
        )
        ref_count = (
            len(list((source_root / "REFdocs").glob("*.md")))
            if (source_root / "REFdocs").exists()
            else 0
        )
        cpd_count = (
            len(list((source_root / "CPDdocs").glob("*.md")))
            if (source_root / "CPDdocs").exists()
            else 0
        )
        click.echo(f"[DRY RUN] Found {ref_count} REFdocs, {cpd_count} CPDdocs")
        return

    result = structure_directory(source_root, output_dir)
    click.echo(f"Structured {result['processed']} files ({result['errors']} errors)")
    for r in result["results"]:
        click.echo(f"  {r['source_file']} -> {r['categories']}")


@cli.command()
@click.option(
    "--structured-dir",
    default=str(DEFAULT_OUTPUT_DIR),
    help="Structured markdown directory",
)
@click.option("--db-path", default=str(DEFAULT_DB_PATH), help="ChromaDB path")
@click.option("--dry-run", is_flag=True, help="Preview without ingesting")
def ingest(structured_dir, db_path, dry_run):
    """Chunk structured markdown and ingest into ChromaDB."""
    structured_dir = Path(structured_dir)
    db_path = Path(db_path)

    if dry_run:
        md_files = []
        for subdir in ["REFdocs", "CPDdocs"]:
            d = structured_dir / subdir
            if d.exists():
                md_files.extend(d.glob("*.md"))
        click.echo(f"[DRY RUN] Would ingest {len(md_files)} files into {db_path}")
        return

    result = chunk_and_ingest_directory(structured_dir, db_path)
    click.echo(
        f"Ingested {result['processed']} files, {result['total_chunks']} total chunks ({result['errors']} errors)"
    )


@cli.command()
@click.option("--db-path", default=str(DEFAULT_DB_PATH), help="ChromaDB path")
def status(db_path):
    """Report pipeline status."""
    db_path = Path(db_path)

    click.echo("Personal Docs Pipeline Status")
    click.echo(f"  DB path: {db_path}")

    if not db_path.exists():
        click.echo("  ChromaDB not found — run 'ingest' first")
        return

    import chromadb

    client = chromadb.PersistentClient(path=str(db_path))
    try:
        collection = client.get_collection("paramedic_notes")
        count = collection.count()
        click.echo(f"  paramedic_notes collection: {count} total chunks")

        ref = collection.get(where={"source_type": "ref_doc"})
        cpd = collection.get(where={"source_type": "cpd_doc"})
        click.echo(f"    ref_doc chunks: {len(ref['ids'])}")
        click.echo(f"    cpd_doc chunks: {len(cpd['ids'])}")
    except Exception:
        click.echo("  Collection not found")


if __name__ == "__main__":
    cli()
