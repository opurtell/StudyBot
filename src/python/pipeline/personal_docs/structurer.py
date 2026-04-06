"""Structure plain markdown files from REFdocs/CPDdocs with YAML front matter."""

import logging
import re
from datetime import datetime, timezone
from pathlib import Path

import yaml

from ..clinical_dictionary import get_categories_for_file, get_source_type_for_dir

logger = logging.getLogger(__name__)


def _extract_title(content: str, fallback: str) -> str:
    match = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
    if match:
        return match.group(1).strip()
    return Path(fallback).stem


def structure_file(md_path: Path, output_dir: Path, source_dir: str) -> dict:
    content = md_path.read_text(encoding="utf-8")
    relative_path = f"{source_dir}/{md_path.name}"
    title = _extract_title(content, md_path.name)
    source_type = get_source_type_for_dir(source_dir)
    categories = get_categories_for_file(relative_path)

    stat = md_path.stat()
    last_modified = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat()

    front_matter = {
        "title": title,
        "source_type": source_type,
        "source_file": relative_path,
        "categories": categories,
        "last_modified": last_modified,
    }

    out_path = output_dir / source_dir / md_path.name
    out_path.parent.mkdir(parents=True, exist_ok=True)

    yaml_block = yaml.dump(front_matter, default_flow_style=False, allow_unicode=True)
    structured = f"---\n{yaml_block}---\n{content}"

    out_path.write_text(structured, encoding="utf-8")

    return {
        "source_file": relative_path,
        "title": title,
        "source_type": source_type,
        "categories": categories,
        "last_modified": last_modified,
    }


def structure_directory(source_root: Path, output_dir: Path) -> dict:
    dirs = ["REFdocs", "CPDdocs"]
    processed = 0
    errors = 0
    results = []

    for dir_name in dirs:
        dir_path = source_root / dir_name
        if not dir_path.exists():
            logger.warning(f"Directory not found: {dir_path}")
            continue

        for md_file in sorted(dir_path.glob("*.md")):
            try:
                result = structure_file(md_file, output_dir, dir_name)
                results.append(result)
                processed += 1
                logger.info(f"Structured: {result['source_file']}")
            except Exception as e:
                logger.error(f"Failed to structure {md_file}: {e}")
                errors += 1

    return {
        "processed": processed,
        "errors": errors,
        "results": results,
    }
