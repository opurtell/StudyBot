import json
import os
import pytest

STRUCTURED_DIR = "data/cmgs/structured"
MED_DIR = f"{STRUCTURED_DIR}/med"


@pytest.fixture(scope="module")
def med_data():
    results = {}
    if not os.path.exists(MED_DIR):
        pytest.skip("No structured medication data found")
    for fname in sorted(os.listdir(MED_DIR)):
        if not fname.endswith(".json"):
            continue
        with open(os.path.join(MED_DIR, fname), encoding="utf-8") as f:
            data = json.load(f)
        results[data["title"]] = data
    return results


class TestDoseAccuracy:
    def test_adrenaline_cardiac_arrest_dose(self, med_data):
        adrenaline = next(
            (d for d in med_data.values() if d["title"].startswith("Adrenaline")),
            None,
        )
        assert adrenaline is not None, "Adrenaline medication entry must exist"
        doses = adrenaline["dose_lookup"].get("Adrenaline", [])
        assert len(doses) > 0, "Adrenaline must have dose entries"
        first_dose_text = doses[0]["text"]
        assert "1mg" in first_dose_text or "0.01" in first_dose_text, (
            "Adrenaline cardiac arrest dose should reference 1mg or weight-based 0.01mg/kg"
        )

    def test_amiodarone_exists(self, med_data):
        amiodarone = next(
            (d for d in med_data.values() if d["title"].startswith("Amiodarone")),
            None,
        )
        assert amiodarone is not None, "Amiodarone must be present"

    def test_fentanyl_dose_entries_exist(self, med_data):
        fentanyl = next(
            (d for d in med_data.values() if "Fentanyl" in d["title"]),
            None,
        )
        if fentanyl is None:
            pytest.skip("Fentanyl not found in structured data")
        doses = fentanyl["dose_lookup"].get("Fentanyl", [])
        assert len(doses) > 0, "Fentanyl must have dose entries"

    def test_all_meds_have_content(self, med_data):
        for name, data in med_data.items():
            content = data.get("content_markdown", "")
            assert len(content) > 50, (
                f"{name} must have substantive content (got {len(content)} chars)"
            )

    def test_all_meds_have_cmg_number(self, med_data):
        for name, data in med_data.items():
            assert data.get("cmg_number"), f"{name} must have a cmg_number"

    def test_total_med_count(self, med_data):
        assert len(med_data) >= 30, (
            f"Expected at least 30 medicines, got {len(med_data)}"
        )
