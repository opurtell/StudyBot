"""Tests for service-aware upload endpoint (Task 9)."""
from __future__ import annotations

from pathlib import Path


def test_upload_accepts_service_and_scope(client, tmp_path, monkeypatch):
    r = client.post(
        "/upload",
        data={"service": "actas", "scope": "general"},
        files={"file": ("test.md", b"# Hi\n", "text/markdown")},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["service"] == "actas"
    assert body["scope"] == "general"


def test_upload_service_scope_defaults_to_service_specific(client):
    """When scope is omitted, it defaults to 'service-specific'."""
    r = client.post(
        "/upload",
        data={"service": "actas"},
        files={"file": ("notes.md", b"# Notes\n\nContent here.", "text/markdown")},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["service"] == "actas"
    assert body["scope"] == "service-specific"


def test_upload_service_required(client):
    """Uploading without service field should fail with 422."""
    r = client.post(
        "/upload",
        files={"file": ("notes.md", b"# Notes\n", "text/markdown")},
    )
    assert r.status_code == 422


def test_upload_source_type_is_upload(client):
    """source_type in response must be 'upload', not 'cpd_doc'."""
    r = client.post(
        "/upload",
        data={"service": "actas", "scope": "service-specific"},
        files={"file": ("notes.md", b"# Notes\n\nContent.", "text/markdown")},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["source_type"] == "upload"
