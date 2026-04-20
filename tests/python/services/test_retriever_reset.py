"""Test that reset_retriever() clears the singleton so the next
get_retriever() call picks up the current active_service."""

import chromadb
import pytest

import quiz.retriever as retriever_mod


@pytest.fixture(autouse=True)
def _clean_singleton():
    """Ensure no cached retriever leaks between tests."""
    prev = retriever_mod._shared_retriever
    retriever_mod._shared_retriever = None
    # Wipe in-memory ChromaDB
    _c = chromadb.Client()
    for col in _c.list_collections():
        _c.delete_collection(col.name)
    yield
    retriever_mod._shared_retriever = prev


def test_reset_clears_singleton():
    """After reset_retriever(), _shared_retriever must be None."""
    client = chromadb.Client()

    col = client.get_or_create_collection("guidelines_actas", metadata={"hnsw:space": "cosine"})
    col.add(ids=["a"], documents=["actas chunk"], metadatas=[{"source_type": "cmg", "visibility": "both"}])

    r1 = retriever_mod.Retriever(client=client, service_id="actas")
    retriever_mod._shared_retriever = r1
    assert retriever_mod._shared_retriever is r1

    retriever_mod.reset_retriever()
    assert retriever_mod._shared_retriever is None


def test_get_retriever_after_reset_uses_new_service(tmp_path, monkeypatch):
    """After reset, get_retriever() should build a retriever for the
    currently-active service, not a previously-cached one."""
    from services.registry import REGISTRY

    client = chromadb.Client()

    for svc in REGISTRY:
        col = client.get_or_create_collection(
            f"guidelines_{svc.id}", metadata={"hnsw:space": "cosine"}
        )
        col.add(
            ids=[f"{svc.id}_1"],
            documents=[f"{svc.display_name} cardiac protocol"],
            metadatas=[{"source_type": "cmg", "section": "Cardiac", "visibility": "both"}],
        )

    actas_r = retriever_mod.Retriever(client=client, service_id="actas")
    retriever_mod._shared_retriever = actas_r

    retriever_mod.reset_retriever()

    at_svc = [s for s in REGISTRY if s.id == "at"][0]
    monkeypatch.setattr(
        "services.active.active_service", lambda: at_svc
    )

    new_r = retriever_mod.get_retriever()
    assert new_r._service_id == "at"
    assert new_r is not actas_r
