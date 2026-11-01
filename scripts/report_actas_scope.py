"""Write a review report of every AP/ICP scope decision in the ACTAS corpus.

Usage (from the repo root)::

    python scripts/report_actas_scope.py [output.md]
"""
from __future__ import annotations

import collections
import glob
import json
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "src" / "python"))

from guidelines import actas_scope as scope  # noqa: E402

_DEFAULT_OUT = ROOT / "docs" / "review" / "actas-scope-tagging.md"


def _docs(pattern: str) -> list[dict]:
    docs = []
    for path in sorted(glob.glob(str(ROOT / pattern))):
        with open(path, encoding="utf-8") as f:
            docs.append(json.load(f))
    return docs


def _label(doc: dict) -> str:
    kind = scope.doc_kind(doc)
    prefix = {"med": "MED", "csm": "", "cmg": "CMG"}[kind]
    return f"{prefix} {doc.get('cmg_number', '')} {doc.get('title', '')}".strip()


def _clip(text: str, limit: int = 160) -> str:
    text = " ".join(text.split()).replace("|", "\\|")
    return text if len(text) <= limit else text[: limit - 1] + "…"


def build_report() -> str:
    cmgs = _docs("data/services/actas/structured/CMG*.json")
    meds = _docs("data/cmgs/structured/med/*.json")
    csms = _docs("data/cmgs/structured/csm/*.json")

    out: list[str] = []
    out.append("## Whole-document scope\n")
    for title, docs in (("Guidelines", cmgs), ("Medicines", meds), ("Clinical skills", csms)):
        groups: dict[str, list[str]] = collections.defaultdict(list)
        for doc in docs:
            groups[scope.document_scope(doc) or "line by line"].append(_label(doc))
        out.append(f"**{title}**\n")
        for key in (scope.ICP, scope.PACER):
            if groups.get(key):
                out.append(f"- {key.upper()}-only: " + "; ".join(groups[key]))
        out.append(f"- Tagged line by line: {len(groups.get('line by line', []))}\n")

    out.append("## Lines hidden from AP users\n")
    out.append("Every line an AP-only user does not see, with the rule that hid it. "
               "Documents that are wholly ICP or PACER are listed above, not here.\n")
    for doc in meds + cmgs + csms:
        if scope.document_scope(doc) is not None:
            continue
        hidden = [s for s in scope.classify(doc) if s.scope != scope.BOTH and s.text.strip()]
        overrides_kept = [
            s for s in scope.classify(doc)
            if s.scope == scope.BOTH and s.reason.startswith("override")
        ]
        if not hidden and not overrides_kept:
            continue
        out.append(f"### {_label(doc)}\n")
        out.append("| Shown to | Line | Why |")
        out.append("|---|---|---|")
        for seg in hidden + overrides_kept:
            who = "ICP" if seg.scope == scope.ICP else seg.scope.upper()
            if seg.scope == scope.BOTH:
                who = "AP and ICP"
            out.append(f"| {who} | {_clip(seg.text)} | {seg.reason} |")
        out.append("")

    out.append("## Dose table entries\n")
    out.append("Weight-band and selector rows from `dose_lookup`. Rows for mixed-scope medicines "
               "whose route or indication cannot be read from the row are kept ICP-only.\n")
    out.append("| Medicine | AP and ICP | ICP only | PACER | Kept ICP because route unclear |")
    out.append("|---|---|---|---|---|")
    counts: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
    ap_rows: dict[str, set[str]] = collections.defaultdict(set)
    for doc in cmgs:
        icp_only = scope.document_scope(doc) == scope.ICP
        for medicine, entries in (doc.get("dose_lookup") or {}).items():
            for entry in entries:
                entry_scope, reason = scope.dose_entry_scope(medicine, entry.get("text", ""), icp_only)
                counts[medicine][entry_scope] += 1
                if reason.startswith("mixed medicine"):
                    counts[medicine]["unclear"] += 1
                if entry_scope == scope.BOTH and scope.drug_scope(medicine) == scope.MIXED_DRUG:
                    ap_rows[medicine].add(_clip(entry.get("text", ""), 120))
    for medicine in sorted(counts):
        c = counts[medicine]
        out.append(f"| {medicine} | {c[scope.BOTH]} | {c[scope.ICP]} | {c[scope.PACER]} | {c['unclear']} |")
    out.append("\nRows of mixed-scope medicines shown to AP users:\n")
    for medicine in sorted(ap_rows):
        for row in sorted(ap_rows[medicine]):
            out.append(f"- {medicine}: {row}")
    return "\n".join(out) + "\n"


def main(argv: list[str]) -> int:
    out_path = Path(argv[0]) if argv else _DEFAULT_OUT
    header_path = out_path.with_suffix(".header.md")
    header = header_path.read_text(encoding="utf-8") if header_path.exists() else ""
    out_path.write_text(header + build_report(), encoding="utf-8")
    print(f"Wrote {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
