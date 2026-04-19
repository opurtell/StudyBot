"""Tests for qualification-set filtering in the Retriever.

These tests verify that the Retriever correctly filters chunks based on
effective_qualifications (replacing the old skill_level string parameter)
and that per-service collection isolation works correctly.
"""

import chromadb
import pytest

from quiz.retriever import Retriever, _shared_retriever


@pytest.fixture()
def in_memory_client():
    """Create a fresh in-memory ChromaDB client for each test."""
    return chromadb.Client()


def _seed_collection(client, collection_name, chunks, metadata_fn):
    """Helper to seed a collection with chunks and per-chunk metadata.

    Args:
        client: ChromaDB client
        collection_name: Name of the collection to create/seed
        chunks: List of (id, text, metadata) tuples
        metadata_fn: Function applied to each metadata dict (not used, kept for API compat)
    """
    col = client.get_or_create_collection(
        collection_name, metadata={"hnsw:space": "cosine"}
    )
    for chunk_id, text, meta in chunks:
        col.add(ids=[chunk_id], documents=[text], metadatas=[meta])


@pytest.fixture(autouse=True)
def _reset_shared_retriever_and_collections():
    """Reset the module-level shared retriever singleton and wipe all ChromaDB collections."""
    import quiz.retriever as mod
    prev = mod._shared_retriever
    mod._shared_retriever = None

    # ChromaDB Client() instances share a global in-process store.
    # Delete all collections to prevent cross-test contamination.
    _client = chromadb.Client()
    for col in _client.list_collections():
        _client.delete_collection(col.name)

    yield
    mod._shared_retriever = prev


# ---------------------------------------------------------------------------
# Test 1: AP-only retrieval excludes ICP chunks
# ---------------------------------------------------------------------------

def test_ap_only_excludes_icp_chunks(in_memory_client):
    """AP users should NOT see chunks tagged visibility='icp'."""
    _seed_collection(
        in_memory_client,
        "guidelines_actas",
        [
            ("icp_1", "ICP-only cardiac content", {"source_type": "cmg", "visibility": "icp", "section": "Cardiac"}),
            ("ap_1", "AP cardiac content", {"source_type": "cmg", "visibility": "ap", "section": "Cardiac"}),
            ("both_1", "Shared cardiac content", {"source_type": "cmg", "visibility": "both", "section": "Cardiac"}),
        ],
        lambda m: m,
    )

    retriever = Retriever(client=in_memory_client, service_id="actas")
    results = retriever.retrieve(
        query="cardiac",
        n=10,
        effective_qualifications=frozenset({"AP"}),
    )

    visibilities = {c.content.split()[0].lower() for c in results}
    assert all("icp-only" not in c.content.lower() for c in results), (
        f"AP retrieval returned ICP-only chunks: {[c.content for c in results]}"
    )
    assert any("AP cardiac" in c.content for c in results), (
        "AP retrieval should include AP-visible chunks"
    )
    assert any("Shared" in c.content for c in results), (
        "AP retrieval should include shared chunks"
    )


# ---------------------------------------------------------------------------
# Test 2: ICP retrieval includes all chunks
# ---------------------------------------------------------------------------

def test_icp_includes_all_chunks(in_memory_client):
    """ICP users should see all visibility levels: both, ap, and icp."""
    _seed_collection(
        in_memory_client,
        "guidelines_actas",
        [
            ("icp_1", "ICP-only cardiac content", {"source_type": "cmg", "visibility": "icp", "section": "Cardiac"}),
            ("ap_1", "AP cardiac content", {"source_type": "cmg", "visibility": "ap", "section": "Cardiac"}),
            ("both_1", "Shared cardiac content", {"source_type": "cmg", "visibility": "both", "section": "Cardiac"}),
        ],
        lambda m: m,
    )

    retriever = Retriever(client=in_memory_client, service_id="actas")
    results = retriever.retrieve(
        query="cardiac",
        n=10,
        effective_qualifications=frozenset({"AP", "ICP"}),
    )

    contents = [c.content for c in results]
    assert len(results) == 3, f"ICP should see all 3 chunks, got {len(results)}: {contents}"
    assert any("ICP-only" in c for c in contents), "ICP should see ICP-only chunks"
    assert any("AP cardiac" in c for c in contents), "ICP should see AP chunks"
    assert any("Shared" in c for c in contents), "ICP should see shared chunks"


# ---------------------------------------------------------------------------
# Test 3: Empty/no qualification requirement always returned
# ---------------------------------------------------------------------------

def test_both_visibility_always_returned(in_memory_client):
    """Chunks with visibility='both' should be returned regardless of qualifications."""
    _seed_collection(
        in_memory_client,
        "guidelines_actas",
        [
            ("both_1", "Shared content A", {"source_type": "cmg", "visibility": "both", "section": "Cardiac"}),
            ("both_2", "Shared content B", {"source_type": "cmg", "visibility": "both", "section": "Trauma"}),
        ],
        lambda m: m,
    )

    retriever = Retriever(client=in_memory_client, service_id="actas")

    # With AP only
    ap_results = retriever.retrieve(
        query="content",
        n=10,
        effective_qualifications=frozenset({"AP"}),
    )
    assert len(ap_results) == 2, f"AP should see both shared chunks, got {len(ap_results)}"

    # With ICP
    icp_results = retriever.retrieve(
        query="content",
        n=10,
        effective_qualifications=frozenset({"AP", "ICP"}),
    )
    assert len(icp_results) == 2, f"ICP should see both shared chunks, got {len(icp_results)}"


# ---------------------------------------------------------------------------
# Test 4: Per-service isolation
# ---------------------------------------------------------------------------

def test_per_service_isolation(in_memory_client):
    """Retriever for 'actas' should only query guidelines_actas / personal_actas."""
    # Seed ACTAS collections
    _seed_collection(
        in_memory_client,
        "guidelines_actas",
        [
            ("actas_1", "ACTAS cardiac guideline", {"source_type": "cmg", "visibility": "both", "section": "Cardiac"}),
        ],
        lambda m: m,
    )
    _seed_collection(
        in_memory_client,
        "personal_actas",
        [
            ("actas_note_1", "ACTAS personal note", {"source_type": "notability_note", "visibility": "both"}),
        ],
        lambda m: m,
    )

    # Seed a different service's collections
    _seed_collection(
        in_memory_client,
        "guidelines_at",
        [
            ("at_1", "AT cardiac guideline", {"source_type": "cmg", "visibility": "both", "section": "Cardiac"}),
        ],
        lambda m: m,
    )
    _seed_collection(
        in_memory_client,
        "personal_at",
        [
            ("at_note_1", "AT personal note", {"source_type": "notability_note", "visibility": "both"}),
        ],
        lambda m: m,
    )

    # ACTAS retriever should NOT see AT data
    actas_retriever = Retriever(client=in_memory_client, service_id="actas")
    actas_results = actas_retriever.retrieve(
        query="cardiac",
        n=10,
        effective_qualifications=frozenset({"AP"}),
    )
    actas_contents = [c.content for c in actas_results]
    assert any("ACTAS" in c for c in actas_contents), "ACTAS retriever should see ACTAS data"
    assert not any("AT cardiac" in c or "AT personal" in c for c in actas_contents), (
        f"ACTAS retriever should NOT see AT data: {actas_contents}"
    )

    # AT retriever should NOT see ACTAS data
    at_retriever = Retriever(client=in_memory_client, service_id="at")
    at_results = at_retriever.retrieve(
        query="cardiac",
        n=10,
        effective_qualifications=frozenset({"PARAMEDIC"}),
    )
    at_contents = [c.content for c in at_results]
    assert any("AT" in c for c in at_contents), "AT retriever should see AT data"
    assert not any("ACTAS" in c for c in at_contents), (
        f"AT retriever should NOT see ACTAS data: {at_contents}"
    )


# ---------------------------------------------------------------------------
# Test 5: get_random_chunk respects qualifications
# ---------------------------------------------------------------------------

def test_get_random_chunk_respects_qualifications(in_memory_client):
    """get_random_chunk should also filter by effective_qualifications."""
    _seed_collection(
        in_memory_client,
        "guidelines_actas",
        [
            ("icp_1", "ICP-only content", {"source_type": "cmg", "visibility": "icp", "section": "Cardiac"}),
            ("both_1", "Shared content", {"source_type": "cmg", "visibility": "both", "section": "Cardiac"}),
        ],
        lambda m: m,
    )

    retriever = Retriever(client=in_memory_client, service_id="actas")

    # AP user should never get the ICP chunk
    for _ in range(20):
        chunk = retriever.get_random_chunk(effective_qualifications=frozenset({"AP"}))
        if chunk is not None:
            assert "ICP-only" not in chunk.content, (
                f"AP get_random_chunk returned ICP content: {chunk.content}"
            )

    # ICP user can get either chunk
    found_icp = False
    found_both = False
    for _ in range(20):
        chunk = retriever.get_random_chunk(effective_qualifications=frozenset({"AP", "ICP"}))
        if chunk is not None:
            if "ICP-only" in chunk.content:
                found_icp = True
            if "Shared" in chunk.content:
                found_both = True
    assert found_icp or found_both, "ICP get_random_chunk should find at least one chunk"


# ---------------------------------------------------------------------------
# Test 6: None qualifications returns all (no filter)
# ---------------------------------------------------------------------------

def test_none_qualifications_returns_all(in_memory_client):
    """When effective_qualifications is None, no visibility filter is applied."""
    _seed_collection(
        in_memory_client,
        "guidelines_actas",
        [
            ("icp_1", "ICP content", {"source_type": "cmg", "visibility": "icp", "section": "Cardiac"}),
            ("ap_1", "AP content", {"source_type": "cmg", "visibility": "ap", "section": "Cardiac"}),
            ("both_1", "Shared content", {"source_type": "cmg", "visibility": "both", "section": "Cardiac"}),
        ],
        lambda m: m,
    )

    retriever = Retriever(client=in_memory_client, service_id="actas")
    results = retriever.retrieve(
        query="content",
        n=10,
        effective_qualifications=None,
    )

    assert len(results) == 3, (
        f"No qualifications filter should return all 3 chunks, got {len(results)}"
    )
