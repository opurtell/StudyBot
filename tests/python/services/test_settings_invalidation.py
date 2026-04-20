"""Test that saving settings with a new active_service invalidates
the retriever, guideline, and medication caches."""

import json
import chromadb
import pytest

import quiz.retriever as retriever_mod


@pytest.fixture()
def settings_file(tmp_path):
    """Create a temporary settings file with actas active."""
    path = tmp_path / "settings.json"
    path.write_text(json.dumps({"active_service": "actas"}))
    return path


@pytest.fixture(autouse=True)
def _clean_retriever():
    prev = retriever_mod._shared_retriever
    retriever_mod._shared_retriever = None
    _c = chromadb.Client()
    for col in _c.list_collections():
        _c.delete_collection(col.name)
    yield
    retriever_mod._shared_retriever = prev


def test_save_with_changed_service_resets_retriever(settings_file, monkeypatch):
    """Saving a different active_service must clear the retriever singleton."""
    monkeypatch.setattr("settings.router._SETTINGS_PATH", settings_file)

    client = chromadb.Client()
    actas_r = retriever_mod.Retriever(client=client, service_id="actas")
    retriever_mod._shared_retriever = actas_r

    from settings.router import SaveSettingsRequest, save_settings

    req = SaveSettingsRequest(
        providers={},
        active_provider="",
        quiz_model="test",
        clean_model="test",
        active_service="at",
    )
    save_settings(req)

    assert retriever_mod._shared_retriever is None, (
        "Retriever singleton should be cleared after active_service change"
    )


def test_save_with_same_service_does_not_reset_retriever(settings_file, monkeypatch):
    """Saving the same active_service should NOT clear the retriever."""
    monkeypatch.setattr("settings.router._SETTINGS_PATH", settings_file)

    client = chromadb.Client()
    actas_r = retriever_mod.Retriever(client=client, service_id="actas")
    retriever_mod._shared_retriever = actas_r

    from settings.router import SaveSettingsRequest, save_settings

    req = SaveSettingsRequest(
        providers={},
        active_provider="",
        quiz_model="test",
        clean_model="test",
        active_service="actas",
    )
    save_settings(req)

    assert retriever_mod._shared_retriever is actas_r, (
        "Retriever singleton should NOT be cleared when service unchanged"
    )


def test_vector_store_status_checks_all_services(tmp_path, monkeypatch):
    """vector_store_status must report chunk counts for the active
    service's collections, not hardcoded ACTAS names."""
    import chromadb

    db_dir = tmp_path / "chroma_db"
    db_dir.mkdir()
    client = chromadb.PersistentClient(path=str(db_dir))

    # Seed AT guidelines only
    at_col = client.get_or_create_collection("guidelines_at")
    at_col.add(ids=["at1"], documents=["AT chunk"], metadatas=[{"source_type": "cmg"}])

    monkeypatch.setattr("settings.router.CHROMA_DB_DIR", db_dir)
    # Active service is AT
    settings = tmp_path / "settings.json"
    settings.write_text(json.dumps({"active_service": "at"}))
    monkeypatch.setattr("settings.router._SETTINGS_PATH", settings)

    from settings.router import vector_store_status
    status = vector_store_status()

    assert status["cmg"] == 1, f"Expected 1 AT CMG chunk, got {status['cmg']}"
