import json
from pathlib import Path

from pipeline.actas.version_dates import apply_version_dates


def _write(path: Path, doc: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc))


def test_dates_applied_by_title_across_subfolders(tmp_path: Path) -> None:
    structured = tmp_path / "structured"
    _write(structured / "CMG_10.json", {"cmg_number": "10", "title": "Diabetic Emergencies", "version_date": None})
    _write(structured / "csm" / "CMG_CSM.C07.json", {"cmg_number": "CSM.C07", "title": "Mechanical CPR", "version_date": None})
    _write(structured / "med" / "MED01.json", {"cmg_number": "MED01", "title": "Adrenaline", "version_date": None})
    _write(structured / "guidelines-index.json", {"title": "Diabetic Emergencies"})
    discovery = tmp_path / "discovery.json"
    discovery.write_text(json.dumps({"guidelines": [
        {"title": "Diabetic Emergencies", "date": "01/02/2025", "version": "2.1"},
        {"title": "CSM.C07 Mechanical CPR", "date": "03/04/2025", "version": "1.0"},
    ]}))

    summary = apply_version_dates(str(discovery), str(structured))

    assert sorted(summary["updated"]) == ["CMG_10.json", "CMG_CSM.C07.json"]
    assert summary["missing"] == ["MED01.json"]
    assert json.loads((structured / "CMG_10.json").read_text())["version_date"] == "01/02/2025 Version 2.1"
    assert json.loads((structured / "csm" / "CMG_CSM.C07.json").read_text())["version_date"] == "03/04/2025 Version 1.0"
    assert "version_date" not in json.loads((structured / "guidelines-index.json").read_text())

    again = apply_version_dates(str(discovery), str(structured))
    assert again["updated"] == [] and again["unchanged"] == 2
