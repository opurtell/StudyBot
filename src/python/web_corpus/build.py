"""Build the web app's guideline corpus (D1 rows plus embedding inputs) from ACTAS structured JSON.

Run from the repo root:

    PYTHONPATH=src/python python3 -m web_corpus.build --out web/corpus-build

Only ACTAS guideline content (CMGs, clinical skills, medicine monographs) is allowed in. Anything else stops the build.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from guidelines import actas_scope as scope
from guidelines.markdown import normalise_markdown_syntax
from paths import APP_ROOT, service_structured_dir

BUILDER_VERSION = "3"
SERVICE_ID = "actas"
SOURCE_TYPE = "guideline"
ALLOWED_SOURCE_TYPES = frozenset({SOURCE_TYPE})
ALLOWED_INPUT_TYPES = {"cmg": "cmg", "csm": "csm", "med": "med"}
LICENCE = "ACTAS public guidelines"
ATTRIBUTION = "ACT Ambulance Service Clinical Management Guidelines"
SOURCE_URL = "https://cmg.ambulance.act.gov.au"
MAX_CHUNK_CHARS = 1600

VIEWS: dict[str, frozenset[str]] = {
    "ap": frozenset({"AP"}),
    "ap_pacer": frozenset({"AP", "PACER"}),
    "icp": frozenset({"AP", "ICP"}),
    "icp_pacer": frozenset({"AP", "ICP", "PACER"}),
}
SCOPE_VIEWS: dict[str, tuple[str, ...]] = {
    scope.BOTH: tuple(VIEWS),
    scope.ICP: ("icp", "icp_pacer"),
    scope.PACER: ("ap_pacer", "icp_pacer"),
}

_HEADING = re.compile(r"^\s*(#{1,6})\s+(.*\S)\s*$")
_LITERAL_ESCAPE = re.compile(r"\\(?:u([0-9a-fA-F]{4})|x([0-9a-fA-F]{2}))")


class CorpusBuildError(Exception):
    pass


@dataclass
class Chunk:
    id: str
    document_id: str
    ordinal: int
    heading: str
    text: str
    embed_text: str
    views: set[str] = field(default_factory=set)


@dataclass
class Document:
    id: str
    kind: str
    number: str
    title: str
    section: str
    scope: str
    version_date: str | None
    checksum: str
    bodies: dict[str, str]
    context: str
    source_type: str = SOURCE_TYPE
    licence: str = LICENCE
    attribution: str = ATTRIBUTION
    source_url: str = SOURCE_URL


@dataclass
class Corpus:
    version: str
    built_at: str
    source_commit: str | None
    documents: list[Document]
    chunks: list[Chunk]


def input_files(structured_dir: Path) -> list[Path]:
    files: list[Path] = []
    for directory in (structured_dir, structured_dir / "csm", structured_dir / "med"):
        if directory.is_dir():
            files.extend(p for p in sorted(directory.glob("*.json")) if not p.name.endswith("-index.json"))
    return files


def load_document(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or "id" not in data:
        raise CorpusBuildError(f"{path.name}: not a guideline document")
    input_type = (data.get("extraction_metadata") or {}).get("source_type")
    if input_type not in ALLOWED_INPUT_TYPES:
        raise CorpusBuildError(
            f"{path.name}: source_type {input_type!r} is not ACTAS guideline content; only "
            f"{sorted(ALLOWED_INPUT_TYPES)} may enter the web corpus"
        )
    kind = scope.doc_kind(data)
    if kind != ALLOWED_INPUT_TYPES[input_type]:
        raise CorpusBuildError(f"{path.name}: extraction type {input_type!r} does not match document kind {kind!r}")
    return data


def decode_literal_escapes(text: str) -> str:
    def repl(match: re.Match[str]) -> str:
        char = chr(int(match.group(1) or match.group(2), 16))
        return " " if char in "\xa0\u2003" else char

    return _LITERAL_ESCAPE.sub(repl, text)


def _heading_text(line: str) -> str:
    match = _HEADING.match(line)
    return match.group(2).strip().strip("*").strip() if match else line.strip()


def sections(text: str) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    stack: list[tuple[int, str]] = []
    body: list[str] = []

    def flush() -> None:
        content = "\n".join(body).strip()
        if content:
            out.append((" > ".join(h for _, h in stack), content))
        body.clear()

    for line in text.splitlines():
        match = _HEADING.match(line)
        if match:
            flush()
            level = len(match.group(1))
            stack[:] = [h for h in stack if h[0] < level] + [(level, _heading_text(line))]
            continue
        body.append(line)
    flush()
    return out


def _common_heading(paths: list[list[str]]) -> str:
    common: list[str] = []
    for parts in zip(*paths):
        if any(p != parts[0] for p in parts):
            break
        common.append(parts[0])
    return " > ".join(common)


def merge_sections(items: list[tuple[str, str]], limit: int = MAX_CHUNK_CHARS) -> list[tuple[str, str]]:
    groups: list[list[tuple[str, str]]] = []
    size = 0
    for heading, body in items:
        cost = len(body) + len(heading.rsplit(" > ", 1)[-1]) + 8
        if groups and size + cost <= limit:
            groups[-1].append((heading, body))
            size += cost
        else:
            groups.append([(heading, body)])
            size = cost
    merged: list[tuple[str, str]] = []
    for group in groups:
        if len(group) == 1:
            merged.append(group[0])
            continue
        paths = [h.split(" > ") if h else [] for h, _ in group]
        common = _common_heading(paths)
        depth = len(common.split(" > ")) if common else 0
        parts = []
        for path, (_, body) in zip(paths, group):
            label = " > ".join(path[depth:])
            parts.append(f"#### {label}\n{body}" if label else body)
        merged.append((common, "\n\n".join(parts)))
    return merged


def _hard_split(text: str, limit: int) -> list[str]:
    pieces: list[str] = []
    rest = text
    while len(rest) > limit:
        cut = max(rest.rfind(". ", 0, limit), rest.rfind("; ", 0, limit), rest.rfind(" ", 0, limit))
        cut = cut + 1 if cut > limit // 2 else limit
        pieces.append(rest[:cut].strip())
        rest = rest[cut:].strip()
    if rest:
        pieces.append(rest)
    return pieces


def pack(text: str, limit: int = MAX_CHUNK_CHARS) -> list[str]:
    units: list[str] = []
    for para in re.split(r"\n\s*\n", text):
        para = para.strip()
        if not para:
            continue
        if len(para) <= limit:
            units.append(para)
            continue
        for line in para.splitlines():
            units.extend(_hard_split(line, limit) if len(line) > limit else [line])

    chunks: list[str] = []
    current = ""
    for unit in units:
        joiner = "\n\n" if "\n" in unit or (current and "\n" in current) else "\n"
        candidate = f"{current}{joiner}{unit}" if current else unit
        if len(candidate) > limit and current:
            chunks.append(current.strip())
            current = unit
        else:
            current = candidate
    if current.strip():
        chunks.append(current.strip())
    return chunks


def _chunk_id(document_id: str, heading: str, text: str) -> str:
    return hashlib.sha256(f"{document_id}\0{heading}\0{text}".encode("utf-8")).hexdigest()[:32]


def _document_scope(data: dict, bodies: dict[str, str]) -> str:
    whole = scope.document_scope(data)
    if whole == scope.ICP:
        return "icp"
    if whole == scope.PACER:
        return "pacer"
    return "all" if len(set(bodies.values())) == 1 else "mixed"


def build_document(
    data: dict, kind: str | None = None, context: str | None = None, merge: bool = True
) -> tuple[Document, list[Chunk]]:
    content = normalise_markdown_syntax(decode_literal_escapes(data.get("content_markdown") or ""))
    segments = scope.classify(data, content)
    whole = scope.document_scope(data)
    visible = SCOPE_VIEWS[whole] if whole else tuple(VIEWS)
    bodies = {view: scope.render(segments, quals) if view in visible else "" for view, quals in VIEWS.items()}
    context = context or scope.context_header(data)
    doc = Document(
        id=data["id"],
        kind=kind or scope.doc_kind(data),
        number=str(data.get("cmg_number", "")),
        title=data.get("title", ""),
        section=data.get("section") or "Other",
        scope=_document_scope(data, bodies),
        version_date=data.get("version_date"),
        checksum=data.get("checksum") or hashlib.sha256(content.encode("utf-8")).hexdigest(),
        bodies=bodies,
        context=context,
    )

    chunks: dict[str, Chunk] = {}

    def add(heading: str, text: str, views: Iterable[str]) -> None:
        chunk_id = _chunk_id(doc.id, heading, text)
        if chunk_id not in chunks:
            embed_text = "\n".join(part for part in (context, heading, text) if part)
            chunks[chunk_id] = Chunk(chunk_id, doc.id, len(chunks), heading, text, embed_text)
        chunks[chunk_id].views.update(views)

    for view in ("icp_pacer", "icp", "ap_pacer", "ap"):
        parts = sections(bodies[view])
        for heading, section_text in merge_sections(parts) if merge else parts:
            for piece in pack(section_text):
                add(heading, piece, [view])

    return doc, list(chunks.values())


REFERENCE_CARDS_PATH = Path(__file__).with_name("reference_cards.json")
REFERENCE_CARDS_ID = "ACTAS_Critical_Care_Reference_Cards"
REFERENCE_CARDS_TITLE = "Critical Care Reference Cards"
# Card fields that belong to ICP-only skills: intubation (CSM.A10-A13) and front of neck access (CSM.A20/A21).
ICP_CARD_FIELDS = frozenset({"ETT size", "ETT length", "Airtraq", "FONA"})
_ICP_TAG = "**ICP:** "
_ICP_CARD_NOTE = re.compile(r"\bETT\b")  # adrenaline down the ETT is ICP (scope PDF)


def _card_value(value: object) -> str:
    return "; ".join(str(v) for v in value) if isinstance(value, list) else str(value)


def _card_dose_line(row: dict) -> str | None:
    """One dose row as written on the card. Rows whose drug label is garbled in the source are left out."""
    if row.get("label_quirk") or not row.get("drug"):
        return None
    parts = [f"{name}: {row[key]}" for key, name in (
        ("formula", "Formula"), ("preparation", "Preparation"), ("dose", "Dose"), ("volume", "Volume")) if row.get(key)]
    parts.extend(_card_value(o) for o in row.get("other") or [] if str(o).rstrip(": ") != row["drug"])
    return f"{row['drug']}: " + "; ".join(parts)


def reference_card_markdown(bands: list[dict]) -> str:
    """The ACTAS critical care reference cards as one guideline-style document, one heading per weight band.

    Each band stays under a single heading, and is never merged with its neighbours, so every chunk names the
    weight and age its doses are for.
    Lines outside AP scope carry an ICP label, decided by the same rules the guideline dose tables use.
    """
    out: list[str] = []
    for band in bands:
        out.append(f"\n## {band['band']}")
        for section in band.get("sections") or []:
            for group in section.get("groups") or []:
                name = group.get("name") or section.get("heading") or ""
                label = section["heading"] if name == section.get("heading") else f"{section['heading']}: {name}"
                lines: list[str] = []
                for key, value in (group.get("fields") or {}).items():
                    tag = _ICP_TAG if key in ICP_CARD_FIELDS else ""
                    lines.append(f"- {tag}{key}: {_card_value(value)}")
                for row in group.get("drugs") or []:
                    line = _card_dose_line(row)
                    if line is None:
                        continue
                    medicine = row["drug"]
                    drug_scope = scope.drug_scope(medicine)
                    if section.get("heading") == "Advanced Airway Medications":
                        icp = True
                    elif drug_scope is None:
                        icp = False
                    else:
                        icp = scope.dose_entry_scope(medicine, line, False)[0] == scope.ICP
                    lines.append(f"- {_ICP_TAG if icp else ''}{line}")
                for note in group.get("notes") or []:
                    tag = _ICP_TAG if _ICP_CARD_NOTE.search(note) else ""
                    lines.append(f"- {tag}{note}")
                if lines:
                    out.append(f"**{label}**")
                    out.extend(lines)
    return "\n".join(out).strip() + "\n"


def reference_card_document(path: Path = REFERENCE_CARDS_PATH) -> dict | None:
    if not path.is_file():
        return None
    content = reference_card_markdown(json.loads(path.read_text(encoding="utf-8")))
    return {
        "id": REFERENCE_CARDS_ID,
        "cmg_number": "REF",
        "title": REFERENCE_CARDS_TITLE,
        "section": "Reference",
        "version_date": None,
        "checksum": hashlib.sha256(content.encode("utf-8")).hexdigest(),
        "content_markdown": content,
    }


def _source_commit() -> str | None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=APP_ROOT, capture_output=True, text=True, check=True
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return result.stdout.strip() or None


def _version(documents: list[Document], chunks: list[Chunk]) -> str:
    digest = hashlib.sha256(f"builder:{BUILDER_VERSION}\n".encode("utf-8"))
    for doc in documents:
        digest.update(json.dumps([doc.id, doc.kind, doc.number, doc.title, doc.section, doc.scope,
                                  doc.version_date, doc.checksum, doc.bodies], sort_keys=True).encode("utf-8"))
    for chunk in chunks:
        digest.update(f"{chunk.id}:{','.join(sorted(chunk.views))}\n".encode("utf-8"))
    return digest.hexdigest()[:16]


def check_allowlist(corpus: Corpus) -> None:
    for doc in corpus.documents:
        if doc.source_type not in ALLOWED_SOURCE_TYPES:
            raise CorpusBuildError(f"{doc.id}: source_type {doc.source_type!r} is not allowed in the web corpus")
    doc_ids = {doc.id for doc in corpus.documents}
    for chunk in corpus.chunks:
        if chunk.document_id not in doc_ids:
            raise CorpusBuildError(f"chunk {chunk.id} belongs to no allowed document")
        if not chunk.views:
            raise CorpusBuildError(f"chunk {chunk.id} is visible to no qualification")


def build(structured_dir: Path | None = None, built_at: str | None = None) -> Corpus:
    """Build from ``structured_dir``; the default ACTAS data also brings in the critical care reference cards."""
    with_cards = structured_dir is None
    structured_dir = structured_dir or service_structured_dir(SERVICE_ID)
    files = input_files(structured_dir)
    if not files:
        raise CorpusBuildError(f"no guideline JSON found in {structured_dir}")
    documents: list[Document] = []
    chunks: list[Chunk] = []
    seen: set[str] = set()
    for path in files:
        data = load_document(path)
        if data["id"] in seen:
            raise CorpusBuildError(f"{path.name}: duplicate document id {data['id']}")
        seen.add(data["id"])
        doc, doc_chunks = build_document(data)
        documents.append(doc)
        chunks.extend(doc_chunks)
    cards = reference_card_document() if with_cards else None
    if cards is not None:
        # Listed with the clinical skills: a reference tool, not a guideline with a CMG number.
        doc, doc_chunks = build_document(
            cards, kind="csm", context=f"[ACTAS {REFERENCE_CARDS_TITLE}]", merge=False
        )
        documents.append(doc)
        chunks.extend(doc_chunks)
    corpus = Corpus(
        version=_version(documents, chunks),
        built_at=built_at or datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        source_commit=_source_commit(),
        documents=documents,
        chunks=chunks,
    )
    check_allowlist(corpus)
    return corpus


def _sql(value: object) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, int):
        return str(value)
    return "'" + str(value).replace("'", "''") + "'"


def _row(values: Iterable[object]) -> str:
    return "(" + ", ".join(_sql(v) for v in values) + ")"


NOW_MS = "CAST(unixepoch('subsec') * 1000 AS INTEGER)"


def to_sql(corpus: Corpus) -> str:
    v = _sql(corpus.version)
    lines = [
        f"INSERT INTO corpus_versions (version, service, built_at, source_commit, documents, chunks, loaded_at, is_current) "
        f"VALUES ({v}, {_sql(SERVICE_ID)}, {_sql(corpus.built_at)}, {_sql(corpus.source_commit)}, "
        f"{len(corpus.documents)}, {len(corpus.chunks)}, {NOW_MS}, 0) "
        f"ON CONFLICT (version) DO UPDATE SET loaded_at = excluded.loaded_at;"
    ]
    for doc in corpus.documents:
        lines.append(
            "INSERT INTO corpus_documents (id, service, kind, number, title, section, scope, version_date, checksum, "
            "source_type, licence, attribution, source_url, corpus_version) VALUES "
            + _row([doc.id, SERVICE_ID, doc.kind, doc.number, doc.title, doc.section, doc.scope, doc.version_date,
                    doc.checksum, doc.source_type, doc.licence, doc.attribution, doc.source_url, corpus.version])
            + " ON CONFLICT (id) DO UPDATE SET service = excluded.service, kind = excluded.kind, "
            "number = excluded.number, title = excluded.title, section = excluded.section, scope = excluded.scope, "
            "version_date = excluded.version_date, checksum = excluded.checksum, source_type = excluded.source_type, "
            "licence = excluded.licence, attribution = excluded.attribution, source_url = excluded.source_url, "
            "corpus_version = excluded.corpus_version;"
        )
        for view, markdown in doc.bodies.items():
            lines.append(
                "INSERT INTO corpus_document_bodies (document_id, view, markdown) VALUES "
                + _row([doc.id, view, markdown])
                + " ON CONFLICT (document_id, view) DO UPDATE SET markdown = excluded.markdown;"
            )
    for chunk in corpus.chunks:
        flags = [view in chunk.views for view in VIEWS]
        lines.append(
            "INSERT INTO corpus_chunks (id, document_id, ordinal, heading, text, embed_text, vis_ap, vis_ap_pacer, "
            "vis_icp, vis_icp_pacer, source_type, licence, attribution, corpus_version) VALUES "
            + _row([chunk.id, chunk.document_id, chunk.ordinal, chunk.heading, chunk.text, chunk.embed_text, *flags,
                    SOURCE_TYPE, LICENCE, ATTRIBUTION, corpus.version])
            + " ON CONFLICT (id) DO UPDATE SET document_id = excluded.document_id, ordinal = excluded.ordinal, "
            "heading = excluded.heading, text = excluded.text, embed_text = excluded.embed_text, "
            "vis_ap = excluded.vis_ap, vis_ap_pacer = excluded.vis_ap_pacer, vis_icp = excluded.vis_icp, "
            "vis_icp_pacer = excluded.vis_icp_pacer, source_type = excluded.source_type, licence = excluded.licence, "
            "attribution = excluded.attribution, corpus_version = excluded.corpus_version, retired_at = NULL, "
            "embedded_at = CASE WHEN corpus_chunks.vis_ap = excluded.vis_ap AND corpus_chunks.vis_ap_pacer = excluded.vis_ap_pacer "
            "AND corpus_chunks.vis_icp = excluded.vis_icp AND corpus_chunks.vis_icp_pacer = excluded.vis_icp_pacer "
            "THEN corpus_chunks.embedded_at ELSE NULL END;"
        )
    lines += [
        f"UPDATE corpus_chunks SET retired_at = {NOW_MS} WHERE corpus_version != {v} AND retired_at IS NULL;",
        f"DELETE FROM corpus_documents WHERE service = {_sql(SERVICE_ID)} AND corpus_version != {v};",
        f"UPDATE corpus_versions SET is_current = CASE WHEN version = {v} THEN 1 ELSE 0 END WHERE service = {_sql(SERVICE_ID)};",
    ]
    return "\n".join(lines) + "\n"


def manifest(corpus: Corpus) -> dict:
    by_kind: dict[str, int] = {}
    for doc in corpus.documents:
        by_kind[doc.kind] = by_kind.get(doc.kind, 0) + 1
    return {
        "version": corpus.version,
        "service": SERVICE_ID,
        "built_at": corpus.built_at,
        "source_commit": corpus.source_commit,
        "documents": len(corpus.documents),
        "documents_by_kind": by_kind,
        "chunks": len(corpus.chunks),
        "chunk_chars": sum(len(c.embed_text) for c in corpus.chunks),
        "source_types": sorted({d.source_type for d in corpus.documents}),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--structured-dir", type=Path, default=None)
    parser.add_argument("--out", type=Path, default=APP_ROOT / "web" / "corpus-build")
    args = parser.parse_args(argv)
    try:
        corpus = build(args.structured_dir)
    except CorpusBuildError as exc:
        print(f"Corpus build failed: {exc}", file=sys.stderr)
        return 1
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "corpus.sql").write_text(to_sql(corpus), encoding="utf-8")
    info = manifest(corpus)
    (args.out / "manifest.json").write_text(json.dumps(info, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(info, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
