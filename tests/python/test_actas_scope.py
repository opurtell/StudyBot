import glob
import json

import pytest

from guidelines import actas_scope as scope
from quiz.retriever import _visibility_values
from services.qualifications import effective_qualifications
from services.registry import get_service


def _load(pattern: str) -> dict:
    matches = glob.glob(pattern)
    assert matches, pattern
    with open(matches[0], encoding="utf-8") as f:
        return json.load(f)


def _med(prefix: str) -> dict:
    return _load(f"data/cmgs/structured/med/{prefix}_*.json")


def _cmg(prefix: str) -> dict:
    return _load(f"data/services/actas/structured/{prefix}_*.json")


def _csm(code: str) -> dict:
    return _load(f"data/cmgs/structured/csm/CMG_CSM.{code}_*.json")


@pytest.mark.parametrize(
    "name,expected",
    [
        ("Adenosine (Adenocor)", scope.ICP_DRUG),
        ("Calcium Chloride", scope.ICP_DRUG),
        ("Amiodarone", scope.ICP_DRUG),
        ("Adrenaline", scope.MIXED_DRUG),
        ("Magnesium", scope.MIXED_DRUG),
        ("Ketamine Hydrochloride (Ketalar)", scope.MIXED_DRUG),
        ("Gtn", scope.AP_DRUG),
        ("Topical Anaesthetic Cream (LMX4)", scope.AP_DRUG),
        ("Olanzapine", scope.PACER_DRUG),
    ],
)
def test_drug_scope(name, expected):
    assert scope.drug_scope(name) == expected


def test_med_documents_ignore_scraped_icp_flag():
    adrenaline = _med("MED_03")
    assert adrenaline["is_icp_only"] is True
    assert scope.document_scope(adrenaline) is None
    adenosine = _med("MED_02")
    assert adenosine["is_icp_only"] is False
    assert scope.document_scope(adenosine) == scope.ICP


def test_olanzapine_needs_pacer():
    olanzapine = _med("MED_25")
    assert scope.document_scope(olanzapine) == scope.PACER
    segments = scope.classify(olanzapine)
    assert "10mg wafer" not in scope.render(segments, {"AP", "ICP"})
    assert "10mg wafer" in scope.render(segments, {"AP", "PACER"})


def test_adrenaline_ap_text_drops_icp_blocks():
    ap = scope.ap_text(_med("MED_03"))
    assert "IM: 0.5mg" in ap
    assert "IV: 0.01mg/kg" in ap
    assert "NEWBORN ONLY" not in ap
    assert "0.02mg/kg" not in ap
    assert "Upper hard infusion limit" not in ap
    assert "Unresponsive to fluid" not in ap
    assert "Bradyarrhythmias resistant to atropine" not in ap


def test_icp_text_keeps_everything():
    doc = _med("MED_03")
    icp = scope.icp_text(doc)
    for marker in ("NEWBORN ONLY", "Upper hard infusion limit", "IM: 0.5mg"):
        assert marker in icp


def test_atropine_ap_keeps_poisoning_doses_and_drops_bradycardia():
    ap = scope.ap_text(_med("MED_05"))
    assert "**AP: ** IM/IV: initial dose 2400mcg" in ap
    assert "IV / IO / IM: initial dose 2400mcg" in ap
    assert "IV / IO / IM: 600mcg" in ap
    assert "IV / IO: 600mcg" not in ap


def test_magnesium_ap_keeps_eclampsia_only():
    ap = scope.ap_text(_med("MED_20"))
    assert "Seizures due to eclampsia" in ap
    assert "Refractory VF: " not in ap
    assert "Dose is 50mg/kg" not in ap


def test_morphine_ap_keeps_im_and_palliative_and_drops_icp():
    ap = scope.ap_text(_med("MED_23"))
    assert "0.1mg/kg IM" in ap
    assert "max. total dose 20mg" in ap
    assert "no max. total dose" not in ap
    assert "Initial infusion rate" not in ap
    assert "SC/IM/IV: 10mg" in ap


def test_midazolam_ap_keeps_im_seizure_and_palliative_doses():
    ap = scope.ap_text(_med("MED_22"))
    assert "0.2mg/kg IM (max. 10mg)" in ap
    assert "IV/IO push" not in ap
    assert "Withdraw 29mL" not in ap
    assert "2.5 – 5mg SC/IM" in ap


def test_ceftriaxone_io_is_icp():
    ap = scope.ap_text(_med("MED_07"))
    assert "IV preferred" in ap
    assert "given IO" not in ap


def test_icp_only_skills_and_guidelines():
    for code in ("A10", "A11", "A14", "A16", "B10", "C05", "DF07", "DF16"):
        assert scope.document_scope(_csm(code)) == scope.ICP, code
    for code in ("A06", "A17", "A19", "DF03", "DF08", "M07"):
        assert scope.document_scope(_csm(code)) is None, code
    assert scope.document_scope(_cmg("CMG_3A")) == scope.ICP
    assert scope.document_scope(_csm("A02")) is None


def test_igt_intubated_note_is_icp():
    ap = scope.ap_text(_csm("A19"))
    assert "Intubated patients" not in ap
    assert "Insertion with LMA" in ap


def test_cmg_lines_naming_icp_only_medicines_are_icp():
    ap = scope.ap_text(_cmg("CMG_22"))
    assert "Levetiracetam" not in ap
    assert "Midazolam" in ap


def test_dialysis_heparin_background_stays_visible():
    ap = scope.ap_text(_cmg("CMG_28"))
    assert "heparin" in ap.lower()


@pytest.mark.parametrize(
    "medicine,text,icp_only,expected",
    [
        ("Heparin", "5000 units IV", False, scope.ICP),
        ("Adrenaline", "Adrenaline (1:10,000) ETT: 0.02mg/kg", False, scope.ICP),
        ("Adrenaline", "IM: 0.01mg/kg (up to 50kg)", False, scope.BOTH),
        ("Adrenaline", "Formula: 0.01mg/kg", False, scope.ICP),
        ("Ceftriaxone", "May also be given IO", False, scope.ICP),
        ("Ceftriaxone", "50mg/kg IV", False, scope.BOTH),
        ("Adrenaline", "Adrenaline (1:10,000) IV/IO: Formula: 0.01mg/kg Dose: 0.05mg", False, scope.BOTH),
        ("Adrenaline", "Adrenaline (1:10,000): Formula: 0.01mg/kg Adrenaline (1:10,000) ETT: Formula: 0.02mg/kg", False, scope.ICP),
        ("Adrenaline", "1mg IV or IO – fast push ", False, scope.BOTH),
        ("Atropine", "In an MCI situation, repeat the initial atropine dose", False, scope.BOTH),
        ("Atropine", "If heart rate less than 50/minute, consider atropine", False, scope.ICP),
        ("Oxygen", "Titrate to SpO2", True, scope.ICP),
    ],
)
def test_dose_entry_scope(medicine, text, icp_only, expected):
    assert scope.dose_entry_scope(medicine, text, icp_only)[0] == expected


def test_pacer_endorsement_for_actas():
    actas = get_service("actas")
    eff = effective_qualifications("AP", ("PACER",), actas)
    assert eff == frozenset({"AP", "PACER"})
    assert "pacer" in _visibility_values(eff)
    assert "pacer" not in _visibility_values(frozenset({"AP", "ICP"}))


def test_misfiled_doses_are_moved_to_their_medicine():
    from pipeline.actas.dose_tables import correct_misfiled_doses

    index = {
        "Midazolam": [{"text": " Up to 4mg/kg IM injection"}, {"text": "0.1mg/kg IV"}],
        "Naloxone": [{"text": "1.5mcg/kg IN, up to 100mcg. "}],
        "Ketamine": [],
    }
    fixed = correct_misfiled_doses(index, create_missing=False)
    assert fixed["Midazolam"] == [{"text": "0.1mg/kg IV"}]
    assert fixed["Ketamine"] == [{"text": " Up to 4mg/kg IM injection"}]
    assert fixed["Naloxone"] == []
    assert "Fentanyl" not in fixed
    assert "Fentanyl" in correct_misfiled_doses(
        {"Naloxone": [{"text": "1.5mcg/kg IN, up to 100mcg. "}]}
    )


def test_structured_data_has_no_misfiled_doses():
    for path in glob.glob("data/services/actas/structured/CMG*.json"):
        with open(path, encoding="utf-8") as f:
            lookup = json.load(f).get("dose_lookup") or {}
        for entry in lookup.get("Midazolam", []):
            assert "4mg/kg IM" not in entry["text"], path
        for entry in lookup.get("Naloxone", []):
            assert "1.5mcg/kg IN" not in entry["text"], path
