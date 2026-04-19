import os
from pathlib import Path
from unittest.mock import patch

import pytest


def _reload_paths():
    import importlib
    import sys

    # Remove cached module
    if "paths" in sys.modules:
        del sys.modules["paths"]

    # Import fresh
    import paths
    return paths


class TestServiceAwarePaths:
    def test_service_structured_dir_shape(self, tmp_path, monkeypatch):
        """Test that service_structured_dir returns a path with expected structure."""
        monkeypatch.setenv("STUDYBOT_USER_DATA", str(tmp_path / "user"))
        monkeypatch.setenv("STUDYBOT_APP_ROOT", str(tmp_path / "app"))
        paths = _reload_paths()

        p = paths.service_structured_dir("actas")
        assert p.name == "structured"
        assert p.parent.name == "actas"
        assert "data" in str(p)
        assert "services" in str(p)

    def test_user_service_structured_dir_shape(self, tmp_path, monkeypatch):
        """Test that user_service_structured_dir returns user data path."""
        monkeypatch.setenv("STUDYBOT_USER_DATA", str(tmp_path / "user"))
        monkeypatch.setenv("STUDYBOT_APP_ROOT", str(tmp_path / "app"))
        paths = _reload_paths()

        p = paths.user_service_structured_dir("actas")
        assert p.name == "structured"
        assert p.parent.name == "actas"
        assert str(p).startswith(str(tmp_path / "user"))

    def test_resolve_prefers_user_dir(self, tmp_path, monkeypatch):
        """Test that resolve_service_structured_dir prefers user directory when it exists with data."""
        user_root = tmp_path / "user"
        app_root = tmp_path / "app"
        user_dir = user_root / "services" / "actas" / "structured"
        user_dir.mkdir(parents=True)
        (user_dir / "x.json").write_text("{}")

        monkeypatch.setenv("STUDYBOT_USER_DATA", str(user_root))
        monkeypatch.setenv("STUDYBOT_APP_ROOT", str(app_root))
        paths = _reload_paths()

        out = paths.resolve_service_structured_dir("actas")
        assert out == user_dir

    def test_resolve_service_structured_dir_falls_back_to_app(self, tmp_path, monkeypatch):
        """Test that resolve_service_structured_dir falls back to app directory when user doesn't exist."""
        user_root = tmp_path / "user"
        app_root = tmp_path / "app"
        app_dir = app_root / "data" / "services" / "actas" / "structured"

        monkeypatch.setenv("STUDYBOT_USER_DATA", str(user_root))
        monkeypatch.setenv("STUDYBOT_APP_ROOT", str(app_root))
        paths = _reload_paths()

        out = paths.resolve_service_structured_dir("actas")
        assert out == app_dir

    def test_resolve_service_structured_dir_falls_back_if_user_empty(self, tmp_path, monkeypatch):
        """Test that resolve_service_structured_dir falls back to app when user dir exists but is empty."""
        user_root = tmp_path / "user"
        app_root = tmp_path / "app"
        user_dir = user_root / "services" / "actas" / "structured"
        user_dir.mkdir(parents=True)  # Create but leave empty
        app_dir = app_root / "data" / "services" / "actas" / "structured"

        monkeypatch.setenv("STUDYBOT_USER_DATA", str(user_root))
        monkeypatch.setenv("STUDYBOT_APP_ROOT", str(app_root))
        paths = _reload_paths()

        out = paths.resolve_service_structured_dir("actas")
        assert out == app_dir

    def test_service_uploads_dir(self, tmp_path, monkeypatch):
        """Test that service_uploads_dir returns correct path under user data."""
        monkeypatch.setenv("STUDYBOT_USER_DATA", str(tmp_path / "user"))
        monkeypatch.setenv("STUDYBOT_APP_ROOT", str(tmp_path / "app"))
        paths = _reload_paths()

        p = paths.service_uploads_dir("actas")
        assert p.name == "uploads"
        assert p.parent.name == "actas"
        assert "services" in str(p)
        assert str(p).startswith(str(tmp_path / "user"))

    def test_user_service_uploads_dir(self, tmp_path, monkeypatch):
        """Test that user_service_uploads_dir is equivalent to service_uploads_dir."""
        monkeypatch.setenv("STUDYBOT_USER_DATA", str(tmp_path / "user"))
        monkeypatch.setenv("STUDYBOT_APP_ROOT", str(tmp_path / "app"))
        paths = _reload_paths()

        p1 = paths.service_uploads_dir("actas")
        p2 = paths.user_service_uploads_dir("actas")
        assert p1 == p2

    def test_service_medications_dir(self, tmp_path, monkeypatch):
        """Test that service_medications_dir returns correct path under user data."""
        monkeypatch.setenv("STUDYBOT_USER_DATA", str(tmp_path / "user"))
        monkeypatch.setenv("STUDYBOT_APP_ROOT", str(tmp_path / "app"))
        paths = _reload_paths()

        p = paths.service_medications_dir("actas")
        assert p.name == "medications"
        assert p.parent.name == "actas"
        assert "services" in str(p)
        assert str(p).startswith(str(tmp_path / "user"))

    def test_bundled_service_structured_dir(self, tmp_path, monkeypatch):
        """Test that bundled_service_structured_dir points to app bundle."""
        monkeypatch.setenv("STUDYBOT_USER_DATA", str(tmp_path / "user"))
        monkeypatch.setenv("STUDYBOT_APP_ROOT", str(tmp_path / "app"))
        paths = _reload_paths()

        p = paths.bundled_service_structured_dir("actas")
        assert p.name == "structured"
        assert p.parent.name == "actas"
        assert str(p).startswith(str(tmp_path / "app"))

    def test_multiple_services(self, tmp_path, monkeypatch):
        """Test that helpers work for different service IDs."""
        monkeypatch.setenv("STUDYBOT_USER_DATA", str(tmp_path / "user"))
        monkeypatch.setenv("STUDYBOT_APP_ROOT", str(tmp_path / "app"))
        paths = _reload_paths()

        # Test ACTAS
        actas_dir = paths.service_structured_dir("actas")
        assert "actas" in str(actas_dir)

        # Test another service
        tas_dir = paths.service_structured_dir("ambulance_tas")
        assert "ambulance_tas" in str(tas_dir)

        # They should be different
        assert actas_dir != tas_dir
