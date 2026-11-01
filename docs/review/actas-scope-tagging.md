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

## Oscar's decisions (2026-11-01)

1. **Atropine:** AP may give IM/IV/IO for organophosphate or nerve agent poisoning and big black spider bite with cholinergic symptoms. Bradyarrhythmia doses stay ICP.
2. **Morphine IV/IO** shared analgesia line shown to AP as written: confirmed.
3. **Palliative midazolam and morphine** (SC/IM/IV) shown to AP: confirmed.
4. **Adrenaline paediatric cardiac arrest:** AP may give IV, IO stays ICP. The calculator rows ("1:10,000 IV/IO 0.01mg/kg") are now shown to AP because the dose is the same. Rows that also carry the newborn ETT dose stay ICP. The adult "1mg IV or IO – fast push" row is shown to AP to match the monograph.
5. **CSM.DF08** shown to both: confirmed.
6. **CSM.A20 and A21** stay ICP.
7. **CSM.C07** is missing from the scraped data. A rescrape is added to Phase 0 of `docs/web-port-plan.md`.
8. **Misfiled doses fixed:** the ketamine "Up to 4mg/kg IM" dose is moved from midazolam to ketamine, and the fentanyl "1.5mcg/kg IN" dose is removed from naloxone. The fix is in `pipeline/actas/dose_tables.py` (`correct_misfiled_doses`), so a rescrape keeps it.

## Whole-document scope

**Guidelines**

- ICP-only: CMG 3A RSI (Rapid Sequence Intubation); CMG 3B Intubation Algorithm
- Tagged line by line: 54

**Medicines**

- ICP-only: MED 02 Adenosine (Adenocor); MED 04 Amiodarone (Cordarone); MED 06 Calcium Chloride; MED 14 Heparin; MED 15 Hydrocortisone; MED 19 Lignocaine; MED 30 Sodium Bicarbonate; MED 31 Suxamethonium; MED 35 Levetiracetam
- PACER-only: MED 25 Olanzapine
- Tagged line by line: 25

**Clinical skills**

- ICP-only: CSM.A10 AirTraq (Endotracheal Intubation); CSM.A11 AirTraq Camera; CSM.A12 Laryngoscope and Bougie (Endotracheal Intubation); CSM.A13 Laryngoscope and Bougie Railroad Technique (Endotracheal Intubation); CSM.A14 BURP Manoeuvre; CSM.A15 Extubation; CSM.A16 Cricothyroid Pressure; CSM.A20 Front of Neck (Surgical Airway); CSM.A21 Needle Cricothyroidotomy; CSM.B10 Tension Pneumothorax Needle Decompression; CSM.C05 External Cardiac Pacing (Zoll X Series); CSM.DF07 External Jugular Cannulation; CSM.DF16 Adrenaline Infusion
- Tagged line by line: 86

## Lines hidden from AP users

Every line an AP-only user does not see, with the rule that hid it. Documents that are wholly ICP or PACER are listed above, not here.

### MED 03 Adrenaline

| Shown to | Line | Why |
|---|---|---|
| ICP | - Bradyarrhythmias resistant to atropine **- ICP only** | labelled ICP |
| ICP | - Shock unresponsive to fluid boluses **- ICP only** | labelled ICP |
| ICP | - **ICP:** IV/IO adrenaline by infusion – titrated to response | labelled ICP |
| ICP | - **ICP:** IO: 0.01mg/kg – fast push | labelled ICP |
| ICP | - No limit on number of doses in cardiac arrest. | continues ICP-labelled item |
| ICP | - **ICP:** ETT: NEWBORN ONLY | labelled ICP |
| ICP | - If no IV or IO access – 0.02mg/kg. | continues ICP-labelled item |
| ICP | - **ICP:** If required – **IV/IO** adrenaline by infusion | labelled ICP |
| ICP | - Titrated to response. | continues ICP-labelled item |
| ICP | - **ICP:** If required – **IV/IO** adrenaline by infusion | labelled ICP |
| ICP | - Titrated to response. | continues ICP-labelled item |
| ICP | #### Critically ill shocked patients | heading |
| ICP | **Unresponsive to fluid bolus/es** | override: Scope PDF: adrenaline IV/IO with cardiac output is ICP |
| ICP | - **ICP: ****IV/IO** adrenaline by infusion | override: Scope PDF: adrenaline IV/IO with cardiac output is ICP |
| ICP | - Titrated to response. | override: Scope PDF: adrenaline IV/IO with cardiac output is ICP |
| ICP | #### Infusion Notes | heading |
| ICP | #### Adult and Paediatric Adrenaline infusion (gravity fed) | heading |
| ICP | **Note:** Add 1mL (1mg) 1:1000 adrenaline to 500mL NaCl. | Scope PDF: infusions, intubation and post-tube sedation are ICP |
| ICP | - **ICP: ** 1mg in 500mL = 2mcg/mL | labelled ICP |
| ICP | - 20 drops/min = 1 ml/min = 2 mcg/min (titrate as required) | Scope PDF: infusions, intubation and post-tube sedation are ICP |
| ICP | - Titrate infusion rate as required. | Scope PDF: infusions, intubation and post-tube sedation are ICP |
| ICP | - Utilising a burette will achieve more accurate dosing (ALWAYS use a burette with paediatric patients). | Scope PDF: infusions, intubation and post-tube sedation are ICP |
| ICP | - **Remember to label the flask with a medication label.** | Scope PDF: infusions, intubation and post-tube sedation are ICP |
| ICP | #### Adult (≥40kg) Adrenaline infusion (infusion pump) | heading |
| ICP | **Note:** Withdraw 3mL from 50mL NaCl bag, then add 3mL (3mg) 1:1000 adrenaline to make 3mg/50mL | Scope PDF: infusions, intubation and post-tube sedation are ICP |
| ICP | - **ICP: **Initial infusion rate : 5mcg/min | labelled ICP |
| ICP | - Lower soft infusion limit: 1mcg/min | Scope PDF: infusions, intubation and post-tube sedation are ICP |
| ICP | - Upper soft infusion limit: 25mcg/min | Scope PDF: infusions, intubation and post-tube sedation are ICP |
| ICP | - Upper hard infusion limit: 50mcg/min | Scope PDF: infusions, intubation and post-tube sedation are ICP |
| ICP | - **ICP: **Default bolus: 12mcg (0.2mL) | labelled ICP |
| ICP | - Lower soft bolus limit: 1.2mcg (0.02mL) | Scope PDF: infusions, intubation and post-tube sedation are ICP |
| ICP | - Upper soft bolus limit: 24mcg (0.4mL) | Scope PDF: infusions, intubation and post-tube sedation are ICP |
| ICP | - Upper hard bolus limit: 48mcg (0.8mL) | Scope PDF: infusions, intubation and post-tube sedation are ICP |
| ICP | #### Large Paediatric (21-39kg) Adrenaline infusion (infusion pump) | heading |
| ICP | **Note:** Withdraw 3mL from 50mL NaCl bag, then add 3mL (3mg) 1:1000 adrenaline to make 3mg/50mL | Scope PDF: infusions, intubation and post-tube sedation are ICP |
| ICP | - **ICP: **Initial infusion rate : 0.05mcg/kg/min | labelled ICP |
| ICP | - Lower soft infusion limit: 0.02mcg/kg/min | Scope PDF: infusions, intubation and post-tube sedation are ICP |
| ICP | - Upper soft infusion limit: 0.5mcg/kg/min | Scope PDF: infusions, intubation and post-tube sedation are ICP |
| ICP | - Upper hard infusion limit: 1mcg/kg/min | Scope PDF: infusions, intubation and post-tube sedation are ICP |
| ICP | - **ICP: **Default bolus: 6mcg (0.1mL) | labelled ICP |
| ICP | - Lower soft bolus limit: 0.6mcg (0.01mL) | Scope PDF: infusions, intubation and post-tube sedation are ICP |
| ICP | - Upper soft bolus limit: 12mcg (0.2mL) | Scope PDF: infusions, intubation and post-tube sedation are ICP |
| ICP | - Upper hard bolus limit: 48mcg (0.8mL) | Scope PDF: infusions, intubation and post-tube sedation are ICP |
| ICP | #### Small Paediatric (≤20kg) Adrenaline infusion (infusion pump) | heading |
| ICP | **Note:** Withdraw 3mL from 50mL NaCl bag, then add 3mL (300mcg) 1:10,000 adrenaline to make 300mcg/50mL | Scope PDF: infusions, intubation and post-tube sedation are ICP |
| ICP | - **ICP: **Initial infusion rate : 0.05mcg/kg/min | labelled ICP |
| ICP | - Lower soft infusion limit: 0.02mcg/kg/min | Scope PDF: infusions, intubation and post-tube sedation are ICP |
| ICP | - Upper soft infusion limit: 0.5mcg/kg/min | Scope PDF: infusions, intubation and post-tube sedation are ICP |
| ICP | - Upper hard infusion limit: 1mcg/kg/min | Scope PDF: infusions, intubation and post-tube sedation are ICP |
| ICP | - **ICP: **Default bolus: 1mcg/kg | labelled ICP |
| ICP | - Lower soft bolus limit: 0.5mcg/kg | Scope PDF: infusions, intubation and post-tube sedation are ICP |
| ICP | - Upper soft bolus limit: 5mcg/kg | Scope PDF: infusions, intubation and post-tube sedation are ICP |
| ICP | - Upper hard bolus limit: 10mcg/kg | Scope PDF: infusions, intubation and post-tube sedation are ICP |

### MED 05 Atropine Sulphate

| Shown to | Line | Why |
|---|---|---|
| ICP | - Bradyarrhythmias with poor perfusion **- ICP only** | labelled ICP |
| ICP | - **ICP:** IV / IO: 600mcg – fast push | labelled ICP |
| ICP | - Repeat once after 3-5 minutes, if required. | continues ICP-labelled item |
| AP and ICP | - IV / IO / IM: initial dose 2400mcg – fast push | override: Oscar: AP may give atropine IM/IV/IO for organophosphate and spider bite |
| AP and ICP | - IV / IO / IM: initial dose 50mcg/kg (max. initial dose 2400mcg) – fast push | override: Oscar: AP may give atropine IM/IV/IO for organophosphate and spider bite |
| AP and ICP | - IV / IO / IM: 600mcg – fast push | override: Oscar: AP may give atropine IM/IV/IO for organophosphate and spider bite |
| AP and ICP | - IV / IO / IM: 20mcg/kg (max. 600mcg) – fast push | override: Oscar: AP may give atropine IM/IV/IO for organophosphate and spider bite |

### MED 07 Ceftriaxone (Rocephin)

| Shown to | Line | Why |
|---|---|---|
| ICP | - **ICP:** May also be given IO if no IV available. | labelled ICP |

### MED 18 Ketamine Hydrochloride (Ketalar)

| Shown to | Line | Why |
|---|---|---|
| ICP | - Induction agent for intubation **- ICP only** | labelled ICP |
| ICP | - Maintenance of sedation **- ICP only** | labelled ICP |
| ICP | - Procedural dissociation to facilitate painful interventions (e.g., straightening long bones, extrication) **- ICP only** | labelled ICP |
| ICP | - Analgesia for severe pain in the patient with signs of shock, or is at risk of shock **- ICP only** | labelled ICP |
| ICP | - **ICP: ****When used as the first line agent:** Up to 4mg/kg IM injection | labelled ICP |
| ICP | - **ICP: ****When used as the second line agent:** Up to 2mg/kg IM/IV/IO | labelled ICP |
| ICP | - For all regimes: repeat as required. | continues ICP-labelled item |
| ICP | - All IV doses are to be given slowly, over 30 seconds. | continues ICP-labelled item |
| ICP | - Reduce dose by half following droperidol use (i.e. up to 1mg/kg IM/IV/IO). | continues ICP-labelled item |
| ICP | #### For intubation induction with Suxamethonium | heading |
| ICP | ##### Adult only | heading |
| ICP | - **ICP:** 1mg/kg IV/IO over 30-60 seconds | labelled ICP |
| ICP | #### For intubation when suxamethonium is contraindiated | heading |
| ICP | ##### Adult only | heading |
| ICP | - **ICP:** 2mg/kg IV/IO over 30-60 seconds | labelled ICP |
| ICP | #### Post intubation analgosedation | heading |
| ICP | ##### Adult and Paediatric (Syringe bolus) | heading |
| ICP | - **ICP:** Up to 1mg/kg IV or IO | labelled ICP |
| ICP | - 1-5 minute intervals as required. | Scope PDF: infusions, intubation and post-tube sedation are ICP |
| ICP | ##### Adult (Infusion pump) | heading |
| ICP | **Note:** Withdraw 14mL from 50mL NaCl bag, then add 4mL (400mg) ketamine to make 400mg/40mL | Scope PDF: infusions, intubation and post-tube sedation are ICP |
| ICP | - **ICP:** Initial infusion rate: 100mg/hr | labelled ICP |
| ICP | - Lower soft infusion limit: 10mg/hr | Scope PDF: infusions, intubation and post-tube sedation are ICP |
| ICP | - Upper soft infusion limit: 400mg/hr | Scope PDF: infusions, intubation and post-tube sedation are ICP |
| ICP | - Upper hard infusion limit: 800mg/hr | Scope PDF: infusions, intubation and post-tube sedation are ICP |
| ICP | - **ICP:** Default bolus: 20mg (2mL) | labelled ICP |
| ICP | - Lower hard bolus limit: 5mg (0.5mL) | Scope PDF: infusions, intubation and post-tube sedation are ICP |
| ICP | - Upper hard bolus limit: 100mg (10mL) | Scope PDF: infusions, intubation and post-tube sedation are ICP |
| ICP | HYPOPERFUSED PATIENT | override: Ketamine chart row labelled (ICP) |
| ICP | (ICP) | labelled ICP |
| ICP | Halve above doses | override: Ketamine chart row labelled (ICP) |
| ICP | Halve above doses | override: Ketamine chart row labelled (ICP) |

### MED 20 Magnesium Sulphate

| Shown to | Line | Why |
|---|---|---|
| ICP | - Torsades de pointes / polymorphic VT **- ICP only** | labelled ICP |
| ICP | - Refractory VF (3rd drug) **- ICP only** | labelled ICP |
| ICP | - Symptomatic pre-eclampsia – hypertensive pregnant patient (20/40 to 6/52 post partum) presenting as unwell (altered LOC, headache, abdominal pain, visual dis… | labelled ICP |
| ICP | - **ICP: ****With cardiac output: **2.5g IV/IO | labelled ICP |
| ICP | - Diluted up to 10ml with normal saline | continues ICP-labelled item |
| ICP | - Given over 5 minutes. | continues ICP-labelled item |
| ICP | - **ICP: ****Refractory VF: **2.5g IV/IO | labelled ICP |
| ICP | - Over 30-60 seconds | continues ICP-labelled item |
| ICP | - **ICP: ****Torsades de pointes: **2.5g IV/IO | labelled ICP |
| ICP | - Over 30-60 seconds | continues ICP-labelled item |
| ICP | - **ICP: ****Pre-eclampsia: **2.5g IV/IO via Springfusor | labelled ICP |
| ICP | - Made up to 7ml total volume with normal saline (7ml will run over 10 minutes). | continues ICP-labelled item |
| ICP | ##### Paediatric | heading |
| ICP | - Dose is 50mg/kg (to max of 2.5g) | override: Scope PDF: paediatric magnesium is VF/torsades only, which is ICP |
| ICP | - Dilute entire ampoule up to 10ml = 250mg/ml. Discard excess. | override: Scope PDF: paediatric magnesium is VF/torsades only, which is ICP |
| ICP | - **With cardiac output: **Give calculated dose IV/IO over 3 – 5 minutes. | override: Scope PDF: paediatric magnesium is VF/torsades only, which is ICP |
| ICP | - **No cardiac output: **Give calculated dose IV/IO over 30 – 60 seconds. | override: Scope PDF: paediatric magnesium is VF/torsades only, which is ICP |
| AP and ICP | - **Seizures due to eclampsia: ** | override: Scope PDF: magnesium IV/IO for eclamptic seizure is AP |
| AP and ICP | - 2.5g IV/IO over 30-60 seconds | override: Scope PDF: magnesium IV/IO for eclamptic seizure is AP |
| AP and ICP | - Followed by 2.5g IV/IO via Springfusor - Made up to 7ml total volume with normal saline (7ml will run over 10 minutes). | override: Scope PDF: magnesium IV/IO for eclamptic seizure is AP |

### MED 22 Midazolam

| Shown to | Line | Why |
|---|---|---|
| ICP | - **ICP:** 0.2mg/kg IV/IO push over 60 sec. (max. 10mg) | labelled ICP |
| ICP | - Repeat @5/60 if required. (max. 2 doses) | continues ICP-labelled item |
| ICP | #### Post Intubation Sedation (as adjunct to ketamine) | heading |
| ICP | ##### Adult and Paediatric | heading |
| ICP | - **ICP:** 0.05mg/kg IV/IO push over 60 sec. | labelled ICP |
| ICP | - Repeat @5/60 as required. | Scope PDF: infusions, intubation and post-tube sedation are ICP |
| ICP | #### Post Intubation Sedation (as adjunct to morphine) | heading |
| ICP | ##### Adult | heading |
| ICP | **Note:** Withdraw 29mL from 50mL NaCl bag, then add 6mL (30mg) midazolam and 3mL (30mg) morphine to make 30mg:30mg/30mL | Scope PDF: infusions, intubation and post-tube sedation are ICP |
| ICP | - **ICP:** Initial infusion rate: 5mg/hr | labelled ICP |
| ICP | - Lower soft infusion limit: 1mg/hr | Scope PDF: infusions, intubation and post-tube sedation are ICP |
| ICP | - Upper soft infusion limit: 30mg/hr | Scope PDF: infusions, intubation and post-tube sedation are ICP |
| ICP | - Upper hard infusion limit: 50mg/hr | Scope PDF: infusions, intubation and post-tube sedation are ICP |
| ICP | - **ICP:** Default bolus: 2mg (2mL) | labelled ICP |
| ICP | - Lower hard bolus limit: 0.5mg (0.5mL) | Scope PDF: infusions, intubation and post-tube sedation are ICP |
| ICP | - Upper hard bolus limit: 5mg (5mL) | Scope PDF: infusions, intubation and post-tube sedation are ICP |

### MED 23 Morphine

| Shown to | Line | Why |
|---|---|---|
| ICP | - **ICP:** no max. total dose | labelled ICP |
| ICP | - **ICP:** no max. total dose | labelled ICP |
| ICP | #### Post-intubation analgosedation (as adjunct to midazolam) | heading |
| ICP | ##### Adult (infusion pump) | heading |
| ICP | **Note:** Withdraw 29mL from 50mL NaCl bag, then add 3mL (30mg) morphine and 6mL (30mg) midazolam to make 30mg:30mg/30mL | Scope PDF: infusions, intubation and post-tube sedation are ICP |
| ICP | - **ICP: **Initial infusion rate: 5mg/hr | labelled ICP |
| ICP | - Lower soft infusion limit: 1mg/hr | Scope PDF: infusions, intubation and post-tube sedation are ICP |
| ICP | - Upper soft infusion limit: 30mg/hr | Scope PDF: infusions, intubation and post-tube sedation are ICP |
| ICP | - Upper hard infusion limit: 50mg/hr | Scope PDF: infusions, intubation and post-tube sedation are ICP |
| ICP | - **ICP: **Default bolus: 2mg (2mL) | labelled ICP |
| ICP | - Lower hard bolus limit: 0.5mg (0.5mL) | Scope PDF: infusions, intubation and post-tube sedation are ICP |
| ICP | - Upper hard bolus limit: 5mg (5mL) | Scope PDF: infusions, intubation and post-tube sedation are ICP |
| AP and ICP | - Consider IM: | override: Scope PDF: morphine IM is AP |
| AP and ICP | - IV/IO unobtainable | override: Scope PDF: morphine IM is AP |
| AP and ICP | - Little risk of hypotension | override: Scope PDF: morphine IM is AP |
| AP and ICP | - Patient contact estimated >20/60 | override: Scope PDF: morphine IM is AP |
| AP and ICP | - No ischaemic chest pain | override: Scope PDF: morphine IM is AP |
| AP and ICP | - 0.1mg/kg IM | override: Scope PDF: morphine IM is AP |
| AP and ICP | - Repeat once @30/60 if required | override: Scope PDF: morphine IM is AP |

### MED 24 Naloxone (Narcan)

| Shown to | Line | Why |
|---|---|---|
| ICP | - **ICP:** 2nd and subsequent doses: | labelled ICP |
| ICP | - 0.4mg IV increments, fast push | continues ICP-labelled item |
| ICP | - May repeat IV dose up to 3 times (to maximum of 2mg) | continues ICP-labelled item |
| ICP | - All doses may be administered IM or IV as the situation demands. | continues ICP-labelled item |
| ICP | - **ICP:** IV: 0.01mg/kg – fast push | labelled ICP |
| ICP | - Maximum paediatric dose: 3 x calculated doses | continues ICP-labelled item |
| ICP | - All doses may be administered IM or IV as the situation demands. | continues ICP-labelled item |

### CMG 11A Heat Abnormalities

| Shown to | Line | Why |
|---|---|---|
| ICP | - **ICP:** Treat significant arrhythmias (as per appropriate CMG). | labelled ICP |

### CMG 11B Hypothermia

| Shown to | Line | Why |
|---|---|---|
| ICP | - **ICP:** Most cardiac arrhythmias resolve with rewarming | labelled ICP |

### CMG 12 Upper Airway Obstruction

| Shown to | Line | Why |
|---|---|---|
| ICP | - **ICP:** If fails: | labelled ICP |
| ICP | - **ICP:** Consider the need for advanced airway management early (e.g. RSI). | labelled ICP |
| ICP | - **ICP:** Consider IV adrenaline infusion. | labelled ICP |
| ICP | - **ICP:** Implement Intubation Algorithm. | labelled ICP |
| ICP | - **ICP:** If not resolved (and continuing signs of hypoxia): | labelled ICP |

### CMG 13 Abdominal Emergencies

| Shown to | Line | Why |
|---|---|---|
| ICP | - **ICP:** Consider intragastric tube to facilitate stomach emptying, if appropriate. | labelled ICP |

### CMG 14 Shock and Hypoperfusion

| Shown to | Line | Why |
|---|---|---|
| ICP | - **ICP:** Treat significant arrhythmias as per appropriate CMG. | labelled ICP |
| ICP | - **ICP:** Adrenaline infusion to maintain sBP of ≥ 90mmHg ICP. | labelled ICP |
| ICP | - **ICP:** Adrenaline infusion if unresponsive to fluid. | labelled ICP |
| ICP | - **ICP:** Consider adrenaline infusion if sBP < 90mmHg with clinical signs of shock, refractory to fluids. | labelled ICP |
| ICP | - **ICP:** Decompress tension pneumothorax if suspected. | labelled ICP |
| ICP | - **ICP:** Adrenaline infusion if sBP < 90mmHg with clinical signs of shock. | labelled ICP |

### CMG 16 Suspected ACS (Acute Coronary Syndrome)

| Shown to | Line | Why |
|---|---|---|
| ICP | - **ICP:** 15 lead ECG as appropriate: | labelled ICP |
| ICP | - **ICP:** Treat haemodynamically significant arrhythmias (as per appropriate CMG). | labelled ICP |
| ICP | - **ICP:** Treat as per **Heparin Checklist.** | labelled ICP |

### CMG 17 Chest Injuries

| Shown to | Line | Why |
|---|---|---|
| ICP | - **ICP:** Suspect a tension pneumothorax in a patient with diminished air entry and with significant respiratory or cardiovascular compromise. | labelled ICP |
| ICP | - **ICP:** Continue to observe and reassess a patient who has been decompressed as tension may redevelop. | labelled ICP |
| ICP | - **ICP:** Have a low threshold for chest decompression. | labelled ICP |

### CMG 18A Autonomic Dysreflexia

| Shown to | Line | Why |
|---|---|---|
| ICP | - **ICP:** Sedation with caution as required. | labelled ICP |

### CMG 22 Seizures

| Shown to | Line | Why |
|---|---|---|
| ICP | #### Confirm Levetiracetam Indication | heading |
| ICP | - Refractory seizure activity 5/60 after second benzodiazepine dose | section about an ICP-only medicine |
| ICP | **OR** | section about an ICP-only medicine |
| ICP | - >20/60 seizure duration. | section about an ICP-only medicine |
| ICP | It is permissible to concurrently administer Midazolam and Levetiracetam if a seizure has persisted ≥20/60 without any pharmacological management prior to ACTA… | section about an ICP-only medicine |
| ICP | #### Mx - Levetiracetam | heading |
| ICP | - **ICP: **Levetiracetam | labelled ICP |

### CMG 24 Drowning

| Shown to | Line | Why |
|---|---|---|
| ICP | - **ICP:** An ETT is preferred but do not remove an effective LMA (if placed prior). | labelled ICP |
| ICP | - **ICP:** Consider delaying treatment of non-life threatening arrhythmias until hypoxia is corrected. | labelled ICP |

### CMG 26C Other Obstetric and Gynaecological Emergencies

| Shown to | Line | Why |
|---|---|---|
| ICP | - **ICP: Pre‐eclampsia:** | labelled ICP |

### CMG 27 Hyperkalaemia

| Shown to | Line | Why |
|---|---|---|
| ICP | - **ICP:** Calcium chloride. | labelled ICP |
| ICP | - **ICP:** Sodium bicarbonate. | labelled ICP |
| ICP | - **ICP:** If ECG changes persist after 10-15 minutes post medication: | labelled ICP |
| ICP | - Repeat calcium chloride and sodium bicarbonate doses once each. | names an ICP-only medicine |
| ICP | - **ICP:** Early sodium bicarbonate - **ICP:** Calcium chloride | labelled ICP |

### CMG 28 Home Dialysis Emergencies

| Shown to | Line | Why |
|---|---|---|
| AP and ICP | This may occur due to excess thinning of the blood by the heparin used in dialysis. Heparin has a **half life of 92 minutes**. | override: Patient's own dialysis heparin; background knowledge for AP |

### CMG 29 Allergic and Anaphylactic Reactions

| Shown to | Line | Why |
|---|---|---|
| ICP | - **ICP:** If inadequate response or deterioration: | labelled ICP |
| ICP | - **ICP:** Consider early advanced airway care if angioedema present. | labelled ICP |

### CMG 35A Poisoning and Overdose

| Shown to | Line | Why |
|---|---|---|
| ICP | - **ICP: **Sodium Bicarbonate. | labelled ICP |

### CMG 37 Combative and Agitated Patients

| Shown to | Line | Why |
|---|---|---|
| ICP | - **ICP:** Consider escalating to polypharmacy sedation with repeat ketamine / midazolam if required. | labelled ICP |

### CMG 38A Meningococcal Disease

| Shown to | Line | Why |
|---|---|---|
| ICP | - **ICP:** If deterioration continues: | labelled ICP |

### CMG 38 Sepsis

| Shown to | Line | Why |
|---|---|---|
| ICP | - **ICP:** Adrenaline infusion if critically unwell or refractory shock post 20ml/kg fluid. | labelled ICP |

### CMG 3C Preexisting Tracheostomy Management

| Shown to | Line | Why |
|---|---|---|
| ICP | - **ICP:** Reinsert new tracheostomy tube or appropriately sized ETT | labelled ICP |
| ICP | - **ICP:** Attempt **ORAL** intubation | labelled ICP |
| ICP | - **ICP:** Attempt intubation of **STOMA:** | labelled ICP |
| ICP | - **ICP:** Consider insertion of new tube or appropriately sized ETT | labelled ICP |
| ICP | - **ICP:** Attempt **ORAL** intubation | labelled ICP |
| ICP | - **ICP:** Attempt intubation of **laryngectomy STOMA:** | labelled ICP |

### CMG 3 Airway Management

| Shown to | Line | Why |
|---|---|---|
| ICP | - **ICP:** Mild sedation to permit **basic** airway management (midazolam). | labelled ICP |
| ICP | - **ICP: Assess need to intubate:** | labelled ICP |
| ICP | - **ICP:** Mild sedation to permit **basic** airway management (midazolam). | labelled ICP |
| ICP | - **ICP: Assess need to intubate:** | labelled ICP |

### CMG 43 Adrenal Crisis

| Shown to | Line | Why |
|---|---|---|
| ICP | - **ICP:** Hydrocortisone. | labelled ICP |

### CMG 4A ROSC: Adult (Return of Spontaneous Circulation)

| Shown to | Line | Why |
|---|---|---|
| ICP | - **ICP:** Treat significant arrhythmias if persistent | labelled ICP |
| ICP | - **ICP:** Consider adrenaline infusion. | labelled ICP |

### CMG 4 Cardiac Arrest: Adult

| Shown to | Line | Why |
|---|---|---|
| ICP | - **ICP: Amiodarone** 300mg after 3rd shock. | labelled ICP |
| ICP | - **ICP: Magnesium sulphate** | labelled ICP |
| ICP | - **ICP: Sodium bicarbonate** | labelled ICP |
| ICP | - **ICP: Sodium bicarbonate** | labelled ICP |

### CMG 5A ROSC: Paediatric (Return of Spontaneous Circulation)

| Shown to | Line | Why |
|---|---|---|
| ICP | - **ICP:** Maintain sedation if an ETT was placed during arrest | labelled ICP |
| ICP | - **ICP:** In a ROSC patient who is responsive and breathing, yet still bradycardic, consider adrenaline infusion. | labelled ICP |
| ICP | - **ICP:** Consider adrenaline infusion. | labelled ICP |

### CMG 5 Cardiac Arrest: Paediatric (<12 years old)

| Shown to | Line | Why |
|---|---|---|
| ICP | - **ICP:** Consider intraosseous access. | labelled ICP |
| ICP | - **ICP: Amiodarone 5mg/kg **(max 150mg) | labelled ICP |
| ICP | - **ICP: Magnesium sulphate 50mg/kg (max 2.5kg)** | labelled ICP |
| ICP | - **ICP: Sodium bicarbonate 1mMol/kg** | labelled ICP |
| ICP | - **ICP:** Consider intraosseous access. | labelled ICP |
| ICP | - **ICP: Sodium bicarbonate 1mMol/kg** | labelled ICP |

### CMG 7 Bradyarrhythmias

| Shown to | Line | Why |
|---|---|---|
| ICP | - **ICP:** If poorly perfused or symptomatic: | labelled ICP |
| ICP | - **ICP:** Repeat atropine once, if required. | labelled ICP |
| ICP | - **ICP:** If perfusion remains poor: | labelled ICP |

### CMG 8 Tachyarrhythmias

| Shown to | Line | Why |
|---|---|---|
| ICP | - **ICP: If SVT:** | labelled ICP |
| ICP | - Adenosine. | names an ICP-only medicine |
| ICP | - **ICP: Symptomatic VT** with cardiac output: | labelled ICP |
| ICP | - Amiodarone | names an ICP-only medicine |
| ICP | - **If amiodarone contraindicated:** lignocaine. | names an ICP-only medicine |
| ICP | - **ICP: Torsades De Pointes: ** | labelled ICP |
| ICP | - Do not use amiodarone. | names an ICP-only medicine |
| ICP | - **Do not** use amiodarone in these patients. | names an ICP-only medicine |
| ICP | - **ICP:** If LVF and hypotension: | labelled ICP |
| ICP | - Treat **cautiously** with amiodarone. | names an ICP-only medicine |
| ICP | - **ICP:** Treat rapid rate with amiodarone concurrently. | labelled ICP |
| ICP | - **ICP:** Treat rapid rate with amiodarone concurrently. | labelled ICP |
| ICP | - **Do not** use amiodarone in these patients. | names an ICP-only medicine |
| ICP | **Note:** unconscious patients post cardiac arrest in rapid AF may be treated with amiodarone unless otherwise contraindicated. Allow several minutes for rhyth… | names an ICP-only medicine |

### CMG 9 Respiratory Distress

| Shown to | Line | Why |
|---|---|---|
| ICP | - **ICP:** Consider hydrocortisone. | labelled ICP |
| ICP | - **ICP: For life‐threatening respiratory distress where cardiorespiratory arrest is considered imminent: ** | labelled ICP |
| ICP | - **ICP:** Consider hydrocortisone. | labelled ICP |
| ICP | - **ICP:** Consider hydrocortisone. | labelled ICP |

### CSM.A01 Manual Clearance (Airway Management)

| Shown to | Line | Why |
|---|---|---|
| ICP | - **ICP:** Mild sedation to permit **basic** airway management (midazolam). | labelled ICP |
| ICP | - **ICP: Assess need to intubate:** | labelled ICP |
| ICP | - **ICP:** Mild sedation to permit **basic** airway management (midazolam). | labelled ICP |
| ICP | - **ICP: Assess need to intubate:** | labelled ICP |

### CSM.A03 Suction (Airway Management)

| Shown to | Line | Why |
|---|---|---|
| ICP | - **ICP:** Mild sedation to permit **basic** airway management (midazolam). | labelled ICP |
| ICP | - **ICP: Assess need to intubate:** | labelled ICP |
| ICP | - **ICP:** Mild sedation to permit **basic** airway management (midazolam). | labelled ICP |
| ICP | - **ICP: Assess need to intubate:** | labelled ICP |

### CSM.A05 Back Blows (Airway Obstruction)

| Shown to | Line | Why |
|---|---|---|
| ICP | - **ICP:** If fails: | labelled ICP |
| ICP | - **ICP:** Consider the need for advanced airway management early (e.g. RSI). | labelled ICP |
| ICP | - **ICP:** Consider IV adrenaline infusion. | labelled ICP |
| ICP | - **ICP:** Implement Intubation Algorithm. | labelled ICP |
| ICP | - **ICP:** If not resolved (and continuing signs of hypoxia): | labelled ICP |

### CSM.A06 Magill Forceps (Airway Obstruction)

| Shown to | Line | Why |
|---|---|---|
| ICP | - **ICP:** If fails: | labelled ICP |
| ICP | - **ICP:** Consider the need for advanced airway management early (e.g. RSI). | labelled ICP |
| ICP | - **ICP:** Consider IV adrenaline infusion. | labelled ICP |
| ICP | - **ICP:** Implement Intubation Algorithm. | labelled ICP |
| ICP | - **ICP:** If not resolved (and continuing signs of hypoxia): | labelled ICP |

### CSM.A19 Intragastric Tube (IGT) Insertion

| Shown to | Line | Why |
|---|---|---|
| ICP | - **Intubated patients:** use laryngoscope and Magill forceps. | override: Oscar: IGT note for intubated patients is ICP |

### CSM.DF01 Drawing Up Drugs

| Shown to | Line | Why |
|---|---|---|
| ICP | - **For hydrocortisone:** draw up 2mls of saline. | names an ICP-only medicine |

### CSM.DF08 Intraosseous Insertion (EZ-IO)

| Shown to | Line | Why |
|---|---|---|
| ICP | - Prime the EZ connect with normal saline or Lignocaine for conscious/semi conscious patients, leaving the syringe attached. | names an ICP-only medicine |
| ICP | - In the conscious patient use the appropriate volume of Lignocaine for first flush. Repeat as required as per clinical guidelines. | names an ICP-only medicine |
| ICP | - In the conscious/semi conscious patient, the port line should be primed with the approved designated dose of Lignocaine. This is to be flushed with 1.2-1.5ml… | names an ICP-only medicine |

### CSM.DF12 Springfuser and Flow Control Tubing

| Shown to | Line | Why |
|---|---|---|
| ICP | - Amiodarone for VT, rapid AF or AFl, with output. | names an ICP-only medicine |

### CSM.M07 Skills Matrix

| Shown to | Line | Why |
|---|---|---|
| ICP | Adenosine \u2714 | names an ICP-only medicine |
| ICP | Amiodarone \u2714 | names an ICP-only medicine |
| ICP | Calcium chloride \u2714 | names an ICP-only medicine |
| ICP | Heparin \u2714 | names an ICP-only medicine |
| ICP | Hydrocortisone \u2714 | names an ICP-only medicine |
| ICP | Lignocaine \u2714 | names an ICP-only medicine |
| ICP | Sodium bicarbonate \u2714 | names an ICP-only medicine |
| ICP | Suxamethonium \u2714 | names an ICP-only medicine |

## Dose table entries

Weight-band and selector rows from `dose_lookup`. Rows for mixed-scope medicines whose route or indication cannot be read from the row are kept ICP-only.

| Medicine | AP and ICP | ICP only | PACER | Kept ICP because route unclear |
|---|---|---|---|---|
| Adenosine | 0 | 3 | 0 | 0 |
| Adrenaline | 364 | 392 | 0 | 238 |
| Amiodarone | 0 | 84 | 0 | 0 |
| Aspirin | 2 | 0 | 0 | 0 |
| Atropine | 3 | 9 | 0 | 3 |
| Calcium Chloride | 0 | 1 | 0 | 0 |
| Ceftriaxone | 5 | 1 | 0 | 0 |
| Fentanyl | 1 | 0 | 0 | 0 |
| Glucagon | 4 | 0 | 0 | 0 |
| Glucose | 30 | 0 | 0 | 0 |
| Glyceryl Trinitrate | 2 | 0 | 0 | 0 |
| Gtn | 12 | 0 | 0 | 0 |
| Heparin | 0 | 10 | 0 | 0 |
| Hydrocortisone | 0 | 4 | 0 | 0 |
| Ibuprofen | 8 | 0 | 0 | 0 |
| Ipratropium | 1 | 0 | 0 | 0 |
| Ketamine | 3 | 56 | 0 | 30 |
| Levetiracetam | 0 | 2 | 0 | 0 |
| Lignocaine | 0 | 6 | 0 | 0 |
| Magnesium | 0 | 124 | 0 | 112 |
| Methoxyflurane | 6 | 0 | 0 | 0 |
| Midazolam | 12 | 88 | 0 | 60 |
| Morphine | 6 | 36 | 0 | 16 |
| Naloxone | 0 | 1 | 0 | 0 |
| Normal Saline | 99 | 33 | 0 | 0 |
| Ondansetron | 4 | 0 | 0 | 0 |
| Oxygen | 1248 | 96 | 0 | 0 |
| Paracetamol | 6 | 0 | 0 | 0 |
| Prochlorperazine | 3 | 0 | 0 | 0 |
| Salbutamol | 2 | 0 | 0 | 0 |
| Sodium Bicarbonate | 0 | 120 | 0 | 0 |
| Suxamethonium | 0 | 18 | 0 | 0 |

Rows of mixed-scope medicines shown to AP users:

- Adrenaline: 1mg IV or IO – fast push
- Adrenaline: Adrenaline (1:10,000) IV/ IO: Formula: 0.01mg/kg Preparation: 1mg in 10mls Dose: 0.05mg Volume: 0.5ml
- Adrenaline: Adrenaline (1:10,000) IV/IO: Formula: 0.01mg/kg Preparation: 1mg in 10mls Dose: 0.07mg Volume: 0.7ml
- Adrenaline: Adrenaline (1:10,000) IV/IO: Formula: 0.01mg/kg Preparation: 1mg in 10mls Dose: 0.11 Volume: 1.1mls
- Adrenaline: Adrenaline (1:10,000): Formula: 0.01mg/kg Preparation: 1mg in 10mls Dose: 0.13mg Volume: 1.3ml
- Adrenaline: Adrenaline (1:10,000): Formula: 0.01mg/kg Preparation: 1mg in 10mls Dose: 0.15mg Volume: 1.5mls
- Adrenaline: Adrenaline (1:10,000): Formula: 0.01mg/kg Preparation: 1mg in 10mls Dose: 0.17mg Volume: 1.7ml
- Adrenaline: Adrenaline (1:10,000): Formula: 0.01mg/kg Preparation: 1mg in 10mls Dose: 0.19mg Volume: 1.9ml
- Adrenaline: Adrenaline (1:10,000): Formula: 0.01mg/kg Preparation: 1mg in 10mls Dose: 0.21mg Volume: 2.1ml
- Adrenaline: Adrenaline (1:10,000): Formula: 0.01mg/kg Preparation: 1mg in 10mls Dose: 0.23mg Volume: 2.3ml
- Adrenaline: Adrenaline (1:10,000): Formula: 0.01mg/kg Preparation: 1mg in 10mls Dose: 0.25mg Volume: 2.5ml
- Adrenaline: Adrenaline (1:10,000): Formula: 0.01mg/kg Preparation: 1mg in 10mls Dose: 0.27mg Volume: 2.7ml
- Adrenaline: Adrenaline (1:10,000): Formula: 0.01mg/kg Preparation: 1mg in 10mls Dose: 0.33mg Volume: 3.3ml
- Adrenaline: Adrenaline (1:10,000): Formula: 0.01mg/kg Preparation: 1mg in 10mls Dose: 0.3mg Volume: 3ml
- Adrenaline: Adrenaline (1:10,000): Formula: 0.01mg/kg Preparation: 1mg in 10mls Dose: 1mg Volume: 10ml
- Adrenaline: IM: 0.01mg/kg (up to 50kg)
- Adrenaline: Weight >10kg: nebulise 5ml adrenaline 1:1,000 Weight <10kg: nebulise 0.5ml/kg adrenaline 1:1,000 Make volume up to 5ml …
- Atropine: In an MCI situation, it’s permissible to simply repeat the initial atropine dose every 5/60.
- Fentanyl: ##### Type Synthetic narcotic analgesic [S8] ##### Presentations 100mcg in 2mL (5mcg/0.1mL) glass ampoule ##### Actions…
- Ketamine: 0.3mg/kg Dilute to 10mL. Administer via Springfusor 0.15mg/kg Dilute to 10mL. Administer via Springfusor
- Ketamine: Up to 4mg/kg IM injection
- Midazolam: 0.2mg/kg IM (max. 10mg)
- Midazolam: Midazolam: 2.5mg – 5mg SC
- Midazolam: Morphine: 10mg IV or SC Midazolam: 5mg IV or 10mg SC. Repeat @10/60 (max. dose 60mg)
- Morphine: Morphine: 10mg IV or SC Midazolam: 5mg IV or 10mg SC. Repeat @10/60 (max. dose 60mg)
- Morphine: Morphine: 2.5mg – 5mg SC
- Morphine: Morphine: IM (Max 2 Doses)
