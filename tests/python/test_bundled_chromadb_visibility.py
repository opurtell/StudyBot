"""Verify the bundled ChromaDB ships with visibility metadata on every CMG chunk."""

import chromadb
import pytest

from paths import CHROMA_DB_DIR


@pytest.fixture
def _cmg_collection():
    client = chromadb.PersistentClient(path=str(CHROMA_DB_DIR))
    return client.get_or_create_collection("cmg_guidelines")


def test_all_cmg_chunks_have_visibility(_cmg_collection):
    """Every CMG chunk must carry a 'visibility' field (both|icp|ap)."""
    col = _cmg_collection
    if col.count() == 0:
        pytest.skip("No CMG chunks in local ChromaDB")

    all_data = col.get(include=["metadatas"])
    missing = [
        (i, mid)
        for i, (mid, meta) in enumerate(
            zip(all_data["ids"], all_data["metadatas"])
        )
        if "visibility" not in meta
    ]
    assert missing == [], (
        f"{len(missing)} chunks missing 'visibility' metadata. "
        f"First 5: {missing[:5]}. Re-run the CMG chunker to regenerate."
    )


def test_visibility_values_are_valid(_cmg_collection):
    """Visibility values must be one of: both, icp, ap."""
    col = _cmg_collection
    if col.count() == 0:
        pytest.skip("No CMG chunks in local ChromaDB")

    all_data = col.get(include=["metadatas"])
    valid = {"both", "icp", "ap"}
    invalid = [
        (i, mid, meta.get("visibility"))
        for i, (mid, meta) in enumerate(
            zip(all_data["ids"], all_data["metadatas"])
        )
        if meta.get("visibility") not in valid
    ]
    assert invalid == [], (
        f"{len(invalid)} chunks have invalid visibility values. "
        f"First 5: {invalid[:5]}"
    )
