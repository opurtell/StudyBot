"""Trace each pooled ACTAS dose line back to the app page whose JavaScript bundle holds it.

Run from the repo root (needs the gitignored scrape artefacts in data/cmgs/raw and data/cmgs/investigation):

    PYTHONPATH=src/python python3 -m web_corpus.dose_provenance

The scrape pools dose lines by medicine (dose_tables.json) with no record of where each line came from.
dose_tables_segmented.json keeps the source bundle per line, and the app's webpack module map
(the bundle holding "./guidelines/<slug>/<slug>.module": [chunk ids]) says which pages load each bundle.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

from paths import APP_ROOT, service_structured_dir

RAW_DIR = APP_ROOT / "data" / "cmgs" / "raw"
BUNDLE_DIR = APP_ROOT / "data" / "cmgs" / "investigation"
OUT_PATH = Path(__file__).with_name("dose_provenance.json")

REFERENCE_CARD = "reference_card"
SHARED_CALCULATOR = "shared_calculator"
REFERENCE_CARD_SLUGS = {"critical-care-reference-cards"}
SHARED_CHUNKS = {"7"}
MODULE_RE = re.compile(r'"\./([a-z-]+)/([a-z0-9-]+)/[a-z0-9-]+\.module":\[([\d,]+)\]')
CATEGORIES = {"guidelines", "medicines", "reference", "calculators", "extra-content"}


def chunk_id(source_file: str) -> str:
    prefix, rest = source_file.split(".", 1)[0].split("_", 1)
    return rest if rest.isdigit() else prefix


def normalise(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().lower()


def line_hash(text: str) -> str:
    return hashlib.sha256(normalise(text).encode("utf-8")).hexdigest()[:16]


def slugify(text: str) -> str:
    text = re.sub(r"\([^)]*\)", " ", text.lower()).replace("&", "and")
    return re.sub(r"[^a-z0-9]+", "-", text).strip("-")


def module_map(bundle_dir: Path) -> dict[str, set[str]]:
    """chunk id -> page slugs ("category/slug") that load it."""
    pages: dict[str, set[str]] = defaultdict(set)
    for path in sorted(bundle_dir.glob("*.js")):
        text = path.read_text(encoding="utf-8", errors="ignore")
        if ".module\":[" not in text:
            continue
        for category, slug, ids in MODULE_RE.findall(text):
            if category not in CATEGORIES:
                continue
            for cid in ids.split(","):
                pages[cid].add(f"{category}/{slug}")
    return pages


def documents(raw_dir: Path) -> tuple[dict[str, str], dict[str, str]]:
    """Page slug -> document id, from the navigation URL where the app gives one, else the title."""
    structured = service_structured_dir("actas")
    ids = {}
    for path in [*structured.glob("*.json"), *(structured / "csm").glob("*.json"), *(structured / "med").glob("*.json")]:
        if path.name.endswith("-index.json"):
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        ids[(str(data.get("cmg_number")), data.get("title"))] = data["id"]
    nav = {p["spotlightId"]: p for p in json.loads((raw_dir / "cmg_navigation.json").read_text(encoding="utf-8"))["all_pages"]}
    by_url: dict[str, list[str]] = defaultdict(list)
    by_title: dict[str, list[str]] = defaultdict(list)
    for g in json.loads((raw_dir / "guidelines.json").read_text(encoding="utf-8")):
        doc_id = ids.get((str(g["cmg_number"]), g["title"]))
        if not doc_id:
            continue
        url = nav.get(g.get("spotlightId"), {}).get("url")
        if url:
            by_url[url].append(doc_id)
        by_title[slugify(g["title"])].append(doc_id)
    return by_url, by_title


def resolve(page: str, by_url: dict[str, list[str]], by_title: dict[str, list[str]]) -> tuple[list[str], str]:
    slug = page.split("/", 1)[1]
    if slug in REFERENCE_CARD_SLUGS:
        return [REFERENCE_CARD], "reference_card"
    if slug in by_title:
        return sorted(set(by_title[slug])), "title"
    if slug in by_url:
        return sorted(set(by_url[slug])), "url"
    prefix = [d for t, docs in by_title.items() if t.startswith(slug + "-") or slug.startswith(t + "-") for d in docs]
    if prefix:
        return sorted(set(prefix)), "title_prefix"
    return [f"page:{page}"], "no_document"


def build_mapping(raw_dir: Path = RAW_DIR, bundle_dir: Path = BUNDLE_DIR) -> dict:
    pages = module_map(bundle_dir)
    by_url, by_title = documents(raw_dir)
    segmented = json.loads((raw_dir / "dose_tables_segmented.json").read_text(encoding="utf-8"))
    pooled = json.loads((raw_dir / "dose_tables.json").read_text(encoding="utf-8"))["medicine_index"]

    origin: dict[str, set[str]] = defaultdict(set)
    for entry in segmented["per_file"]:
        for group in entry["dose_groups"]:
            for text in (group["combined_text"], *group["lines"]):
                origin[normalise(text)].add(entry["source_file"])

    records = []
    for medicine, entries in sorted(pooled.items()):
        for entry in entries:
            text = entry.get("text") or ""
            if entry.get("source"):
                records.append({"medicine": medicine, "hash": line_hash(text), "text": text[:120],
                                "source_files": [], "pages": [], "owner": f"monograph:{entry['source']}",
                                "status": "monograph"})
                continue
            files = sorted(origin.get(normalise(text), set()))
            owners, owner_pages, how = set(), set(), set()
            for source_file in files:
                cid = chunk_id(source_file)
                if cid in SHARED_CHUNKS:
                    owners.add(SHARED_CALCULATOR)
                    how.add("shared_calculator")
                    continue
                for page in sorted(pages.get(cid, ())):
                    owner_pages.add(page)
                    docs, method = resolve(page, by_url, by_title)
                    owners.update(docs)
                    how.add(method)
            if not files:
                status = "unmatched_text"
            elif not owners:
                status = "unmapped"
            elif owners == {SHARED_CALCULATOR}:
                status = "shared_calculator"
            elif owners == {REFERENCE_CARD}:
                status = "reference_card"
            elif len(owners) == 1 and not any(o.startswith("page:") for o in owners):
                status = "clean"
            elif all(o.startswith("page:") for o in owners):
                status = "page_without_document"
            else:
                status = "ambiguous"
            records.append({
                "medicine": medicine,
                "hash": line_hash(text),
                "text": text[:120],
                "source_files": files,
                "pages": sorted(owner_pages),
                "owner": sorted(owners)[0] if len(owners) == 1 else sorted(owners),
                "status": status,
                "matched_by": sorted(how),
            })

    summary = Counter(r["status"] for r in records)
    by_owner = Counter(r["owner"] for r in records if r["status"] == "clean")
    ambiguous = sorted({(r["medicine"], tuple(r["owner"]) if isinstance(r["owner"], list) else (r["owner"],))
                        for r in records if r["status"] in ("ambiguous", "page_without_document")})
    return {
        "summary": {"lines": len(records), **dict(sorted(summary.items()))},
        "clean_by_document": dict(by_owner.most_common()),
        "ambiguous": [{"medicine": m, "owners": list(o)} for m, o in ambiguous],
        "lines": records,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, default=OUT_PATH)
    args = parser.parse_args(argv)
    for needed in (RAW_DIR / "dose_tables_segmented.json", RAW_DIR / "dose_tables.json", BUNDLE_DIR):
        if not needed.exists():
            print(f"Missing scrape artefact: {needed}", file=sys.stderr)
            return 1
    mapping = build_mapping()
    args.out.write_text(json.dumps(mapping, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({k: mapping[k] for k in ("summary", "clean_by_document", "ambiguous")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
