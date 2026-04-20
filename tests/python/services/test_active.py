import json
import pytest

from src.python.services.active import active_service_from_path


def test_reads_active_service_from_config(tmp_path):
    cfg = tmp_path / "settings.json"
    cfg.write_text(json.dumps({"active_service": "at"}))
    assert active_service_from_path(cfg).id == "at"


def test_missing_falls_back_to_first(tmp_path):
    cfg = tmp_path / "settings.json"
    cfg.write_text("{}")
    assert active_service_from_path(cfg).id == "actas"


def test_unknown_service_raises(tmp_path):
    cfg = tmp_path / "settings.json"
    cfg.write_text(json.dumps({"active_service": "bogus"}))
    with pytest.raises(KeyError):
        active_service_from_path(cfg)
