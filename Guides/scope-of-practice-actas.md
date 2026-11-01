# Scope of Practice — ACT Ambulance Service (ACTAS)

> **Sources, in priority order:**
> 1. Oscar's medication, clinical skill and guideline scope lists (2026-11-01)
> 2. ACTAS CMG text labels (`**ICP:**`, `**- ICP only**`, `**AP:**`, `(ICP)`, `(ICP/AP)`)
> 3. ACTAS Scope of Practice, POLACTAS001 Attachment A (reviewed 12/09/2024), for routes and
>    indications. CSM.M07 Skills Matrix overrides the PDF for skills.
>
> The rules are code in `src/python/guidelines/actas_scope.py`. Every decision is listed in
> `docs/review/actas-scope-tagging.md` (regenerate with `python scripts/report_actas_scope.py`).
> Referenced by `registry.py` as `scope_source_doc` for the `actas` service entry.

---

## Qualifications

| ID | Name | Notes |
|----|------|-------|
| `AP` | Ambulance Paramedic | Base |
| `ICP` | Intensive Care Paramedic | Base, implies AP |
| `PACER` | PACER | Endorsement on AP or ICP. Needed for olanzapine |

---

## Guidelines

Only **CMG 3A RSI** and **CMG 3B Intubation Algorithm** are ICP-only. Every other CMG is AP or
mixed, and is tagged line by line from its ICP labels.

---

## Medicines

*AP = every use is in AP (and ICP) scope. Mixed = some uses are ICP-only.*

| Scope | Medicines |
|-------|-----------|
| AP | Aspirin, Ceftriaxone (IO is ICP), Droperidol, Glucagon, Glucose 10%, Oral glucose gel, GTN, Ibuprofen, Ipratropium bromide, Methoxyflurane, Normal saline, Ondansetron, Oxygen, Paracetamol, Prochlorperazine, Salbutamol, Topical anaesthetic cream (LMX4) |
| ICP only | Adenosine, Amiodarone (expected to become mixed at the next guideline update), Calcium chloride, Heparin, Hydrocortisone, Levetiracetam, Lignocaine, Sodium bicarbonate, Suxamethonium |
| Mixed | Adrenaline, Atropine, Fentanyl, Ketamine, Magnesium sulphate, Midazolam, Morphine, Naloxone |
| PACER only | Olanzapine |

### Routes and indications for mixed medicines (scope PDF)

| Medicine | AP | ICP only |
|----------|----|----------|
| Adrenaline | Nebulised (upper airway obstruction); IM (asthma/anaphylaxis); IV in cardiac arrest (adult and paediatric) | IV/IO with cardiac output; infusion; newborn ETT; paediatric IO |
| Atropine | IM/IV/IO for organophosphate or nerve agent poisoning and big black spider bite with cholinergic symptoms (Oscar, overrides the PDF) | Bradyarrhythmias |
| Fentanyl | Intranasal | IV (flight) |
| Ketamine | Low dose via Springfusor; IM and IV/IO for analgesia and sedation | RSI, procedural sedation, induction, post-tube sedation; infusion pump |
| Magnesium sulphate | IV/IO for eclamptic seizure | All other IV/IO (VF, torsades, pre-eclampsia, paediatric) |
| Midazolam | IM for seizures; palliative SC/IM | IV/IO for seizures and sedation; infusion pump |
| Morphine | IM (0.1mg/kg × 2, max 20mg); IV up to 20mg total; palliative SC | IV/IO with no dose limit; infusion pump |
| Naloxone | IM | IV/IO |

Subcutaneous injection (CSM.DF03) is AP since the palliative care guideline was introduced,
which overrides the PDF.

---

## Clinical skills

| Scope | Skills |
|-------|--------|
| ICP only | A10–A16 (AirTraq, AirTraq camera, laryngoscope and bougie, railroad technique, BURP, extubation, cricothyroid pressure), A20 front of neck, A21 needle cricothyroidotomy, B10 needle decompression, C05 external pacing, DF07 EJ cannulation, DF16 adrenaline infusion |
| Mixed | A19 IGT (the intubated-patient note is ICP); DF08 IO (AP: tibial sites in cardiac arrest only; ICP: humeral and tibial in all indicated patients) |
| AP | Everything else, including C07 (primary responsibility ICP) and DF03 subcutaneous injection |

---

## Vector store

ACTAS chunks live in `guidelines_actas` with a `visibility` of `both`, `ap` (AP-only text of a
mixed document), `icp` or `pacer`. The retriever shows `both` and `ap` to AP users, adds `icp`
for ICP users, and adds `pacer` for users with the PACER endorsement.

---

*Last reviewed: 2026-11-01. Update when guidelines change or Oscar revises scope.*
