import os
from pathlib import Path
from unittest.mock import patch

import pytest


def _reload_paths():
    import importlib
    import paths

    importlib.reload(paths)
    return paths


class TestPackagedMode:
    def test_user_data_dir_from_env(self, tmp_path, monkeypatch):
        monkeypatch.setenv("STUDYBOT_USER_DATA", str(tmp_path / "userdata"))
        monkeypatch.setenv("STUDYBOT_APP_ROOT", str(tmp_path / "approot"))
        paths = _reload_paths()
        assert paths.USER_DATA_DIR == tmp_path / "userdata"

    def test_app_root_from_env(self, tmp_path, monkeypatch):
        monkeypatch.setenv("STUDYBOT_USER_DATA", str(tmp_path / "userdata"))
        monkeypatch.setenv("STUDYBOT_APP_ROOT", str(tmp_path / "approot"))
        paths = _reload_paths()
        assert paths.APP_ROOT == tmp_path / "approot"

    def test_settings_path_under_user_data(self, tmp_path, monkeypatch):
        monkeypatch.setenv("STUDYBOT_USER_DATA", str(tmp_path / "ud"))
        monkeypatch.setenv("STUDYBOT_APP_ROOT", str(tmp_path / "ar"))
        paths = _reload_paths()
        assert paths.SETTINGS_PATH == tmp_path / "ud" / "config" / "settings.json"
        assert str(paths.SETTINGS_PATH).startswith(str(tmp_path / "ud"))

    def test_example_settings_under_app_root(self, tmp_path, monkeypatch):
        monkeypatch.setenv("STUDYBOT_USER_DATA", str(tmp_path / "ud"))
        monkeypatch.setenv("STUDYBOT_APP_ROOT", str(tmp_path / "ar"))
        paths = _reload_paths()
        assert (
            paths.EXAMPLE_SETTINGS_PATH
            == tmp_path / "ar" / "config" / "settings.example.json"
        )
        assert str(paths.EXAMPLE_SETTINGS_PATH).startswith(str(tmp_path / "ar"))

    def test_chroma_db_dir_under_user_data(self, tmp_path, monkeypatch):
        monkeypatch.setenv("STUDYBOT_USER_DATA", str(tmp_path / "ud"))
        monkeypatch.setenv("STUDYBOT_APP_ROOT", str(tmp_path / "ar"))
        paths = _reload_paths()
        assert paths.CHROMA_DB_DIR == tmp_path / "ud" / "data" / "chroma_db"

    def test_mastery_db_path_under_user_data(self, tmp_path, monkeypatch):
        monkeypatch.setenv("STUDYBOT_USER_DATA", str(tmp_path / "ud"))
        monkeypatch.setenv("STUDYBOT_APP_ROOT", str(tmp_path / "ar"))
        paths = _reload_paths()
        assert paths.MASTERY_DB_PATH == tmp_path / "ud" / "data" / "mastery.db"

    def test_host_from_env(self, monkeypatch):
        monkeypatch.setenv("STUDYBOT_USER_DATA", "/tmp/ud")
        monkeypatch.setenv("STUDYBOT_APP_ROOT", "/tmp/ar")
        monkeypatch.setenv("STUDYBOT_HOST", "0.0.0.0")
        monkeypatch.setenv("STUDYBOT_PORT", "9999")
        paths = _reload_paths()
        assert paths.HOST == "0.0.0.0"
        assert paths.PORT == 9999

    def test_host_defaults(self, monkeypatch):
        monkeypatch.setenv("STUDYBOT_USER_DATA", "/tmp/ud")
        monkeypatch.setenv("STUDYBOT_APP_ROOT", "/tmp/ar")
        monkeypatch.delenv("STUDYBOT_HOST", raising=False)
        monkeypatch.delenv("STUDYBOT_PORT", raising=False)
        paths = _reload_paths()
        assert paths.HOST == "127.0.0.1"
        assert paths.PORT == 7777

    def test_logs_dir_under_user_data(self, tmp_path, monkeypatch):
        monkeypatch.setenv("STUDYBOT_USER_DATA", str(tmp_path / "ud"))
        monkeypatch.setenv("STUDYBOT_APP_ROOT", str(tmp_path / "ar"))
        paths = _reload_paths()
        assert paths.LOGS_DIR == tmp_path / "ud" / "logs"

    def test_config_dir_under_user_data(self, tmp_path, monkeypatch):
        monkeypatch.setenv("STUDYBOT_USER_DATA", str(tmp_path / "ud"))
        monkeypatch.setenv("STUDYBOT_APP_ROOT", str(tmp_path / "ar"))
        paths = _reload_paths()
        assert paths.CONFIG_DIR == tmp_path / "ud" / "config"


class TestDevMode:
    def test_project_root_fallback(self, monkeypatch):
        monkeypatch.delenv("STUDYBOT_USER_DATA", raising=False)
        monkeypatch.delenv("STUDYBOT_APP_ROOT", raising=False)
        paths = _reload_paths()
        assert paths.PROJECT_ROOT.exists()
        assert paths.USER_DATA_DIR == paths.PROJECT_ROOT
        assert paths.APP_ROOT == paths.PROJECT_ROOT

    def test_dev_paths_are_under_project_root(self, monkeypatch):
        monkeypatch.delenv("STUDYBOT_USER_DATA", raising=False)
        monkeypatch.delenv("STUDYBOT_APP_ROOT", raising=False)
        paths = _reload_paths()
        assert str(paths.SETTINGS_PATH).startswith(str(paths.PROJECT_ROOT))
        assert str(paths.CHROMA_DB_DIR).startswith(str(paths.PROJECT_ROOT))
        assert str(paths.MASTERY_DB_PATH).startswith(str(paths.PROJECT_ROOT))


class TestSettingsRouterUsesPaths:
    @pytest.fixture(autouse=True)
    def _mock_heavy_imports(self, monkeypatch):
        import types
        import sys

        def _stub(name, *attrs):
            mod = types.ModuleType(name)
            for a in attrs:
                setattr(mod, a, lambda *args, **kwargs: None)
            monkeypatch.setitem(sys.modules, name, mod)

        _stub("pipeline.cmg.capture_assets", "capture_all_assets")
        _stub(
            "pipeline.cmg.refresh", "load_refresh_status", "start_refresh_in_background"
        )
        _stub("guidelines.router", "invalidate_guideline_cache")
        _stub("medication.router", "invalidate_medication_cache")
        _stub("llm.factory", "load_config")
        _stub("llm.models", "load_model_registry", "save_model_registry")

    def test_settings_path_matches_paths_module(self, monkeypatch):
        monkeypatch.delenv("STUDYBOT_USER_DATA", raising=False)
        monkeypatch.delenv("STUDYBOT_APP_ROOT", raising=False)
        paths = _reload_paths()
        import importlib
        import settings.router as sr

        importlib.reload(sr)
        assert sr._SETTINGS_PATH == paths.SETTINGS_PATH

    def test_settings_path_packaged_mode(self, tmp_path, monkeypatch):
        monkeypatch.setenv("STUDYBOT_USER_DATA", str(tmp_path / "ud"))
        monkeypatch.setenv("STUDYBOT_APP_ROOT", str(tmp_path / "ar"))
        paths = _reload_paths()
        import importlib
        import settings.router as sr

        importlib.reload(sr)
        assert sr._SETTINGS_PATH == tmp_path / "ud" / "config" / "settings.json"


class TestFactoryUsesPaths:
    def test_default_config_path_matches_paths_module(self, monkeypatch):
        monkeypatch.delenv("STUDYBOT_USER_DATA", raising=False)
        monkeypatch.delenv("STUDYBOT_APP_ROOT", raising=False)
        paths = _reload_paths()
        import importlib
        import llm.factory as fac

        importlib.reload(fac)
        assert fac._DEFAULT_CONFIG_PATH == paths.SETTINGS_PATH

    def test_example_config_path_matches_paths_module(self, monkeypatch):
        monkeypatch.delenv("STUDYBOT_USER_DATA", raising=False)
        monkeypatch.delenv("STUDYBOT_APP_ROOT", raising=False)
        paths = _reload_paths()
        import importlib
        import llm.factory as fac

        importlib.reload(fac)
        assert fac._EXAMPLE_CONFIG_PATH == paths.EXAMPLE_SETTINGS_PATH


class TestModelsUsesPaths:
    def test_env_path_under_project_root(self, monkeypatch):
        monkeypatch.delenv("STUDYBOT_USER_DATA", raising=False)
        monkeypatch.delenv("STUDYBOT_APP_ROOT", raising=False)
        paths = _reload_paths()
        import importlib
        import llm.models as mod

        importlib.reload(mod)
        assert str(mod._ENV_PATH).startswith(str(paths.PROJECT_ROOT))


class TestPipelineRunUsesPaths:
    def test_defaults_match_paths_module(self, monkeypatch):
        monkeypatch.delenv("STUDYBOT_USER_DATA", raising=False)
        monkeypatch.delenv("STUDYBOT_APP_ROOT", raising=False)
        paths = _reload_paths()
        import importlib
        import pipeline.run as pr

        importlib.reload(pr)
        assert pr.DEFAULT_DB_PATH == paths.CHROMA_DB_DIR


class TestMainCors:
    @pytest.fixture(autouse=True)
    def _mock_heavy_imports(self, monkeypatch):
        import types
        import sys

        def _stub(name, *attrs):
            mod = types.ModuleType(name)
            for a in attrs:
                setattr(mod, a, lambda *args, **kwargs: None)
            monkeypatch.setitem(sys.modules, name, mod)

        from fastapi import APIRouter

        _stub_router = APIRouter()

        _stub("pipeline.cmg.capture_assets", "capture_all_assets")
        _stub(
            "pipeline.cmg.refresh", "load_refresh_status", "start_refresh_in_background"
        )
        _stub("llm.factory", "load_config")
        _stub("llm.models", "load_model_registry", "save_model_registry")

        llm_base = types.ModuleType("llm.base")
        llm_base.LLMError = type("LLMError", (Exception,), {})
        llm_base.ErrorCategory = type("ErrorCategory", (), {})
        monkeypatch.setitem(sys.modules, "llm.base", llm_base)

        for mod_name in [
            "guidelines.router",
            "medication.router",
            "search.router",
            "sources.router",
            "settings.router",
        ]:
            mod = types.ModuleType(mod_name)
            mod.router = _stub_router
            monkeypatch.setitem(sys.modules, mod_name, mod)

        quiz_mod = types.ModuleType("quiz.router")
        quiz_mod.warm_quiz_dependencies = lambda *a, **k: None
        quiz_mod.router = _stub_router
        monkeypatch.setitem(sys.modules, "quiz.router", quiz_mod)

    def test_cors_allows_file_origin_in_packaged_mode(self, tmp_path, monkeypatch):
        monkeypatch.setenv("STUDYBOT_USER_DATA", str(tmp_path / "ud"))
        monkeypatch.setenv("STUDYBOT_APP_ROOT", str(tmp_path / "ar"))
        import importlib
        import main

        importlib.reload(main)
        from fastapi.testclient import TestClient

        client = TestClient(main.app)
        response = client.options(
            "/health",
            headers={
                "Origin": "file:///path/to/index.html",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert response.status_code in (200, 204)


import shutil


class TestFirstRunSeeding:
    def test_seeds_settings_from_example(self, tmp_path, monkeypatch):
        monkeypatch.setenv("STUDYBOT_USER_DATA", str(tmp_path / "ud"))
        monkeypatch.setenv("STUDYBOT_APP_ROOT", str(tmp_path / "ar"))
        _reload_paths()

        example_dir = tmp_path / "ar" / "config"
        example_dir.mkdir(parents=True)
        (example_dir / "settings.example.json").write_text('{"test": true}')

        import importlib
        import seed

        importlib.reload(seed)
        seed.seed_user_data()

        settings = (tmp_path / "ud" / "config" / "settings.json").read_text()
        assert '"test"' in settings

    def test_does_not_overwrite_existing_settings(self, tmp_path, monkeypatch):
        monkeypatch.setenv("STUDYBOT_USER_DATA", str(tmp_path / "ud"))
        monkeypatch.setenv("STUDYBOT_APP_ROOT", str(tmp_path / "ar"))
        _reload_paths()

        config_dir = tmp_path / "ud" / "config"
        config_dir.mkdir(parents=True)
        (config_dir / "settings.json").write_text('{"existing": true}')

        example_dir = tmp_path / "ar" / "config"
        example_dir.mkdir(parents=True)
        (example_dir / "settings.example.json").write_text('{"test": true}')

        import importlib
        import seed

        importlib.reload(seed)
        seed.seed_user_data()

        settings = (config_dir / "settings.json").read_text()
        assert '"existing"' in settings
        assert '"test"' not in settings

    def test_creates_writable_dirs(self, tmp_path, monkeypatch):
        monkeypatch.setenv("STUDYBOT_USER_DATA", str(tmp_path / "ud"))
        monkeypatch.setenv("STUDYBOT_APP_ROOT", str(tmp_path / "ar"))
        _reload_paths()

        import importlib
        import seed

        importlib.reload(seed)
        seed.seed_user_data()

        assert (tmp_path / "ud" / "data" / "chroma_db").is_dir()
        assert (tmp_path / "ud" / "logs").is_dir()


class TestPackagedDataPaths:
    def test_cmg_structured_dir_under_app_root(self, tmp_path, monkeypatch):
        monkeypatch.setenv("STUDYBOT_USER_DATA", str(tmp_path / "ud"))
        monkeypatch.setenv("STUDYBOT_APP_ROOT", str(tmp_path / "ar"))
        paths = _reload_paths()
        assert (
            paths.CMG_STRUCTURED_DIR == tmp_path / "ar" / "data" / "cmgs" / "structured"
        )

    def test_refdocs_dir_under_app_root(self, tmp_path, monkeypatch):
        monkeypatch.setenv("STUDYBOT_USER_DATA", str(tmp_path / "ud"))
        monkeypatch.setenv("STUDYBOT_APP_ROOT", str(tmp_path / "ar"))
        paths = _reload_paths()
        assert paths.REFDOCS_DIR == tmp_path / "ar" / "docs" / "REFdocs"

    def test_cpddocs_dir_under_app_root(self, tmp_path, monkeypatch):
        monkeypatch.setenv("STUDYBOT_USER_DATA", str(tmp_path / "ud"))
        monkeypatch.setenv("STUDYBOT_APP_ROOT", str(tmp_path / "ar"))
        paths = _reload_paths()
        assert paths.CPDDOCS_DIR == tmp_path / "ar" / "docs" / "CPDdocs"

    def test_notability_dir_under_app_root(self, tmp_path, monkeypatch):
        monkeypatch.setenv("STUDYBOT_USER_DATA", str(tmp_path / "ud"))
        monkeypatch.setenv("STUDYBOT_APP_ROOT", str(tmp_path / "ar"))
        paths = _reload_paths()
        assert (
            paths.NOTABILITY_NOTE_DOCS_DIR
            == tmp_path / "ar" / "docs" / "notabilityNotes" / "noteDocs"
        )

    def test_dev_mode_cmg_structured_dir_under_project_root(self, monkeypatch):
        monkeypatch.delenv("STUDYBOT_USER_DATA", raising=False)
        monkeypatch.delenv("STUDYBOT_APP_ROOT", raising=False)
        paths = _reload_paths()
        assert str(paths.CMG_STRUCTURED_DIR).startswith(str(paths.PROJECT_ROOT))

    def test_personal_structured_dir_under_user_data(self, tmp_path, monkeypatch):
        monkeypatch.setenv("STUDYBOT_USER_DATA", str(tmp_path / "ud"))
        monkeypatch.setenv("STUDYBOT_APP_ROOT", str(tmp_path / "ar"))
        paths = _reload_paths()
        assert (
            paths.PERSONAL_STRUCTURED_DIR
            == tmp_path / "ud" / "data" / "personal_docs" / "structured"
        )

    def test_raw_notes_dir_under_user_data(self, tmp_path, monkeypatch):
        monkeypatch.setenv("STUDYBOT_USER_DATA", str(tmp_path / "ud"))
        monkeypatch.setenv("STUDYBOT_APP_ROOT", str(tmp_path / "ar"))
        paths = _reload_paths()
        assert paths.RAW_NOTES_DIR == tmp_path / "ud" / "data" / "notes_md" / "raw"

    def test_cleaned_notes_dir_under_user_data(self, tmp_path, monkeypatch):
        monkeypatch.setenv("STUDYBOT_USER_DATA", str(tmp_path / "ud"))
        monkeypatch.setenv("STUDYBOT_APP_ROOT", str(tmp_path / "ar"))
        paths = _reload_paths()
        assert (
            paths.CLEANED_NOTES_DIR == tmp_path / "ud" / "data" / "notes_md" / "cleaned"
        )
