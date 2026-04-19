# Scope of Practice — ACT Ambulance Service (ACTAS)

> **Authoritative source:** ACTAS Clinical Management Guidelines (CMGs) at
> <https://cmg.ambulance.act.gov.au>. This document summarises the scope distinction
> between AP and ICP as reflected in the CMG corpus and the app's quiz/retrieval logic.
> It is referenced by `registry.py` as `scope_source_doc` for the `actas` service entry.

---

## Qualification Levels

ACTAS operates with two clinical qualification levels. ICP implies AP — every ICP paramedic
operates within the full AP scope plus the additional ICP-specific procedures below.

### AP — Ambulance Paramedic

The baseline ACTAS clinical scope. APs may use all CMGs **not** marked `is_icp_only: true`.

**Scope includes:**

- Full emergency patient assessment and management
- Basic and advanced airway management (BVM, OPA/NPA, LMA, CPAP)
- Cardiac monitoring and 12-lead ECG interpretation
- Defibrillation (manual and AED) and cardioversion
- Vascular access (IV/IO)
- Full AP medication formulary:
  Aspirin, Adrenaline, Atropine, Calcium Chloride, Ceftriaxone, Droperidol, Fentanyl,
  Glucagon, Glucose 10%, Oral Glucose Gel, Glyceryl Trinitrate (GTN), Ibuprofen,
  Ipratropium Bromide, Ketamine, Magnesium Sulfate, Methoxyflurane, Midazolam,
  Morphine Sulfate, Naloxone, Olanzapine, Ondansetron, Paracetamol,
  Prochlorperazine (Stemetil), Salbutamol, Topical Anaesthetic Cream (LMX4),
  Oxygen, Normal Saline
- Obstetric emergencies and neonatal resuscitation
- Trauma management including haemorrhage control, splinting, spinal precautions
- Psychological first aid and mental health assessment

**CMG coverage:** All 56 AP-applicable CMGs in the structured data corpus.

---

### ICP — Intensive Care Paramedic

Extended scope above AP. ICPs may perform all AP procedures **plus**:

- Rapid Sequence Intubation (RSI) — CMG 3A
- Intubation Algorithm (including surgical airway) — CMG 3B
- ICP-exclusive medication formulary:
  Adenosine, Amiodarone, Heparin, Hydrocortisone, Lignocaine,
  Sodium Bicarbonate, Suxamethonium, Levetiracetam
- Extended management protocols where the CMG denotes ICP requirement

**ICP-only CMGs in the current corpus (flagged `is_icp_only: true`):**

| CMG | Title |
|-----|-------|
| CMG 3A | RSI (Rapid Sequence Intubation) |
| CMG 3B | Intubation Algorithm |

> **Note:** Additional ICP scope may exist within sections of AP-listed CMGs (e.g.,
> ICP-restricted medication doses within a shared CMG). These are identified during
> the qualifications backfill (Task 11 / `Guides/actas-qualifications-backfill.md`).

---

## Registry Mapping

```python
# src/python/services/registry.py
QualificationModel(
    bases=(
        Base("AP", "Ambulance Paramedic"),
        Base("ICP", "Intensive Care Paramedic", implies=("AP",)),
    ),
)
```

The `implies=("AP",)` on ICP means `effective_qualifications("ICP", (), actas)` returns
`frozenset({"AP", "ICP"})` — ICP paramedics see all AP content plus ICP-restricted content.

---

## ChromaDB Collection

All ACTAS content is stored in collection `guidelines_actas`. Chunks carry
`qualifications_required: []` (available to all ACTAS levels) or
`qualifications_required: ["ICP"]` (ICP-only).

---

*Last reviewed: 2026-04-19. Update when new CMGs are added or scope changes.*
