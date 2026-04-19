# Scope of Practice — Ambulance Tasmania (AT)

> **Authoritative source:** Ambulance Tasmania Clinical Practice Guidelines (CPGs) at
> <https://cpg.ambulance.tas.gov.au>. The scope-of-practice matrix URL will be
> confirmed during Task 22 (Phase 0 Playwright probe) and updated here before this doc
> is committed. **[AT URL: TBD — fill in after Task 22 Phase 0 findings.]**
>
> This document is referenced by `registry.py` as `scope_source_doc` for the `at`
> service entry. It summarises the AT qualification structure used by the app's
> retrieval and quiz logic. **Do not commit this file until Task 22 provides the
> authoritative URL and you have signed off on the qualification descriptions.**

---

## Qualification Levels

Ambulance Tasmania uses a base-plus-endorsement model. The two base levels are
independent (neither implies the other). Endorsements require the PARAMEDIC base.

### VAO — Volunteer Ambulance Officer

First-responder scope. VAOs operate under clinical supervision and the AT CPG framework
appropriate to their level.

**Scope includes (to be confirmed against AT CPG corpus):**

- Basic life support (BPR, AED, OPA)
- Patient assessment and vital signs
- Oxygen therapy
- Wound management and haemorrhage control
- Immobilisation and splinting
- Anaphylaxis — adrenaline autoinjector
- Glucose administration
- Assisted medications (GTN, salbutamol MDI) under protocol

> **[REVIEW REQUIRED]** Exact VAO formulary and procedure list must be confirmed
> against the AT CPG site during Task 22. Do not use this section as authoritative
> until reviewed.

---

### PARAMEDIC — Paramedic

Full Ambulance Tasmania paramedic scope. Baseline for all endorsements.

**Scope includes (to be confirmed against AT CPG corpus):**

- Full emergency assessment and management
- Advanced airway (LMA, supraglottic airways, CPAP)
- Cardiac monitoring, 12-lead ECG, manual defibrillation
- IV/IO access
- Standard AT medication formulary (adrenaline, morphine, fentanyl, midazolam,
  salbutamol, GTN, aspirin, ondansetron, and others per current AT CPGs)
- Obstetric emergencies
- Trauma management
- Mental health assessment

> **[REVIEW REQUIRED]** AT medication formulary and procedure list must be verified
> against the AT CPG site during Task 22.

---

### ICP — Intensive Care Paramedic *(endorsement, requires PARAMEDIC)*

Extended critical care scope above PARAMEDIC baseline.

**Scope includes (to be confirmed against AT CPG corpus):**

- Cold intubation (**NO** Rapid sequence intubation available/approved) and surgical airway
- ICP-exclusive medications and dosing
- Advanced haemodynamic monitoring and management
- Extended critical care transport protocols

> **[REVIEW REQUIRED]** Exact ICP endorsement scope must be confirmed against AT CPGs.

---

### PACER — PACER Program *(endorsement, requires PARAMEDIC)*

A specialised Ambulance Tasmania programme. Exact scope to be confirmed.

> **[REVIEW REQUIRED]** PACER scope and eligibility criteria must be sourced from
> the AT CPG site or internal AT documentation during Task 22.

---

### CP_ECP — Community Paramedic / Extended Care Paramedic *(endorsement, requires PARAMEDIC)*

Provides extended care and community health services outside the traditional emergency
response model.

**Scope includes (to be confirmed):**

- Chronic disease management
- Wound care and minor procedure clinics
- Medication review support
- Falls assessment and prevention
- Referral pathways to primary care

> **[REVIEW REQUIRED]** CP/ECP scope must be confirmed against AT documentation
> during Task 22.

---

## Registry Mapping

```python
# src/python/services/registry.py
QualificationModel(
    bases=(
        Base("VAO", "Volunteer Ambulance Officer"),
        Base("PARAMEDIC", "Paramedic"),
    ),
    endorsements=(
        Endorsement("ICP", "Intensive Care Paramedic", requires_base=("PARAMEDIC",)),
        Endorsement("PACER", "PACER", requires_base=("PARAMEDIC",)),
        Endorsement("CP_ECP", "Community Paramedic / Extended Care Paramedic",
                    requires_base=("PARAMEDIC",)),
    ),
)
```

The bases are **independent** — neither implies the other. Endorsements are only
valid when the user holds the PARAMEDIC base (enforced by `effective_qualifications()`).

---

## ChromaDB Collection

All AT content (once ingested in Plan B) will be stored in collection `guidelines_at`.
Personal docs tagged `service: at` will land in `personal_at`.

---

## Task 22 Interlock

This document is intentionally incomplete pending the Ambulance Tasmania Phase 0 probe
(Task 22). Before committing:

1. Run `scripts/at_phase0_probe.py` against `https://cpg.ambulance.tas.gov.au`.
2. Obtain the authoritative scope-of-practice URL (public, not the intranet matrix).
3. Replace all `[REVIEW REQUIRED]` sections with confirmed information.
4. Replace `[AT URL: TBD]` in the header with the confirmed URL.
5. Get user sign-off on the final content.

*Draft created: 2026-04-19. Do not commit until Task 22 complete and user sign-off obtained.*
