"""Tests for the ACTAS qualifications_required backfill script.

TDD: written before the implementation exists.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

# Import will fail until the script exists — that is expected at the failing-test stage.
from scripts.backfill_actas_qualifications import backfill_directory, ICP_DRUGS

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "services" / "actas"


@pytest.fixture()
def tmp_actas_dir(tmp_path: Path) -> Path:
    """Copy fixture JSONs into a temp directory so tests are hermetic."""
    dest = tmp_path / "services" / "actas" / "structured"
    dest.mkdir(parents=True)
    for src in FIXTURES_DIR.glob("*.json"):
        shutil.copy(src, dest / src.name)
    return dest


# ---------------------------------------------------------------------------
# Document-level qualifications_required
# ---------------------------------------------------------------------------

class TestDocumentLevelQualifications:
    def test_ap_document_gets_ap_qualification(self, tmp_actas_dir: Path) -> None:
        backfill_directory(tmp_actas_dir)
        data = json.loads((tmp_actas_dir / "fixture_ap_doc.json").read_text())
        assert data["qualifications_required"] == ["AP"]

    def test_icp_document_gets_icp_qualification(self, tmp_actas_dir: Path) -> None:
        backfill_directory(tmp_actas_dir)
        data = json.loads((tmp_actas_dir / "fixture_icp_doc.json").read_text())
        assert data["qualifications_required"] == ["ICP"]


# ---------------------------------------------------------------------------
# Medicine-level qualifications_required inside dose_lookup
# ---------------------------------------------------------------------------

class TestMedicineLevelQualifications:
    def test_ap_medicine_gets_ap_qualification(self, tmp_actas_dir: Path) -> None:
        backfill_directory(tmp_actas_dir)
        data = json.loads((tmp_actas_dir / "fixture_ap_doc.json").read_text())
        for entry in data["dose_lookup"]["Adrenaline"]:
            assert entry["qualifications_required"] == ["AP"]

    def test_icp_medicine_in_ap_doc_gets_icp_qualification(self, tmp_actas_dir: Path) -> None:
        """Amiodarone is an ICP drug even inside an AP-level document."""
        backfill_directory(tmp_actas_dir)
        data = json.loads((tmp_actas_dir / "fixture_ap_doc.json").read_text())
        for entry in data["dose_lookup"]["Amiodarone"]:
            assert entry["qualifications_required"] == ["ICP"]

    def test_icp_medicine_in_icp_doc_gets_icp_qualification(self, tmp_actas_dir: Path) -> None:
        backfill_directory(tmp_actas_dir)
        data = json.loads((tmp_actas_dir / "fixture_icp_doc.json").read_text())
        for entry in data["dose_lookup"]["Suxamethonium"]:
            assert entry["qualifications_required"] == ["ICP"]

    def test_ap_medicine_in_icp_doc_gets_ap_qualification(self, tmp_actas_dir: Path) -> None:
        """Morphine is not an ICP drug, so it gets AP even in an ICP document."""
        backfill_directory(tmp_actas_dir)
        data = json.loads((tmp_actas_dir / "fixture_icp_doc.json").read_text())
        for entry in data["dose_lookup"]["Morphine"]:
            assert entry["qualifications_required"] == ["AP"]


# ---------------------------------------------------------------------------
# Idempotency
# ---------------------------------------------------------------------------

class TestIdempotency:
    def test_running_twice_produces_same_result(self, tmp_actas_dir: Path) -> None:
        backfill_directory(tmp_actas_dir)
        first_pass = {
            p.name: json.loads(p.read_text())
            for p in sorted(tmp_actas_dir.glob("*.json"))
        }
        backfill_directory(tmp_actas_dir)
        second_pass = {
            p.name: json.loads(p.read_text())
            for p in sorted(tmp_actas_dir.glob("*.json"))
        }
        assert first_pass == second_pass

    def test_no_duplicate_qualifications_on_second_run(self, tmp_actas_dir: Path) -> None:
        backfill_directory(tmp_actas_dir)
        backfill_directory(tmp_actas_dir)
        data = json.loads((tmp_actas_dir / "fixture_ap_doc.json").read_text())
        assert data["qualifications_required"] == ["AP"]
        for entry in data["dose_lookup"]["Adrenaline"]:
            assert entry["qualifications_required"] == ["AP"]


# ---------------------------------------------------------------------------
# ICP drug list sanity check
# ---------------------------------------------------------------------------

class TestIcpDrugList:
    def test_authoritative_drugs_present(self) -> None:
        expected = {
            "Adenosine", "Amiodarone", "Heparin", "Hydrocortisone",
            "Lignocaine", "Sodium Bicarbonate", "Suxamethonium", "Levetiracetam",
        }
        assert expected.issubset(set(ICP_DRUGS))
