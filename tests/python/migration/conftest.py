"""Conftest for migration script tests.

Provides a ``tmp_repo`` fixture that creates the minimal directory structure
expected by migrate_to_multi_service.py so tests are hermetic and fast.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest


_SAMPLE_CMG_DOC = {
    "title": "Anaphylaxis",
    "cmg_number": "14",
    "category": "Clinical Guidelines",
    "content": "Adrenaline is the first-line treatment for anaphylaxis.",
}

_SAMPLE_PERSONAL_DOC_CONTENT = """\
---
title: ECGs Reference
source_type: ref_doc
category: ECGs
---

# ECGs

Content about ECGs.
"""

_SAMPLE_SETTINGS = {
    "providers": {
        "anthropic": {"api_key": "", "default_model": "claude-haiku-4-5-20251001"},
    },
    "active_provider": "anthropic",
    "quiz_model": "claude-haiku-4-5-20251001",
    "clean_model": "claude-opus-4.6",
}


@pytest.fixture()
def tmp_repo(tmp_path: Path) -> Path:
    """Create a minimal repo-like directory structure for migration tests."""
    # data/cmgs/structured/ — one sample CMG JSON
    cmg_dir = tmp_path / "data" / "cmgs" / "structured"
    cmg_dir.mkdir(parents=True)
    (cmg_dir / "CMG_14_Anaphylaxis.json").write_text(
        json.dumps(_SAMPLE_CMG_DOC, indent=2), encoding="utf-8"
    )

    # data/uploads/ — one sample upload file
    uploads_dir = tmp_path / "data" / "uploads"
    uploads_dir.mkdir(parents=True)
    (uploads_dir / "my_notes.md").write_text("# My Notes\nSome content.", encoding="utf-8")

    # data/personal_docs/structured/ — one sample personal doc
    personal_dir = tmp_path / "data" / "personal_docs" / "structured"
    personal_dir.mkdir(parents=True)
    (personal_dir / "ecgs_reference.md").write_text(
        _SAMPLE_PERSONAL_DOC_CONTENT, encoding="utf-8"
    )

    # config/settings.json — minimal settings without active_service
    config_dir = tmp_path / "config"
    config_dir.mkdir(parents=True)
    (config_dir / "settings.json").write_text(
        json.dumps(_SAMPLE_SETTINGS, indent=2), encoding="utf-8"
    )

    return tmp_path
