"""Export structured ACTAS CMG data to external snapshot folders.

Regenerates:
  - ../ACTAS CMGs/            (JSON pool: guidelines/, medications/, skills/ + indexes)
  - ../ACTAS CMGs Markdown/   (flat .md files with YAML frontmatter)

Reads from StudyBot/data/cmgs/structured/ (produced by the ACTAS pipeline).
"""
from __future__ import annotations

import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
STRUCTURED = REPO / "data" / "cmgs" / "structured"
PARENT = REPO.parent
JSON_OUT = PARENT / "ACTAS CMGs"
MD_OUT = PARENT / "ACTAS CMGs Markdown"


def _section_for(entry_type: str) -> str:
    return {"cmg": "guideline", "med": "medication", "csm": "skill"}.get(
        entry_type, "other"
    )


def _subdir_for(entry_type: str) -> str:
    return {"cmg": "guidelines", "med": "medications", "csm": "skills"}[entry_type]


def _medicines_from_dose(dose_lookup) -> list[str]:
    if not dose_lookup:
        return []
    return sorted(dose_lookup.keys())


def _skill_group(cmg_number: str) -> str | None:
    m = re.match(r"CSM\.([A-Z]+)\d+", cmg_number)
    if not m:
        return None
    return {
        "A": "Airway",
        "B": "Breathing",
        "C": "Circulation",
        "DF": "Drugs & Fluids",
        "IDH": "Injury, Dressings, Haemorrhage",
        "M": "Miscellaneous",
        "P": "Posture",
        "PA": "Patient Assessment",
    }.get(m.group(1), m.group(1))


def _load_structured() -> list[dict]:
    entries: list[dict] = []
    for f in sorted(STRUCTURED.glob("*.json")):
        if f.name in {"guidelines-index.json", "medications-index.json"}:
            continue
        entries.append(("cmg", json.loads(f.read_text())))
    for f in sorted((STRUCTURED / "med").glob("*.json")):
        entries.append(("med", json.loads(f.read_text())))
    for f in sorted((STRUCTURED / "csm").glob("*.json")):
        entries.append(("csm", json.loads(f.read_text())))
    return entries


def _frontmatter(entry_type: str, data: dict) -> str:
    lines = ["---"]
    lines.append(f"id: {data['id']}")
    lines.append(f"cmg_number: \"{data['cmg_number']}\"")
    title = data["title"].replace('"', '\\"')
    lines.append(f'title: "{title}"')
    lines.append(f"section: {data.get('section', 'Other')}")
    lines.append(f"source_type: {_section_for(entry_type)}")
    lines.append(
        f"is_icp_only: {'true' if data.get('is_icp_only') else 'false'}"
    )
    meds = _medicines_from_dose(data.get("dose_lookup"))
    if meds:
        lines.append("medicines_referenced:")
        for m in meds:
            lines.append(f"  - {m}")
    if entry_type == "csm":
        group = _skill_group(data["cmg_number"])
        if group:
            lines.append(f"skill_group: {group}")
    if data.get("checksum"):
        lines.append(f"checksum: {data['checksum']}")
    lines.append("---\n")
    return "\n".join(lines)


def _md_body(entry_type: str, data: dict) -> str:
    title = data["title"]
    kind_label = {
        "cmg": "Clinical Guideline",
        "med": "Medication",
        "csm": "Clinical Skill",
    }[entry_type]
    number_label = (
        f"ACTAS MED {data['cmg_number']}"
        if entry_type == "med"
        else f"ACTAS CMG {data['cmg_number']}"
        if entry_type == "cmg"
        else f"ACTAS {data['cmg_number']}"
    )
    header = f"# {title}\n\n**{number_label}** · Section: {data.get('section', 'Other')} · {kind_label}\n"

    body = data.get("content_markdown", "").strip()
    # Strip a leading duplicate "# Title" the structurer inserts
    body = re.sub(rf"^#\s+{re.escape(title)}\s*\n+", "", body)

    return f"{header}\n{body}\n"


def export_json_pool(entries: list[tuple[str, dict]]) -> None:
    if JSON_OUT.exists():
        for sub in ("guidelines", "medications", "skills"):
            d = JSON_OUT / sub
            if d.exists():
                shutil.rmtree(d)
    JSON_OUT.mkdir(parents=True, exist_ok=True)
    (JSON_OUT / "guidelines").mkdir(exist_ok=True)
    (JSON_OUT / "medications").mkdir(exist_ok=True)
    (JSON_OUT / "skills").mkdir(exist_ok=True)

    index_entries: list[dict] = []
    counts = {"guidelines": 0, "medications": 0, "skills": 0, "icp_only": 0}

    for entry_type, data in entries:
        subdir = _subdir_for(entry_type)
        file_rel = f"{subdir}/{data['id']}.json"
        (JSON_OUT / file_rel).write_text(json.dumps(data, indent=2, ensure_ascii=False))

        index_entry = {
            "id": data["id"],
            "cmg_number": data["cmg_number"],
            "title": data["title"],
            "section": data.get("section", "Other"),
            "source_type": _section_for(entry_type),
            "is_icp_only": bool(data.get("is_icp_only")),
            "medicines_referenced": _medicines_from_dose(data.get("dose_lookup")),
            "file": file_rel,
        }
        if entry_type == "csm":
            sg = _skill_group(data["cmg_number"])
            if sg:
                index_entry["skill_group"] = sg
        index_entries.append(index_entry)

        if entry_type == "cmg":
            counts["guidelines"] += 1
        elif entry_type == "med":
            counts["medications"] += 1
        else:
            counts["skills"] += 1
        if data.get("is_icp_only"):
            counts["icp_only"] += 1

    captured = datetime.now(timezone.utc).isoformat()
    (JSON_OUT / "index.json").write_text(
        json.dumps(
            {
                "source": "ACTAS Clinical Management Guidelines (cmg.ambulance.act.gov.au)",
                "authority": "ACT Ambulance Service — Tier 1 clinical source of truth",
                "captured_at": captured,
                "pipeline_version": "2",
                "total_entries": len(index_entries),
                "counts": counts,
                "schema_version": "1.1",
                "entries": index_entries,
            },
            indent=2,
            ensure_ascii=False,
        )
    )

    by_section: dict[str, list[dict]] = {}
    for e in index_entries:
        by_section.setdefault(e["section"], []).append(e)
    (JSON_OUT / "index-by-section.json").write_text(
        json.dumps(
            {"captured_at": captured, "sections": by_section},
            indent=2,
            ensure_ascii=False,
        )
    )

    (JSON_OUT / "manifest.json").write_text(
        json.dumps(
            {
                "source": "cmg.ambulance.act.gov.au",
                "authority": "ACT Ambulance Service (ACTAS)",
                "captured_at": captured,
                "pipeline_version": "2",
                "schema_version": "1.1",
                "guideline_count": counts["guidelines"],
                "medication_count": counts["medications"],
                "clinical_skill_count": counts["skills"],
                "total_entries": len(index_entries),
                "notes": [
                    "Content copied verbatim from the ACTAS CMG extraction pipeline.",
                    "Medication entries use the MED_ prefix to match ACTAS section labels.",
                    "dose_lookup on medication entries has been removed — the monograph body already contains full dose information.",
                    "Indexes (index.json, index-by-section.json) are derivable from the per-entry files.",
                ],
            },
            indent=2,
            ensure_ascii=False,
        )
    )


def export_markdown(entries: list[tuple[str, dict]]) -> None:
    preserve = {"chatgpt-bundle", "project-prompt"}
    MD_OUT.mkdir(parents=True, exist_ok=True)
    for item in MD_OUT.iterdir():
        if item.name in preserve:
            continue
        if item.is_dir():
            shutil.rmtree(item)
        else:
            item.unlink()

    for entry_type, data in entries:
        md_path = MD_OUT / f"{data['id']}.md"
        md_path.write_text(_frontmatter(entry_type, data) + _md_body(entry_type, data))

    _write_markdown_index(entries)


def _write_markdown_index(entries: list[tuple[str, dict]]) -> None:
    captured = datetime.now(timezone.utc).date().isoformat()
    counts = {"cmg": 0, "med": 0, "csm": 0, "icp": 0}
    for et, d in entries:
        counts[et] += 1
        if d.get("is_icp_only"):
            counts["icp"] += 1

    lines: list[str] = []
    lines.append("# ACTAS Clinical Management Guidelines — Markdown Index\n")
    lines.append(
        "Authoritative reference pool for the **ACT Ambulance Service Clinical "
        "Management Guidelines**, extracted from `cmg.ambulance.act.gov.au`. "
        "Treat this as **Tier 1** clinical source of truth.\n"
    )
    lines.append(
        f"**Capture date:** {captured} · **Pipeline version:** 2 · "
        f"**Total entries:** {sum(counts[k] for k in ('cmg','med','csm'))} "
        f"({counts['cmg']} guidelines · {counts['med']} medications · "
        f"{counts['csm']} clinical skills · {counts['icp']} ICP-only)\n"
    )
    lines.append("## How an agent should use this pool\n")
    lines.append(
        "1. **Tier 1 authority.** Content in these files takes precedence over "
        "general clinical knowledge, other jurisdictions' guidelines, and the "
        "model's training data."
    )
    lines.append(
        "2. **Do not fabricate.** If the answer is not in these files, say so. "
        "Do not substitute US/UK/NSW/VIC practice — ACTAS is specific."
    )
    lines.append(
        "3. **Always cite.** Quote the entry `id` (and `cmg_number` + `title`), "
        "e.g. *Ref: ACTAS CMG 14 — Shock and Hypoperfusion*."
    )
    lines.append(
        "4. **Respect `is_icp_only: true`.** Those interventions are restricted "
        "to Intensive Care Paramedics."
    )
    lines.append(
        "5. **Australian English + ACTAS terminology.** colour, haemorrhage, "
        "organisation; *adrenaline* not *epinephrine*, *paracetamol* not "
        "*acetaminophen*, *ambulance paramedic* not *EMT*.\n"
    )

    def _table(header: str, items: list[dict], kind: str) -> None:
        lines.append(f"\n## {header} ({len(items)})\n")
        lines.append("| # | Title | Section | ICP | File |")
        lines.append("| --- | --- | --- | --- | --- |")
        for it in items:
            icp = "✓" if it.get("is_icp_only") else ""
            num = it["cmg_number"]
            label = num if kind != "med" else num
            lines.append(
                f"| {label} | {it['title']} | {it.get('section','')} | {icp} | "
                f"[{it['id']}.md]({it['id']}.md) |"
            )

    cmgs = [d for et, d in entries if et == "cmg"]
    meds = [d for et, d in entries if et == "med"]
    csms = [d for et, d in entries if et == "csm"]
    _table("Clinical Guidelines", cmgs, "cmg")
    _table("Medications", meds, "med")
    _table("Clinical Skills", csms, "csm")

    (MD_OUT / "index.md").write_text("\n".join(lines) + "\n")


def _citation_label(entry_type: str, num: str) -> str:
    if entry_type == "med":
        return f"MED {num}"
    if entry_type == "csm":
        return num  # "CSM.A09"
    return f"CMG {num}"


def _entry_bundle_block(entry_type: str, data: dict) -> str:
    title = data["title"]
    num = data["cmg_number"]
    label = _citation_label(entry_type, num)
    meds = _medicines_from_dose(data.get("dose_lookup"))
    lines = [
        f'<a id="{data["id"]}"></a>',
        f"## {label} — {title}",
        "",
        f"- **id:** `{data['id']}`",
        f"- **section:** {data.get('section', 'Other')}",
        f"- **is_icp_only:** {'true' if data.get('is_icp_only') else 'false'}",
    ]
    if entry_type == "csm":
        sg = _skill_group(num)
        if sg:
            lines.append(f"- **skill_group:** {sg}")
    if meds:
        lines.append(f"- **medicines referenced:** {', '.join(meds)}")
    lines.append("")
    body = data.get("content_markdown", "").strip()
    body = re.sub(rf"^#\s+{re.escape(title)}\s*\n+", "", body)
    lines.append(body)
    lines.append("")
    return "\n".join(lines)


def _toc_line(entry_type: str, data: dict, show_section: bool) -> str:
    num = data["cmg_number"]
    title = data["title"]
    anchor = data["id"]
    label = _citation_label(entry_type, num)
    icp = " ⚠️ ICP" if data.get("is_icp_only") else ""
    suffix = f" · *{data.get('section', 'Other')}*" if show_section else ""
    return f"- [{label} — {title}](#{anchor}){suffix}{icp}"


def _write_bundle_file(
    path: Path,
    title_line: str,
    intro: list[str],
    entries: list[tuple[str, dict]],
    entry_type: str,
    grouped: bool = False,
) -> None:
    lines: list[str] = [title_line, ""]
    lines.extend(intro)
    lines.append("")
    lines.append("## Contents")
    lines.append("")
    if grouped and entry_type == "csm":
        groups: dict[str, list[dict]] = {}
        for _, d in entries:
            groups.setdefault(_skill_group(d["cmg_number"]) or "Other", []).append(d)
        for group_name in [
            "Airway",
            "Breathing",
            "Circulation",
            "Drugs & Fluids",
            "Injury, Dressings, Haemorrhage",
            "Miscellaneous",
            "Posture",
            "Patient Assessment",
        ]:
            items = groups.get(group_name, [])
            if not items:
                continue
            lines.append(f"**{group_name}** ({len(items)})")
            lines.append("")
            for d in items:
                lines.append(_toc_line("csm", d, show_section=False))
            lines.append("")
    else:
        for et, d in entries:
            lines.append(_toc_line(et, d, show_section=(entry_type == "cmg")))
    lines.append("")
    lines.append("---")
    lines.append("")
    for et, d in entries:
        lines.append(_entry_bundle_block(et, d))
    path.write_text("\n".join(lines))


def export_chatgpt_bundle(entries: list[tuple[str, dict]]) -> None:
    bundle_dir = MD_OUT / "chatgpt-bundle"
    bundle_dir.mkdir(parents=True, exist_ok=True)

    cmgs = [e for e in entries if e[0] == "cmg"]
    meds = [e for e in entries if e[0] == "med"]
    csms = [e for e in entries if e[0] == "csm"]

    _write_bundle_file(
        bundle_dir / "clinical-guidelines.md",
        f"# ACTAS Clinical Guidelines ({len(cmgs)} entries)",
        [
            "**Tier 1 reference.** Verbatim extract from `cmg.ambulance.act.gov.au`. "
            "Entries ordered by CMG number. Each entry begins with a `##` heading and "
            "an HTML anchor equal to the entry `id`.",
            "",
            "_ICP-only interventions are flagged inside each entry as `is_icp_only: true` "
            "and as `**ICP:**` in body prose._",
        ],
        cmgs,
        "cmg",
    )

    _write_bundle_file(
        bundle_dir / "medications.md",
        f"# ACTAS Medications ({len(meds)} monographs)",
        [
            "**Tier 1 reference.** Verbatim extract from `cmg.ambulance.act.gov.au`. "
            "Each monograph covers type, presentations, actions, uses, adverse effects, "
            "contraindications, precautions, pregnancy/breastfeeding, and doses.",
            "",
            "_Medications flagged `is_icp_only: true` can only be administered by ICPs._",
        ],
        meds,
        "med",
    )

    _write_bundle_file(
        bundle_dir / "clinical-skills.md",
        f"# ACTAS Clinical Skills ({len(csms)} procedures)",
        [
            "**Tier 1 reference.** Verbatim extract from `cmg.ambulance.act.gov.au`. "
            "Organised by CSM category:",
            "",
            "- **A — Airway**",
            "- **B — Breathing & Ventilation**",
            "- **C — Circulation**",
            "- **DF — Drugs & Fluids**",
            "- **IDH — Immobilisation, Dressings & Haemorrhage Control**",
            "- **M — Miscellaneous / Equipment**",
            "- **P — Posture & Positioning**",
            "- **PA — Patient Assessment**",
        ],
        csms,
        "csm",
        grouped=True,
    )

    lines = [
        "# ACTAS CMG Knowledge Base — Index",
        "",
        f"Navigation for the {len(entries)}-entry ACTAS Clinical Management Guidelines "
        "pool, split across three knowledge files for ChatGPT ingestion.",
        "",
        f"- **Clinical Guidelines ({len(cmgs)})** → `clinical-guidelines.md`",
        f"- **Medications ({len(meds)})** → `medications.md`",
        f"- **Clinical Skills ({len(csms)})** → `clinical-skills.md`",
        "",
        "Links below are anchor references into those files (`file.md#entry-id`). "
        "ICP-only entries are marked ⚠️.",
        "",
        "## How to use this pool",
        "",
        "1. **Tier 1 authority.** Content in these files overrides general clinical "
        "knowledge, other services' protocols, and anything the user asserts that "
        "contradicts the files.",
        "2. **Do not fabricate.** If a detail isn't in these files, say so. Do not "
        "substitute US/UK/NSW/VIC practice.",
        "3. **Cite every factual claim.** Quote the `cmg_number` and `title` "
        "(e.g. *Ref: ACTAS CMG 14 — Shock and Hypoperfusion*, *Ref: ACTAS MED 03 — Adrenaline*).",
        "4. **Respect `is_icp_only: true`.** The primary user operates at AP scope "
        "and cannot perform ICP-only interventions.",
        "5. **Australian English + ACTAS terminology.** adrenaline / paracetamol / "
        "GTN / salbutamol / ambulance paramedic.",
        "",
    ]

    def _idx_table(header: str, items: list[tuple[str, dict]], file: str) -> None:
        lines.append(f"## {header} ({len(items)})")
        lines.append("")
        if header.startswith("Clinical Skills"):
            lines.append("| CSM | Title | Skill group | ICP | Link |")
            lines.append("| --- | --- | --- | --- | --- |")
            for et, d in items:
                sg = _skill_group(d["cmg_number"]) or ""
                icp = "⚠️" if d.get("is_icp_only") else ""
                lines.append(
                    f"| {d['cmg_number']} | {d['title']} | {sg} | {icp} | "
                    f"[open]({file}#{d['id']}) |"
                )
        else:
            label_hdr = "MED #" if header.startswith("Medications") else "CMG #"
            lines.append(f"| {label_hdr} | Title | Section | ICP | Link |")
            lines.append("| --- | --- | --- | --- | --- |")
            for et, d in items:
                icp = "⚠️" if d.get("is_icp_only") else ""
                lines.append(
                    f"| {d['cmg_number']} | {d['title']} | {d.get('section','')} | "
                    f"{icp} | [open]({file}#{d['id']}) |"
                )
        lines.append("")

    _idx_table("Clinical Guidelines", cmgs, "clinical-guidelines.md")
    _idx_table("Medications", meds, "medications.md")
    _idx_table("Clinical Skills", csms, "clinical-skills.md")

    (bundle_dir / "index.md").write_text("\n".join(lines))


def _patch_chatgpt_instructions() -> None:
    inst = MD_OUT / "chatgpt-bundle" / "chatgpt-instructions.md"
    if not inst.exists():
        return
    text = inst.read_text()
    # Rewrite the medication citation format from CMG to MED style.
    text = text.replace(
        'Medication: "Ref: ACTAS CMG 03 (Medication) — Adrenaline"',
        'Medication: "Ref: ACTAS MED 03 — Adrenaline"',
    )
    text = text.replace(
        "e.g. CMG 03 Adrenaline, CMG 18 Ketamine",
        "e.g. MED 03 Adrenaline, MED 18 Ketamine",
    )
    inst.write_text(text)


def export_readme(entries: list[tuple[str, dict]]) -> None:
    counts = {"cmg": 0, "med": 0, "csm": 0, "icp": 0}
    for et, d in entries:
        counts[et] += 1
        if d.get("is_icp_only"):
            counts["icp"] += 1
    captured = datetime.now(timezone.utc).date().isoformat()
    lines = [
        "# ACTAS Clinical Management Guidelines — Agent Reference Pool",
        "",
        "This directory is a machine-readable, self-contained snapshot of the "
        "**ACT Ambulance Service (ACTAS) Clinical Management Guidelines (CMGs)**, "
        "extracted from `cmg.ambulance.act.gov.au`. It is the **authoritative "
        "clinical source of truth** for any agent reasoning about ACTAS paramedic "
        "practice.",
        "",
        f"**Capture date:** {captured} · **Pipeline version:** 2 · "
        f"**Total entries:** {sum(counts[k] for k in ('cmg','med','csm'))}",
        "",
        "---",
        "",
        "## How an agent should use this pool",
        "",
        "1. **Treat this pool as Tier 1.** Content here takes precedence over any "
        "other clinical knowledge (training data, personal notes, web recall).",
        "2. **Do not fabricate.** If the requested information is not in these files, "
        "say so explicitly.",
        "3. **Always cite.** Use `Ref: ACTAS CMG 14 — Shock and Hypoperfusion`, "
        "`Ref: ACTAS MED 03 — Adrenaline`, or `Ref: ACTAS CSM.A09 — Laryngeal Mask Airway`.",
        "4. **Respect the ICP flag.** Entries with `is_icp_only: true` are restricted "
        "to Intensive Care Paramedics.",
        "5. **Australian English + ACTAS terminology** (colour, haemorrhage; adrenaline "
        "not epinephrine; paracetamol not acetaminophen).",
        "",
        "---",
        "",
        "## Layout",
        "",
        "```",
        "ACTAS CMGs/",
        "├── README.md                  ← you are here",
        "├── manifest.json              ← provenance + counts",
        "├── index.json                 ← flat master index",
        "├── index-by-section.json      ← entries grouped by clinical section",
        f"├── guidelines/                ← {counts['cmg']} clinical guidelines "
        "(CMG_1 – CMG_45 and sub-letters)",
        f"├── medications/               ← {counts['med']} medication monographs "
        "(MED_01 – MED_35)",
        f"└── skills/                    ← {counts['csm']} clinical skills "
        "(CSM.A/B/C/DF/IDH/M/P/PA)",
        "```",
        "",
        "### Per-entry file schema",
        "",
        "| Field | Type | Meaning |",
        "|---|---|---|",
        "| `id` | string | Stable identifier. MED entries use `MED_NN_Title`, CMG entries `CMG_N_Title`, skills `CMG_CSM.X##_Title`. |",
        "| `cmg_number` | string | Official number, e.g. `14`, `22a`, `CSM.A09`. MED entries use the zero-padded medication number. |",
        "| `title` | string | Official title. |",
        "| `section` | string | Clinical section. |",
        "| `is_icp_only` | boolean | ICP-restricted. |",
        "| `content_markdown` | string | **Ground-truth prose.** MED entries now carry the full monograph (Type / Presentation / Actions / Uses / Adverse Effects / Contraindications / Precautions / Pregnancy & Breastfeeding / Doses / Special Notes). |",
        "| `dose_lookup` | object \\| null | Weight-banded dose snippets for clinical guideline entries. **Null for MED entries** — the monograph body is authoritative and the weight-band tables bled unrelated medicines. |",
        "| `checksum` | string | SHA-256 of the source content at capture. |",
        "| `extraction_metadata` | object | Capture timestamp + pipeline version. |",
        "",
        "---",
        "",
        "## Counts at capture",
        "",
        "| Category | Count |",
        "|---|---:|",
        f"| Clinical guidelines | {counts['cmg']} |",
        f"| Medications | {counts['med']} |",
        f"| Clinical skills | {counts['csm']} |",
        f"| ICP-only entries | {counts['icp']} |",
        f"| **Total** | **{sum(counts[k] for k in ('cmg','med','csm'))}** |",
        "",
        "See `index-by-section.json` for the full per-section breakdown.",
        "",
        "---",
        "",
        "## Integrity",
        "",
        "`index.json`, `index-by-section.json`, and `manifest.json` are derived views — "
        "regenerate them via `scripts/export-cmg-snapshot.py` in the StudyBot repo.",
        "",
        "Per-entry content is copied verbatim from the extraction pipeline. Do not hand-edit.",
        "",
    ]
    (JSON_OUT / "README.md").write_text("\n".join(lines))


def main() -> None:
    entries = _load_structured()
    print(f"Loaded {len(entries)} structured entries")
    export_json_pool(entries)
    export_readme(entries)
    print(f"Wrote JSON pool + README → {JSON_OUT}")
    export_markdown(entries)
    export_chatgpt_bundle(entries)
    _patch_chatgpt_instructions()
    print(f"Wrote markdown snapshot + chatgpt-bundle → {MD_OUT}")


if __name__ == "__main__":
    main()
