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

    summary = apply_version_dates(str(discovery), str(structured), str(tmp_path / "no-bundles"))

    assert sorted(summary["updated"]) == ["CMG_10.json", "CMG_CSM.C07.json"]
    assert summary["missing"] == ["MED01.json"]
    assert json.loads((structured / "CMG_10.json").read_text())["version_date"] == "01/02/2025 Version 2.1"
    assert json.loads((structured / "csm" / "CMG_CSM.C07.json").read_text())["version_date"] == "03/04/2025 Version 1.0"
    assert "version_date" not in json.loads((structured / "guidelines-index.json").read_text())

    again = apply_version_dates(str(discovery), str(structured), str(tmp_path / "no-bundles"))
    assert again["updated"] == [] and again["unchanged"] == 2


def test_dates_applied_from_bundle_changelog(tmp_path: Path) -> None:
    bundles = tmp_path / "investigation"
    bundles.mkdir()
    (bundles / "2_main.abc.js").write_text(
        'x=[{version:"1.0.5.4",date:"12/05/2026",changes:[]},{version:"1.0.5.2",date:"23/01/2026",changes:[]}]'
    )
    (bundles / "7_common.def.js").write_text(
        'y=[{"app_version":"1.0.5.2","cpg_reference":"CMG 4","type":"Update:","details":"a"},'
        '{"app_version":"1.0.5.4","cpg_reference":"CMG 4","type":"Update:","details":"b"},'
        '{"app_version":"1.0.5.4","cpg_reference":"CSM.C07","type":"New:","details":"c"},'
        '{"app_version":"1.0.5.2","cpg_reference":"MED29","type":"Update:","details":"d"}]'
    )
    structured = tmp_path / "structured"
    _write(structured / "CMG_4.json", {"cmg_number": "4", "title": "Cardiac Arrest: Adult"})
    _write(structured / "CMG_44.json", {"cmg_number": "44", "title": "Febrile Paediatric"})
    _write(structured / "csm" / "CMG_CSM.C07.json", {"cmg_number": "CSM.C07", "title": "Mechanical CPR"})
    _write(structured / "med" / "MED_29.json", {"cmg_number": "29", "title": "Salbutamol"})

    summary = apply_version_dates(str(tmp_path / "missing.json"), str(structured), str(bundles))

    assert summary["missing"] == ["CMG_44.json"]
    assert json.loads((structured / "CMG_4.json").read_text())["version_date"] == "12/05/2026 Version 1.0.5.4"
    assert json.loads((structured / "csm" / "CMG_CSM.C07.json").read_text())["version_date"] == "12/05/2026 Version 1.0.5.4"
    assert json.loads((structured / "med" / "MED_29.json").read_text())["version_date"] == "23/01/2026 Version 1.0.5.2"
