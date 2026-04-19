from fastapi.testclient import TestClient

from medication.models import MedicationDose
from main import app
from medication import router as medication_router

client = TestClient(app)

TEST_MEDICATIONS = [
    MedicationDose(
        name="Adrenaline",
        indication="Cardiac arrest",
        contraindications="See clinical management guideline",
        adverse_effects="Tachycardia",
        precautions="Monitor rhythm",
        dose="1 mg IV/IO every 3-5 minutes",
        cmg_reference="CMG 03",
        is_icp_only=False,
    )
]


class TestMedicationDoses:
    def test_get_doses_returns_list(self, monkeypatch):
        monkeypatch.setattr(medication_router, "load_medications", lambda: TEST_MEDICATIONS)
        response = client.get("/medication/doses")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_dose_entry_has_required_fields(self, monkeypatch):
        monkeypatch.setattr(medication_router, "load_medications", lambda: TEST_MEDICATIONS)
        response = client.get("/medication/doses")
        data = response.json()
        if len(data) == 0:
            return
        med = data[0]
        assert "name" in med
        assert "indication" in med
        assert "contraindications" in med
        assert "adverse_effects" in med
        assert "precautions" in med
        assert "dose" in med
        assert "cmg_reference" in med

    def test_doses_contain_adrenaline(self, monkeypatch):
        monkeypatch.setattr(medication_router, "load_medications", lambda: TEST_MEDICATIONS)
        response = client.get("/medication/doses")
        data = response.json()
        names = [m["name"] for m in data]
        assert "Adrenaline" in names

    def test_medication_payload_is_cached_until_invalidated(self, monkeypatch, tmp_path):
        calls = {"count": 0}

        def fake_load() -> list[MedicationDose]:
            calls["count"] += 1
            return TEST_MEDICATIONS

        medication_router.invalidate_medication_cache()
        monkeypatch.setattr(medication_router, "_resolve_medication_index_path", lambda: tmp_path / "missing.json")
        monkeypatch.setattr(medication_router, "load_medications", fake_load)

        first = client.get("/medication/doses")
        second = client.get("/medication/doses")

        assert first.status_code == 200
        assert second.status_code == 200
        assert calls["count"] == 1

        medication_router.invalidate_medication_cache()
        third = client.get("/medication/doses")

        assert third.status_code == 200
        assert calls["count"] == 2
