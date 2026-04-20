# Ambulance Tasmania — Category Mapping

Maps AT CPG clinical category taxonomy to the project's broad study categories.
Used by the structurer to populate `categories` in `GuidelineDocument` records.

Source: Phase 0 extraction findings (`Guides/at-cpg-extraction-findings.md`, Section 6.3).

## Mapping Table

| AT Category | CPG Code Range | Project Broad Category |
|---|---|---|
| Assessment | A0101–A0112 | Clinical Skills |
| Mental Health | A0106 | Clinical Guidelines |
| Cardiac Arrest | A0201–A0203 | Clinical Guidelines |
| Airway Management | A0300–A0307 | Clinical Skills |
| Cardiac | A0401–A0411 | Clinical Guidelines |
| Pain Relief | A0501 | Medication Guidelines |
| Respiratory | A0601–A0604 | Clinical Guidelines |
| Medical | A0701–A0712 | Clinical Guidelines |
| Trauma | A0801–A0809 | Clinical Guidelines |
| Environment | A0901–A0902 | Clinical Guidelines |
| Obstetrics | M001–M010 | Clinical Guidelines |
| Medicines | D002–D047 | Medication Guidelines, Pharmacology |
| Paediatric | P0201–P0710 | Clinical Guidelines |
| Reference Notes | E002–E009 | Operational Guidelines |

## Category Code Prefix Rules

| Prefix | Type | Broad Category |
|---|---|---|
| `A0` | Adult patient guideline | varies by topic (see table above) |
| `D` | Medicine monograph | Medication Guidelines, Pharmacology |
| `M` | Maternity/obstetric | Clinical Guidelines |
| `P` | Paediatric | Clinical Guidelines |
| `E` | Equipment/reference | Operational Guidelines |

## Secondary Categories

Medicine monographs (D-codes) also map to **Pharmacology**. Dose-related content
within medicine pages maps to both **Medication Guidelines** and **Pharmacology**.

Paediatric guidelines (P-codes) with medication content additionally carry
**Pharmacology** as a secondary category.

## Lookup Function

The structurer uses prefix-based lookup with the AT category name for disambiguation:

1. Check CPG code prefix (`A0`, `D`, `M`, `P`, `E`)
2. If `A0`, look up the AT category name in the table above
3. If `D`, return `["Medication Guidelines", "Pharmacology"]`
4. If `M`, return `["Clinical Guidelines"]`
5. If `P`, return `["Clinical Guidelines"]` (add `"Pharmacology"` if medicines referenced)
6. If `E`, return `["Operational Guidelines"]`
