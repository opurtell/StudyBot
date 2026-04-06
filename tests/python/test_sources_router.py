from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from main import app
from sources import router as sources_router

client = TestClient(app)


def test_get_sources_returns_repository_cards(monkeypatch, tmp_path):
    cmg_dir = tmp_path / "cmgs"
    ref_dir = tmp_path / "REFdocs"
    cpd_dir = tmp_path / "CPDdocs"
    personal_dir = tmp_path / "personal"
    note_dir = tmp_path / "noteDocs"
    raw_dir = tmp_path / "raw"
    cleaned_dir = tmp_path / "cleaned"

    (cmg_dir / "cmg-a.json").parent.mkdir(parents=True, exist_ok=True)
    (cmg_dir / "cmg-a.json").write_text("{}", encoding="utf-8")
    ref_dir.mkdir(parents=True, exist_ok=True)
    (ref_dir / "ref-one.md").write_text("# ref", encoding="utf-8")
    cpd_dir.mkdir(parents=True, exist_ok=True)
    (cpd_dir / "cpd-one.md").write_text("# cpd", encoding="utf-8")
    (cpd_dir / "cpd-two.md").write_text("# cpd", encoding="utf-8")
    (personal_dir / "REFdocs").mkdir(parents=True, exist_ok=True)
    (personal_dir / "CPDdocs").mkdir(parents=True, exist_ok=True)
    (personal_dir / "REFdocs" / "ref-one.md").write_text("# ref", encoding="utf-8")
    (personal_dir / "CPDdocs" / "cpd-one.md").write_text("# cpd", encoding="utf-8")
    note_dir.mkdir(parents=True, exist_ok=True)
    (note_dir / "topic-1.note").write_text("note", encoding="utf-8")
    (note_dir / "topic-2.note").write_text("note", encoding="utf-8")
    raw_dir.mkdir(parents=True, exist_ok=True)
    (raw_dir / "topic-1.md").write_text("# raw", encoding="utf-8")
    (raw_dir / "topic-2.md").write_text("# raw", encoding="utf-8")
    cleaned_dir.mkdir(parents=True, exist_ok=True)
    (cleaned_dir / "topic-1.md").write_text("# cleaned", encoding="utf-8")

    monkeypatch.setattr(sources_router, "CMG_STRUCTURED_DIR", cmg_dir)
    monkeypatch.setattr(sources_router, "REFDOCS_DIR", ref_dir)
    monkeypatch.setattr(sources_router, "CPDDOCS_DIR", cpd_dir)
    monkeypatch.setattr(sources_router, "PERSONAL_STRUCTURED_DIR", personal_dir)
    monkeypatch.setattr(sources_router, "NOTABILITY_NOTE_DOCS_DIR", note_dir)
    monkeypatch.setattr(sources_router, "RAW_NOTES_DIR", raw_dir)
    monkeypatch.setattr(sources_router, "CLEANED_NOTES_DIR", cleaned_dir)
    monkeypatch.setattr(
        sources_router,
        "load_refresh_status",
        lambda: {"is_running": False, "last_run_at": "2026-04-04T12:00:00+00:00"},
    )

    response = client.get("/sources")

    assert response.status_code == 200
    data = response.json()
    assert len(data["sources"]) == 4
    assert data["sources"][0]["detail"] == "1 Guideline"
    assert data["sources"][1]["status_text"] == "INGESTED"
    assert data["sources"][2]["status_text"] == "INGESTION IN PROGRESS"
    assert data["sources"][3]["status_text"] == "CLEANING IN PROGRESS"
    assert data["cleaning_feed"][0]["status"] == "complete"
    assert data["cleaning_feed"][1]["status"] == "active"
    assert data["cleaning_feed"][2]["status"] == "active"


def test_get_sources_handles_missing_directories(monkeypatch, tmp_path):
    missing = tmp_path / "missing"

    monkeypatch.setattr(sources_router, "CMG_STRUCTURED_DIR", missing / "cmgs")
    monkeypatch.setattr(sources_router, "REFDOCS_DIR", missing / "ref")
    monkeypatch.setattr(sources_router, "CPDDOCS_DIR", missing / "cpd")
    monkeypatch.setattr(sources_router, "PERSONAL_STRUCTURED_DIR", missing / "personal")
    monkeypatch.setattr(sources_router, "NOTABILITY_NOTE_DOCS_DIR", missing / "notes")
    monkeypatch.setattr(sources_router, "RAW_NOTES_DIR", missing / "raw")
    monkeypatch.setattr(sources_router, "CLEANED_NOTES_DIR", missing / "cleaned")
    monkeypatch.setattr(
        sources_router,
        "load_refresh_status",
        lambda: {"is_running": False, "last_run_at": None},
    )

    response = client.get("/sources")

    assert response.status_code == 200
    data = response.json()
    assert data["sources"][0]["status_text"] == "NOT INGESTED"
    assert data["sources"][1]["detail"] == "0 Documents"
    assert data["sources"][3]["status_text"] == "NO FILES"
    assert data["cleaning_feed"][1]["status"] == "waiting"
    assert data["cleaning_feed"][2]["preview"] == "No Notability note files detected."
