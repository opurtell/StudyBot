"""ACTAS AP/ICP scope tagging for guideline, medication and clinical skill text.

Sources:
- Oscar's medication scope list (2026-11-01)
- Oscar's clinical skills scope list (2026-11-01), which overrides the PDF for skills
- ACTAS Scope of Practice, POLACTAS001 Attachment A (reviewed 12/09/2024)

See Guides/scope-of-practice-actas.md for the transcribed tables.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable

BOTH = "both"
ICP = "icp"
PACER = "pacer"

AP_DRUG = "ap"
ICP_DRUG = "icp"
MIXED_DRUG = "mixed"
PACER_DRUG = "pacer"

DRUG_SCOPE: dict[str, str] = {
    "aspirin": AP_DRUG,
    "adenosine": ICP_DRUG,
    "adrenaline": MIXED_DRUG,
    "amiodarone": ICP_DRUG,
    "atropine": MIXED_DRUG,
    "calcium chloride": ICP_DRUG,
    "ceftriaxone": AP_DRUG,
    "droperidol": AP_DRUG,
    "fentanyl": MIXED_DRUG,
    "glucagon": AP_DRUG,
    "glucose 10%": AP_DRUG,
    "oral glucose gel": AP_DRUG,
    "glyceryl trinitrate": AP_DRUG,
    "heparin": ICP_DRUG,
    "hydrocortisone": ICP_DRUG,
    "ibuprofen": AP_DRUG,
    "ipratropium bromide": AP_DRUG,
    "ketamine": MIXED_DRUG,
    "levetiracetam": ICP_DRUG,
    "lignocaine": ICP_DRUG,
    "magnesium sulphate": MIXED_DRUG,
    "methoxyflurane": AP_DRUG,
    "midazolam": MIXED_DRUG,
    "morphine": MIXED_DRUG,
    "naloxone": MIXED_DRUG,
    "normal saline": AP_DRUG,
    "olanzapine": PACER_DRUG,
    "ondansetron": AP_DRUG,
    "oxygen": AP_DRUG,
    "paracetamol": AP_DRUG,
    "prochlorperazine": AP_DRUG,
    "salbutamol": AP_DRUG,
    "sodium bicarbonate": ICP_DRUG,
    "suxamethonium": ICP_DRUG,
    "topical anaesthetic cream": AP_DRUG,
}

_DRUG_ALIASES: dict[str, str] = {
    "acetylsalicylic acid": "aspirin",
    "atropine sulphate": "atropine",
    "glucose": "glucose 10%",
    "gtn": "glyceryl trinitrate",
    "ipratropium": "ipratropium bromide",
    "ketamine hydrochloride": "ketamine",
    "magnesium": "magnesium sulphate",
    "lmx4": "topical anaesthetic cream",
}


def canonical_drug(name: str) -> str | None:
    key = re.sub(r"\s*\(.*?\)\s*", " ", name).strip().lower()
    key = re.sub(r"\s+", " ", key)
    if key in DRUG_SCOPE:
        return key
    if key in _DRUG_ALIASES:
        return _DRUG_ALIASES[key]
    for alias, target in _DRUG_ALIASES.items():
        if key.startswith(alias):
            return target
    for drug in DRUG_SCOPE:
        if key.startswith(drug):
            return drug
    return None


def drug_scope(name: str) -> str | None:
    drug = canonical_drug(name)
    return DRUG_SCOPE.get(drug) if drug else None


ICP_GUIDELINES: frozenset[str] = frozenset({"3A", "3B"})

ICP_SKILLS: frozenset[str] = frozenset({
    "CSM.A10", "CSM.A11", "CSM.A12", "CSM.A13", "CSM.A14", "CSM.A15", "CSM.A16",
    "CSM.A20", "CSM.A21", "CSM.B10", "CSM.C05", "CSM.DF07", "CSM.DF16",
})

_ICP_DRUG_MENTION = re.compile(
    r"\b(adenosine|amiodarone|calcium chloride|heparin|hydrocortisone|"
    r"levetiracetam|sodium bicarbonate|suxamethonium|"
    r"(?<!topical )lignocaine)\b",
    re.IGNORECASE,
)
_TOPICAL = re.compile(r"topical|LMX4|cream", re.IGNORECASE)
_ICP_SKILL_MENTION = re.compile(r"\b(?:external |transcutaneous )?pacing\b", re.IGNORECASE)

_ICP_LABEL = re.compile(
    r"\*\*\s*-?\s*ICP\s*(?::|only|\*\*)|^\s*-?\s*ICP:|\(ICP\)|\bICP\.\s*$"
)
_AP_LABEL = re.compile(r"\*\*\s*AP\s*:|\(ICP/AP\)|\(AP/ICP\)")
_HEADING = re.compile(r"^\s*#{1,6}\s")
_GLUED_ITEM = re.compile(
    r"(?<=[^\s*-])- (?=\*\*|[A-Z0-9<>≥≤])"
    r"|(?<=[.:;!?)])\s+- (?=\*\*|[A-Z])"
    r"|(?<=\*\*)- (?=\*\*ICP)"
)

_ICP_SECTION_HEADING = re.compile(r"infusion|intubation|\bRSI\b", re.IGNORECASE)


@dataclass(frozen=True)
class Override:
    doc: str
    scope: str
    reason: str
    heading: str | None = None
    line: str | None = None

    def matches(self, doc_key: str, headings: tuple[str, ...], text: str) -> bool:
        if self.doc != doc_key:
            return False
        if self.heading and not any(
            re.search(self.heading, h, re.IGNORECASE) for h in headings
        ):
            return False
        if self.line and not re.search(self.line, text, re.IGNORECASE):
            return False
        return True


OVERRIDES: tuple[Override, ...] = (
    Override("med:03", ICP, "Scope PDF: adrenaline IV/IO with cardiac output is ICP",
             heading=r"Critically ill shocked"),
    Override("med:05", BOTH, "Oscar: AP may give atropine IM/IV/IO for organophosphate and spider bite",
             heading=r"Organophosphate|spider", line=r"^\s*-\s*IV\s*/\s*IO\s*/\s*IM"),
    Override("med:20", BOTH, "Scope PDF: magnesium IV/IO for eclamptic seizure is AP",
             line=r"Seizures due to eclampsia"),
    Override("med:20", ICP, "Scope PDF: paediatric magnesium is VF/torsades only, which is ICP",
             heading=r"^#+\s*Paediatric"),
    Override("med:23", BOTH, "Scope PDF: morphine IM is AP",
             heading=r"^#+\s*Adult and Paediatric", line=r"Consider IM|IV/IO unobtainable|Little risk|0\.1mg/kg IM|Repeat once @30/60"),
    Override("med:18", ICP, "Ketamine chart row labelled (ICP)",
             heading=r"Dose Chart", line=r"Halve above doses|HYPOPERFUSED PATIENT"),
    Override("cmg:28", BOTH, "Patient's own dialysis heparin; background knowledge for AP",
             line=r"heparin"),
    Override("csm:CSM.A19", ICP, "Oscar: IGT note for intubated patients is ICP",
             line=r"Intubated patients"),
)


@dataclass(frozen=True)
class Segment:
    text: str
    scope: str
    reason: str
    headings: tuple[str, ...]


def doc_kind(doc: dict) -> str:
    number = str(doc.get("cmg_number", ""))
    if doc.get("section") == "Medicine":
        return "med"
    if number.startswith("CSM"):
        return "csm"
    return "cmg"


def doc_key(doc: dict) -> str:
    return f"{doc_kind(doc)}:{doc.get('cmg_number', '')}"


def context_header(doc: dict) -> str:
    """One line naming the document, so a chunk taken from its middle still says what it is about."""
    label = {"med": "MED", "csm": "", "cmg": "CMG"}[doc_kind(doc)]
    name = f"{label} {doc.get('cmg_number', '')}".strip()
    return f"[ACTAS {name}: {doc.get('title', '')}]"


def document_scope(doc: dict) -> str | None:
    """Whole-document scope, or None when lines must be tagged individually.

    MED monographs and clinical skills ignore the scraped ``is_icp_only`` flag:
    it marks adrenaline, atropine, ketamine and magnesium ICP-only, misses
    adenosine and lignocaine, and misses the AirTraq camera, BURP and
    cricothyroid pressure skills. Guidelines and skills follow Oscar's lists
    (2026-11-01): only CMG 3A and 3B are ICP-only.
    """
    kind = doc_kind(doc)
    if kind == "med":
        scope = drug_scope(doc.get("title", ""))
        if scope == ICP_DRUG:
            return ICP
        if scope == PACER_DRUG:
            return PACER
        return None
    if kind == "csm":
        return ICP if doc.get("cmg_number") in ICP_SKILLS else None
    return ICP if str(doc.get("cmg_number", "")).upper() in ICP_GUIDELINES else None


def _split_glued(text: str) -> list[str]:
    lines: list[str] = []
    for line in text.splitlines():
        parts = _GLUED_ITEM.split(line)
        lines.append(parts[0])
        lines.extend(f"- {p}" for p in parts[1:])
    return lines


def classify(doc: dict, text: str | None = None) -> list[Segment]:
    text = doc.get("content_markdown", "") if text is None else text
    key = doc_key(doc)
    kind = doc_kind(doc)
    whole = document_scope(doc)
    mixed_med = kind == "med" and drug_scope(doc.get("title", "")) == MIXED_DRUG

    segments: list[Segment] = []
    headings: list[tuple[int, str]] = []
    carry: tuple[str, str] | None = None
    section_stack: list[tuple[int, tuple[str, str]]] = []

    for line in _split_glued(text):
        heading_path = tuple(h for _, h in headings)
        if _HEADING.match(line):
            level = len(line) - len(line.lstrip("#"))
            headings = [h for h in headings if h[0] < level] + [(level, line.strip())]
            heading_path = tuple(h for _, h in headings)
            carry = None
            section_stack = [e for e in section_stack if e[0] < level]
            heading_scope = BOTH
            if section_stack:
                heading_scope = section_stack[-1][1][0]
            if whole is None and mixed_med and _ICP_SECTION_HEADING.search(line):
                section_stack.append(
                    (level, (ICP, "Scope PDF: infusions, intubation and post-tube sedation are ICP"))
                )
                heading_scope = ICP
            elif whole is None and kind != "med" and _ICP_DRUG_MENTION.search(line):
                section_stack.append((level, (ICP, "section about an ICP-only medicine")))
                heading_scope = ICP
            elif whole is None:
                override = next(
                    (o for o in OVERRIDES if o.heading and not o.line and o.matches(key, (line.strip(),), line)),
                    None,
                )
                if override is not None:
                    heading_scope = override.scope
            segments.append(Segment(line, heading_scope, "heading", heading_path))
            continue

        if not line.strip():
            carry = None
            segments.append(Segment(line, BOTH, "blank", heading_path))
            continue

        if whole is not None:
            segments.append(Segment(line, whole, "whole document", heading_path))
            continue

        override = next(
            (o for o in OVERRIDES if o.matches(key, heading_path, line)), None
        )
        if override is not None:
            scope, reason = override.scope, f"override: {override.reason}"
            if mixed_med:
                carry = (scope, reason)
        elif _ICP_LABEL.search(line):
            scope, reason = ICP, "labelled ICP"
            if mixed_med:
                carry = (ICP, "continues ICP-labelled item")
        elif _AP_LABEL.search(line):
            scope, reason = BOTH, "labelled AP"
            if mixed_med:
                carry = (BOTH, "continues AP-labelled item")
        elif section_stack:
            scope, reason = section_stack[-1][1]
        elif carry is not None:
            scope, reason = carry
        elif kind != "med" and _ICP_DRUG_MENTION.search(line) and not _TOPICAL.search(line):
            scope, reason = ICP, "names an ICP-only medicine"
        elif kind != "med" and _ICP_SKILL_MENTION.search(line):
            scope, reason = ICP, "names an ICP-only skill (CSM.C05 external pacing)"
        else:
            scope, reason = BOTH, "unlabelled"
        segments.append(Segment(line, scope, reason, heading_path))

    return segments


def visible_scopes(effective_qualifications: Iterable[str]) -> frozenset[str]:
    quals = set(effective_qualifications)
    scopes = {BOTH}
    if "ICP" in quals:
        scopes.add(ICP)
    if "PACER" in quals:
        scopes.add(PACER)
    return frozenset(scopes)


def _heading_level(text: str) -> int:
    stripped = text.lstrip()
    return len(stripped) - len(stripped.lstrip("#"))


def _has_body(segments: list[Segment], start: int) -> bool:
    level = _heading_level(segments[start].text)
    for nxt in segments[start + 1:]:
        if nxt.reason == "heading":
            if _heading_level(nxt.text) <= level:
                return False
            continue
        if nxt.text.strip():
            return True
    return False


def render(segments: list[Segment], effective_qualifications: Iterable[str]) -> str:
    """Text visible to the given qualifications. Headings emptied by filtering are dropped."""
    allowed = visible_scopes(effective_qualifications)
    kept_idx = [i for i, s in enumerate(segments) if s.scope in allowed]
    kept = [segments[i] for i in kept_idx]
    out: list[str] = []
    for pos, seg in enumerate(kept):
        if seg.reason == "heading" and _has_body(segments, kept_idx[pos]) and not _has_body(kept, pos):
            continue
        out.append(seg.text)
    result = "\n".join(out)
    return re.sub(r"\n{3,}", "\n\n", result).strip()


def ap_text(doc: dict, text: str | None = None) -> str:
    return render(classify(doc, text), {"AP"})


def icp_text(doc: dict, text: str | None = None) -> str:
    return render(classify(doc, text), {"AP", "ICP"})


_DOSE_AP_ROUTE: dict[str, re.Pattern[str]] = {
    "adrenaline": re.compile(r"\bIM\b|nebuli[sz]|EpiPen", re.IGNORECASE),
    "atropine": re.compile(r"\bIM\b|\bMCI\b|organophosph|nerve agent|spider", re.IGNORECASE),
    "fentanyl": re.compile(r"\bIN\b|intranasal", re.IGNORECASE),
    "ketamine": re.compile(r"\bIM\b|springfus", re.IGNORECASE),
    "magnesium sulphate": re.compile(r"eclamp", re.IGNORECASE),
    "midazolam": re.compile(r"\bIM\b|\bSC\b"),
    "morphine": re.compile(r"\bIM\b|\bSC\b"),
    "naloxone": re.compile(r"\bIM\b|\bIN\b"),
}
_DOSE_TEXT_OVERRIDES: tuple[tuple[str, re.Pattern[str], str, str], ...] = (
    ("adrenaline", re.compile(r"^(?![\s\S]*\b(?:ETT|infusion)\b)[\s\S]*1:10,?000\)?[^\n]*?Formula: 0\.01mg/kg"),
     BOTH, "Oscar: AP may give IV adrenaline in paediatric cardiac arrest; IO is ICP at the same dose"),
    ("adrenaline", re.compile(r"^\s*1mg IV or IO – fast push\s*$"), BOTH,
     "Adult cardiac arrest dose; the monograph shows it to AP"),
)
_DOSE_ICP_ROUTE = re.compile(r"\bETT\b|infusion|\bIO\b", re.IGNORECASE)


def dose_entry_scope(medicine: str, text: str, guideline_icp_only: bool) -> tuple[str, str]:
    """Scope for one dose_lookup entry. Mixed medicines default to ICP when unclear."""
    if guideline_icp_only:
        return ICP, "ICP-only guideline"
    scope = drug_scope(medicine)
    if scope == ICP_DRUG:
        return ICP, "ICP-only medicine"
    if scope == PACER_DRUG:
        return PACER, "PACER-only medicine"
    if scope == AP_DRUG:
        if canonical_drug(medicine) == "ceftriaxone" and re.search(r"\bIO\b", text):
            return ICP, "Scope PDF: ceftriaxone IO is ICP"
        return BOTH, "AP medicine"
    drug = canonical_drug(medicine) or ""
    for target, pattern, override_scope, reason in _DOSE_TEXT_OVERRIDES:
        if drug == target and pattern.search(text):
            return override_scope, reason
    if scope == MIXED_DRUG:
        if _ICP_LABEL.search(text) or re.search(r"\bICP\b", text):
            return ICP, "labelled ICP"
        if _DOSE_ICP_ROUTE.search(text):
            return ICP, "ICP route (ETT, IO or infusion)"
        rule = _DOSE_AP_ROUTE.get(canonical_drug(medicine) or "")
        if rule and rule.search(text):
            return BOTH, "AP route per scope PDF"
        return ICP, "mixed medicine, route unclear: kept ICP"
    return BOTH, "not in scope table"


def qualifications_for(scope: str) -> list[str]:
    if scope == ICP:
        return ["ICP"]
    if scope == PACER:
        return ["PACER"]
    return ["AP"]
