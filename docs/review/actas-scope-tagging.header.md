# ACTAS AP/ICP Scope Tagging Review

**Date:** 2026-11-01
**Code:** `src/python/guidelines/actas_scope.py`. Regenerate the tables below with `python scripts/report_actas_scope.py`.
**Sources, in priority order:**
1. Oscar's medication, clinical skill and guideline scope lists (2026-11-01)
2. The ACTAS Clinical Management Guideline text itself: `**ICP:**`, `**- ICP only**`, `**AP:**`, `(ICP)` and `(ICP/AP)` labels
3. ACTAS Scope of Practice, POLACTAS001 Attachment A (reviewed 12/09/2024), for routes and indications of mixed-scope medicines. CSM.M07 Skills Matrix overrides the PDF for skills.

## How tagging works

- **Whole documents:** ICP-only medicines, ICP-only skills and CMG 3A/3B are ICP. Olanzapine is PACER only. The scraped `is_icp_only` flag is no longer trusted. It wrongly marked adrenaline, atropine, ketamine and magnesium as ICP-only, so AP users saw none of those monographs. It also missed adenosine, lignocaine, the AirTraq camera, BURP and cricothyroid pressure, so AP users saw all of those.
- **Mixed-scope medicine monographs:** an ICP label covers the labelled item and the unlabelled items directly under it (up to the next blank line or heading). An AP label resets that. Infusion, intubation and post-intubation sections are ICP. Explicit overrides (listed in the tables as "override") handle the cases the labels get wrong.
- **Guidelines and skills:** the ICP label covers only its own line, because ICP and AP steps are interleaved without blank lines. Lines and headings that name an ICP-only medicine are ICP.
- **Dose tables:** each row is tagged on its own. For mixed-scope medicines, rows that mention ETT, IO or infusion are ICP. Rows on an AP route from the scope PDF (for example adrenaline IM or nebulised, midazolam IM or SC) are shown to both. Rows whose route or indication can't be read are **kept ICP-only**. This hides some AP content rather than risk showing ICP content.
- **AP chunks are now built from the tagged text before splitting**, so an ICP block can't lose its label by being split across two chunks.

## What was wrong before

1. **ICP doses leaked into AP questions.** Unlabelled continuation lines of ICP blocks stayed in the AP text. For example, the adrenaline newborn ETT dose ("If no IV or IO access – 0.02mg/kg") and every adrenaline infusion pump limit were visible to AP users.
2. **Whole ICP-only medicines and skills were visible to AP users:** adenosine, lignocaine, the AirTraq camera, BURP and cricothyroid pressure.
3. **Several AP-scope monographs were hidden from AP users entirely:** adrenaline, atropine, ketamine and magnesium.
4. **Dose table tags were whole-medicine,** so every dose of a drug got the same tag whatever its route or indication.

## Please check

1. **Atropine IV.** The monograph labels "**AP:** IM/IV" for organophosphate and spider bite. The 2024 scope PDF lists atropine IV/IO as ICP only, with AP limited to IM. I followed the CMG (source hierarchy), so AP users see the IM/IV doses.
2. **Morphine IV/IO.** The shared analgesia line reads "0.05mg/kg IV/IO" with "**AP:** max. total dose 20mg". It is shown to AP users as written, including the IO route.
3. **Palliative care midazolam and morphine** (SC/IM/IV) are shown to AP users. This follows your note that subcutaneous injection is AP since the palliative care guideline was introduced.
4. **Adrenaline paediatric cardiac arrest calculator rows** ("1:10,000 IV/IO 0.01mg/kg") are kept ICP-only because the row names IO. AP users still get the IV dose from the monograph text. Say if you want these rows shown to AP.
5. **CSM.DF08 IO insertion** is shown to both. The text doesn't separate tibial from humeral sites or cardiac arrest from other indications, so there is nothing to split. The lignocaine priming lines are ICP.
6. **CSM.A20 and A21** (surgical airway, needle cricothyroidotomy). Your list was cut off there. I kept them ICP, as the source data has them.
7. **CSM.C07** is on your list, but there is no C07 file in the scraped data. The skill is missing from the corpus.
8. **Dose data errors found while checking:** a ketamine dose ("Up to 4mg/kg IM injection") is filed under midazolam, and the fentanyl intranasal dose ("1.5mcg/kg IN") is filed under naloxone. Both come from the scraper. The midazolam row is forced to ICP; the naloxone row is harmless scope-wise but wrong content.

