"""Conftest for upload router tests.

Monkeypatches USER_DATA_DIR to a tmp_path so uploads land in isolated dirs.
Stubs ChromaDB with an in-memory client so tests don't write to disk.
Sets active_service to "actas" in a temporary settings.json.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import chromadb
import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def upload_tmp(tmp_path: Path):
    """Return a tmp_path configured as USER_DATA_DIR for uploads."""
    return tmp_path


@pytest.fixture()
def client(upload_tmp: Path, monkeypatch):
    """FastAPI test client with upload paths and ChromaDB monkeypatched."""
    # Write a minimal settings.json with active_service set
    config_dir = upload_tmp / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    settings_file = config_dir / "settings.json"
    settings_file.write_text(
        json.dumps({"active_service": "actas", "providers": {}}),
        encoding="utf-8",
    )

    # Create an in-memory ChromaDB client to avoid disk writes
    in_memory_client = chromadb.EphemeralClient()

    # Patch service_uploads_dir in paths and upload.router to use tmp_path
    import paths
    import upload.router as upload_router

    def _fake_service_uploads_dir(service_id: str) -> Path:
        return upload_tmp / "services" / service_id / "uploads"

    monkeypatch.setattr(paths, "USER_DATA_DIR", upload_tmp)
    monkeypatch.setattr(upload_router, "service_uploads_dir", _fake_service_uploads_dir)

    # Stub chunk_and_ingest so tests don't need real ChromaDB or embeddings
    def _fake_chunk_and_ingest(md_path: Path, db_path: Path, collection_name: str = "paramedic_notes") -> dict:  # noqa: ARG001
        return {"chunk_count": 1, "source_file": str(md_path.name), "success": True}

    monkeypatch.setattr(upload_router, "chunk_and_ingest", _fake_chunk_and_ingest)

    from main import app
    return TestClient(app)
