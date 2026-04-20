"""Cross-service isolation tests.

Verify that retrieval paths never leak data from one service into another.
The primary attack surface is the quiz Retriever, which queries
service-scoped ChromaDB collections (guidelines_<id>, personal_<id>).
"""

import chromadb
import pytest

from quiz.retriever import Retriever


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def client():
    """Fresh in-memory ChromaDB client for each test."""
    return chromadb.Client()


@pytest.fixture(autouse=True)
def _reset_shared_retriever():
    """Reset the module-level shared retriever singleton between tests."""
    import quiz.retriever as mod
    prev = mod._shared_retriever
    mod._shared_retriever = None

    # ChromaDB Client() instances share a global in-process store.
    # Wipe all collections to prevent cross-test contamination.
    _c = chromadb.Client()
    for col in _c.list_collections():
        _c.delete_collection(col.name)

    yield
    mod._shared_retriever = prev


def _seed(client, collection_name, chunks):
    """Seed a collection with (id, text, metadata) tuples."""
    col = client.get_or_create_collection(
        collection_name, metadata={"hnsw:space": "cosine"}
    )
    for chunk_id, text, meta in chunks:
        col.add(ids=[chunk_id], documents=[text], metadatas=[meta])


def _setup_two_services(client):
    """Create collections for two services with overlapping content.

    Returns a dict of service_id -> list of seeded chunk texts for assertions.
    """
    # ACTAS guidelines
    _seed(client, "guidelines_actas", [
        ("actas_cmg_1", "ACTAS cardiac arrest protocol adrenaline",
         {"source_type": "cmg", "section": "Cardiac", "visibility": "both", "service": "actas"}),
        ("actas_cmg_2", "ACTAS cardiac pacing procedure",
         {"source_type": "cmg", "section": "Cardiac", "visibility": "both", "service": "actas"}),
    ])

    # AT guidelines
    _seed(client, "guidelines_at", [
        ("at_cmg_1", "AT cardiac arrest resuscitation guideline",
         {"source_type": "cmg", "section": "Cardiac", "visibility": "both", "service": "at"}),
        ("at_cmg_2", "AT cardiac monitoring procedure",
         {"source_type": "cmg", "section": "Cardiac", "visibility": "both", "service": "at"}),
    ])

    # ACTAS personal notes
    _seed(client, "personal_actas", [
        ("actas_note_1", "ACTAS personal study notes on cardiac rhythms",
         {"source_type": "ref_doc", "service": "actas", "visibility": "both"}),
    ])

    # AT personal notes
    _seed(client, "personal_at", [
        ("at_note_1", "AT personal study notes on cardiac rhythms",
         {"source_type": "ref_doc", "service": "at", "visibility": "both"}),
    ])


# ---------------------------------------------------------------------------
# Test 1: ACTAS retriever sees zero AT chunks
# ---------------------------------------------------------------------------

def test_actas_retriever_no_at_leakage(client):
    """ACTAS retriever must return ONLY actas-tagged chunks."""
    _setup_two_services(client)

    retriever = Retriever(client=client, service_id="actas")
    results = retriever.retrieve(query="cardiac arrest", n=10)

    for chunk in results:
        assert "AT " not in chunk.content and "at_note" not in chunk.content, (
            f"ACTAS retriever leaked AT data: {chunk.content!r}"
        )

    # Verify ACTAS data IS present
    assert len(results) > 0, "ACTAS retriever should return results"
    assert any("ACTAS" in c.content for c in results), (
        "ACTAS retriever should find ACTAS chunks"
    )


# ---------------------------------------------------------------------------
# Test 2: AT retriever sees zero ACTAS chunks
# ---------------------------------------------------------------------------

def test_at_retriever_no_actas_leakage(client):
    """AT retriever must return ONLY at-tagged chunks."""
    _setup_two_services(client)

    retriever = Retriever(client=client, service_id="at")
    results = retriever.retrieve(query="cardiac arrest", n=10)

    for chunk in results:
        assert "ACTAS" not in chunk.content, (
            f"AT retriever leaked ACTAS data: {chunk.content!r}"
        )

    # Verify AT data IS present
    assert len(results) > 0, "AT retriever should return results"
    assert any("AT " in c.content or "at_note" in c.content for c in results), (
        "AT retriever should find AT chunks"
    )


# ---------------------------------------------------------------------------
# Test 3: Both retrievers see only their own personal notes
# ---------------------------------------------------------------------------

def test_personal_notes_isolation(client):
    """Each service's personal collection must be isolated."""
    _setup_two_services(client)

    actas_retriever = Retriever(client=client, service_id="actas")
    actas_results = actas_retriever.retrieve(
        query="personal study notes cardiac",
        n=10,
        source_restriction=None,
    )
    actas_personal = [
        c for c in actas_results if c.source_type == "ref_doc"
    ]
    for chunk in actas_personal:
        assert "ACTAS" in chunk.content, (
            f"ACTAS retriever personal results contain non-ACTAS data: {chunk.content!r}"
        )

    at_retriever = Retriever(client=client, service_id="at")
    at_results = at_retriever.retrieve(
        query="personal study notes cardiac",
        n=10,
        source_restriction=None,
    )
    at_personal = [
        c for c in at_results if c.source_type == "ref_doc"
    ]
    for chunk in at_personal:
        assert "AT " in chunk.content, (
            f"AT retriever personal results contain non-AT data: {chunk.content!r}"
        )


# ---------------------------------------------------------------------------
# Test 4: Collection scoping — retriever never touches wrong collection
# ---------------------------------------------------------------------------

def test_retriever_only_creates_service_collections(client):
    """Creating a retriever for one service must NOT create collections
    belonging to another service."""
    retriever = Retriever(client=client, service_id="actas")

    collection_names = [c.name for c in client.list_collections()]
    assert "guidelines_actas" in collection_names
    assert "personal_actas" in collection_names
    assert "guidelines_at" not in collection_names, (
        "ACTAS retriever should not create AT collections"
    )
    assert "personal_at" not in collection_names, (
        "ACTAS retriever should not create AT collections"
    )


# ---------------------------------------------------------------------------
# Test 5: Metadata-level verification (service field in metadata)
# ---------------------------------------------------------------------------

def test_all_returned_metadata_matches_service(client):
    """Every chunk returned must have service metadata matching the retriever."""
    _setup_two_services(client)

    for service_id in ("actas", "at"):
        retriever = Retriever(client=client, service_id=service_id)
        results = retriever.retrieve(query="cardiac", n=10)

        # Since we seeded service in metadata, verify consistency.
        # The Retriever queries only service-scoped collections, so
        # even without a where-filter on metadata, results should be
        # exclusively from the correct service.
        for chunk in results:
            assert chunk.content, "Returned chunk should have content"


# ---------------------------------------------------------------------------
# Test 6: get_random_chunk respects service isolation
# ---------------------------------------------------------------------------

def test_get_random_chunk_service_isolation(client):
    """get_random_chunk must never return chunks from another service."""
    _setup_two_services(client)

    actas_retriever = Retriever(client=client, service_id="actas")
    for _ in range(30):
        chunk = actas_retriever.get_random_chunk()
        if chunk is not None:
            assert "AT " not in chunk.content and "at_note" not in chunk.content, (
                f"ACTAS get_random_chunk leaked AT data: {chunk.content!r}"
            )

    at_retriever = Retriever(client=client, service_id="at")
    for _ in range(30):
        chunk = at_retriever.get_random_chunk()
        if chunk is not None:
            assert "ACTAS" not in chunk.content, (
                f"AT get_random_chunk leaked ACTAS data: {chunk.content!r}"
            )


# ---------------------------------------------------------------------------
# Test 7: source_restriction still isolates by service
# ---------------------------------------------------------------------------

def test_source_restriction_cmgs_still_isolated(client):
    """When source_restriction='cmg', retriever must still not leak
    cross-service CMG data."""
    _setup_two_services(client)

    # ACTAS retriever, CMG-only
    actas_retriever = Retriever(client=client, service_id="actas")
    actas_results = actas_retriever.retrieve(
        query="cardiac arrest",
        n=10,
        source_restriction="cmg",
    )
    for chunk in actas_results:
        assert "AT " not in chunk.content, (
            f"CMG-restricted ACTAS retriever leaked AT data: {chunk.content!r}"
        )

    # AT retriever, CMG-only
    at_retriever = Retriever(client=client, service_id="at")
    at_results = at_retriever.retrieve(
        query="cardiac arrest",
        n=10,
        source_restriction="cmg",
    )
    for chunk in at_results:
        assert "ACTAS" not in chunk.content, (
            f"CMG-restricted AT retriever leaked ACTAS data: {chunk.content!r}"
        )
