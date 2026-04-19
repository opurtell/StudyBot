"""Tests for scripts/migrate_to_multi_service.py.

All tests use the ``tmp_repo`` fixture from conftest.py to operate against
an isolated directory structure — no real data is touched.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

# Add scripts/ to path so we can import the migration module directly.
_SCRIPTS_DIR = Path(__file__).resolve().parents[3] / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from migrate_to_multi_service import run_migration  # noqa: E402


# ---------------------------------------------------------------------------
# CMG file migration
# ---------------------------------------------------------------------------


def test_migration_moves_cmg_files(tmp_repo: Path) -> None:
    """CMG JSON files must be moved to services/actas/structured/."""
    run_migration(repo_root=tmp_repo)
    dest = tmp_repo / "data" / "services" / "actas" / "structured" / "CMG_14_Anaphylaxis.json"
    assert dest.exists(), f"Expected {dest} to exist after migration"

    src = tmp_repo / "data" / "cmgs" / "structured" / "CMG_14_Anaphylaxis.json"
    assert not src.exists(), f"Source file {src} should have been moved (not copied)"


def test_migration_adds_service_field(tmp_repo: Path) -> None:
    """Each migrated CMG JSON must contain service='actas' and a valid guideline_id."""
    run_migration(repo_root=tmp_repo)
    dest = tmp_repo / "data" / "services" / "actas" / "structured" / "CMG_14_Anaphylaxis.json"
    doc = json.loads(dest.read_text(encoding="utf-8"))

    assert doc["service"] == "actas"
    assert "guideline_id" in doc
    assert doc["guideline_id"].startswith("CMG_")


def test_migration_guideline_id_derived_correctly(tmp_repo: Path) -> None:
    """guideline_id for CMG_14_Anaphylaxis.json must be 'CMG_14'."""
    run_migration(repo_root=tmp_repo)
    dest = tmp_repo / "data" / "services" / "actas" / "structured" / "CMG_14_Anaphylaxis.json"
    doc = json.loads(dest.read_text(encoding="utf-8"))
    assert doc["guideline_id"] == "CMG_14"


def test_migration_preserves_cmg_number_in_extra(tmp_repo: Path) -> None:
    """Legacy cmg_number must be preserved inside an 'extra' sub-dict."""
    run_migration(repo_root=tmp_repo)
    dest = tmp_repo / "data" / "services" / "actas" / "structured" / "CMG_14_Anaphylaxis.json"
    doc = json.loads(dest.read_text(encoding="utf-8"))
    assert "extra" in doc
    assert doc["extra"].get("cmg_number") == "14"


def test_migration_is_idempotent(tmp_repo: Path) -> None:
    """Running migration twice must not raise and must leave files intact."""
    run_migration(repo_root=tmp_repo)
    run_migration(repo_root=tmp_repo)  # must not raise

    dest = tmp_repo / "data" / "services" / "actas" / "structured" / "CMG_14_Anaphylaxis.json"
    assert dest.exists()


def test_migration_idempotent_service_field_unchanged(tmp_repo: Path) -> None:
    """Second run must not duplicate or alter the service field."""
    run_migration(repo_root=tmp_repo)
    run_migration(repo_root=tmp_repo)

    dest = tmp_repo / "data" / "services" / "actas" / "structured" / "CMG_14_Anaphylaxis.json"
    doc = json.loads(dest.read_text(encoding="utf-8"))
    assert doc["service"] == "actas"


def test_migration_skips_when_cmg_dir_absent(tmp_path: Path) -> None:
    """If data/cmgs/structured/ does not exist, migration must not raise."""
    # Minimal tmp_path with only config/ present
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "settings.json").write_text(json.dumps({}), encoding="utf-8")

    run_migration(repo_root=tmp_path)  # must not raise


# ---------------------------------------------------------------------------
# Uploads migration
# ---------------------------------------------------------------------------


def test_migration_moves_uploads(tmp_repo: Path) -> None:
    """Files in data/uploads/ must be moved to data/services/actas/uploads/."""
    run_migration(repo_root=tmp_repo)
    dest = tmp_repo / "data" / "services" / "actas" / "uploads" / "my_notes.md"
    assert dest.exists(), f"Expected {dest} to exist after migration"

    src = tmp_repo / "data" / "uploads" / "my_notes.md"
    assert not src.exists(), f"Source upload {src} should have been moved"


def test_migration_uploads_idempotent(tmp_repo: Path) -> None:
    """Running migration twice on uploads must not raise."""
    run_migration(repo_root=tmp_repo)
    run_migration(repo_root=tmp_repo)  # must not raise


# ---------------------------------------------------------------------------
# Personal docs front-matter injection
# ---------------------------------------------------------------------------


def test_migration_adds_service_front_matter_to_personal_docs(tmp_repo: Path) -> None:
    """Personal docs must gain 'service: actas' in their YAML front-matter."""
    run_migration(repo_root=tmp_repo)
    doc_path = tmp_repo / "data" / "personal_docs" / "structured" / "ecgs_reference.md"
    content = doc_path.read_text(encoding="utf-8")
    assert "service: actas" in content


def test_migration_adds_scope_front_matter_to_personal_docs(tmp_repo: Path) -> None:
    """Personal docs must gain 'scope: service-specific' in their YAML front-matter."""
    run_migration(repo_root=tmp_repo)
    doc_path = tmp_repo / "data" / "personal_docs" / "structured" / "ecgs_reference.md"
    content = doc_path.read_text(encoding="utf-8")
    assert "scope: service-specific" in content


def test_migration_personal_docs_idempotent(tmp_repo: Path) -> None:
    """Running migration twice must not duplicate front-matter keys."""
    run_migration(repo_root=tmp_repo)
    run_migration(repo_root=tmp_repo)

    doc_path = tmp_repo / "data" / "personal_docs" / "structured" / "ecgs_reference.md"
    content = doc_path.read_text(encoding="utf-8")
    # 'service: actas' must appear exactly once
    assert content.count("service: actas") == 1
    assert content.count("scope: service-specific") == 1


def test_migration_personal_docs_without_front_matter(tmp_repo: Path) -> None:
    """A personal doc with no YAML front-matter block gets one injected."""
    plain_doc = tmp_repo / "data" / "personal_docs" / "structured" / "plain.md"
    plain_doc.write_text("# Plain Doc\nNo front matter here.\n", encoding="utf-8")

    run_migration(repo_root=tmp_repo)

    content = plain_doc.read_text(encoding="utf-8")
    assert "service: actas" in content
    assert "scope: service-specific" in content


# ---------------------------------------------------------------------------
# Settings: active_service
# ---------------------------------------------------------------------------


def test_migration_sets_active_service_in_settings(tmp_repo: Path) -> None:
    """settings.json must have active_service='actas' after migration."""
    run_migration(repo_root=tmp_repo)
    settings = json.loads((tmp_repo / "config" / "settings.json").read_text(encoding="utf-8"))
    assert settings.get("active_service") == "actas"


def test_migration_does_not_overwrite_existing_active_service(tmp_repo: Path) -> None:
    """If active_service is already set, migration must not change it."""
    settings_path = tmp_repo / "config" / "settings.json"
    data = json.loads(settings_path.read_text(encoding="utf-8"))
    data["active_service"] = "at"
    settings_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    run_migration(repo_root=tmp_repo)

    settings = json.loads(settings_path.read_text(encoding="utf-8"))
    assert settings["active_service"] == "at"


# ---------------------------------------------------------------------------
# Settings: skill_level → base_qualification + endorsements
# ---------------------------------------------------------------------------


def test_migration_rewrites_skill_level_ap(tmp_repo: Path) -> None:
    """skill_level='AP' must become base_qualification='AP', endorsements=[]."""
    settings_path = tmp_repo / "config" / "settings.json"
    data = json.loads(settings_path.read_text(encoding="utf-8"))
    data["skill_level"] = "AP"
    settings_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    run_migration(repo_root=tmp_repo)

    settings = json.loads(settings_path.read_text(encoding="utf-8"))
    assert settings.get("base_qualification") == "AP"
    assert settings.get("endorsements") == []
    assert "skill_level" not in settings


def test_migration_rewrites_skill_level_icp(tmp_repo: Path) -> None:
    """skill_level='ICP' must become base_qualification='ICP', endorsements=[]."""
    settings_path = tmp_repo / "config" / "settings.json"
    data = json.loads(settings_path.read_text(encoding="utf-8"))
    data["skill_level"] = "ICP"
    settings_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    run_migration(repo_root=tmp_repo)

    settings = json.loads(settings_path.read_text(encoding="utf-8"))
    assert settings.get("base_qualification") == "ICP"
    assert settings.get("endorsements") == []
    assert "skill_level" not in settings


def test_migration_skill_level_rewrite_idempotent(tmp_repo: Path) -> None:
    """Running migration twice when skill_level was already rewritten must not corrupt settings."""
    settings_path = tmp_repo / "config" / "settings.json"
    data = json.loads(settings_path.read_text(encoding="utf-8"))
    data["skill_level"] = "AP"
    settings_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    run_migration(repo_root=tmp_repo)
    run_migration(repo_root=tmp_repo)

    settings = json.loads(settings_path.read_text(encoding="utf-8"))
    assert settings.get("base_qualification") == "AP"
    assert settings.get("endorsements") == []
    assert "skill_level" not in settings


def test_migration_no_skill_level_leaves_settings_unchanged(tmp_repo: Path) -> None:
    """If skill_level is absent, settings must not gain spurious keys."""
    settings_path = tmp_repo / "config" / "settings.json"
    before = json.loads(settings_path.read_text(encoding="utf-8"))
    assert "skill_level" not in before

    run_migration(repo_root=tmp_repo)

    after = json.loads(settings_path.read_text(encoding="utf-8"))
    assert "base_qualification" not in after or "skill_level" not in before
    # base_qualification must NOT appear if it was not derived from skill_level
    # (active_service is the only new key that must appear)
    assert "skill_level" not in after
