import json
import plistlib
import zipfile
import yaml
from pathlib import Path

from pipeline.extractor import extract_note, extract_all


def test_extract_note_nsstring_wrapped_title(tmp_path):
    """Handles NSKeyedArchiver NSString objects (dict with NS.string key)."""
    note_dir = tmp_path / "TestSubject"
    note_dir.mkdir(parents=True)
    note_path = note_dir / "My Note.note"

    with zipfile.ZipFile(note_path, "w") as zf:
        objects = [
            "$null",                                              # 0
            {                                                     # 1 root
                "noteName": plistlib.UID(2),
                "noteSubject": plistlib.UID(3),
                "noteModifiedDateKey": plistlib.UID(4),
                "$class": plistlib.UID(7),
            },
            {"$class": plistlib.UID(8), "NS.string": "My Note"},  # 2 NSString title
            "TestSubject",                                        # 3 subject
            {"NS.time": 652000000.0, "$class": plistlib.UID(5)},  # 4 date
            {"$classname": "NSDate", "$classes": ["NSDate", "NSObject"]},  # 5
            {"$classname": "SessionInfo", "$classes": ["SessionInfo", "NSObject"]},  # 6
            {"$classname": "SessionInfo", "$classes": ["SessionInfo", "NSObject"]},  # 7
            {"$classname": "NSMutableString", "$classes": ["NSMutableString", "NSString", "NSObject"]},  # 8
        ]
        metadata = {
            "$version": 100000,
            "$archiver": "NSKeyedArchiver",
            "$top": {"root": plistlib.UID(1)},
            "$objects": objects,
        }
        zf.writestr(
            "My Note/metadata.plist",
            plistlib.dumps(metadata, fmt=plistlib.FMT_BINARY),
        )
        # HandwritingIndex
        index = {"version": 1, "minCompatibleVersion": 1, "pages": {"1": {"text": "OCR text here."}}}
        zf.writestr(
            "My Note/HandwritingIndex/index.plist",
            plistlib.dumps(index, fmt=plistlib.FMT_BINARY),
        )

    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    result = extract_note(note_path, raw_dir)

    assert result["success"] is True
    assert result["title"] == "My Note"
    out_file = raw_dir / "TestSubject" / "My Note.md"
    assert out_file.exists()


def test_extract_note_basic(build_note, tmp_output):
    """Extracts a simple .note with one page of OCR text."""
    note_path = build_note(
        title="Week 2",
        subject="CSA236 Pharmacology",
        pages={"1": "Adrenaline is used in cardiac arrest."},
    )
    result = extract_note(note_path, tmp_output["raw"])

    assert result["success"] is True
    assert result["title"] == "Week 2"
    assert result["subject"] == "CSA236 Pharmacology"

    # Check output file exists and has correct front matter
    out_file = tmp_output["raw"] / "CSA236 Pharmacology" / "Week 2.md"
    assert out_file.exists()
    content = out_file.read_text()
    # Parse YAML front matter
    parts = content.split("---\n", 2)
    meta = yaml.safe_load(parts[1])
    assert meta["title"] == "Week 2"
    assert meta["default_category"] == "Pharmacology"
    assert meta["source_file"] == "CSA236 Pharmacology/Week 2.note"
    assert "Adrenaline is used in cardiac arrest." in parts[2]


def test_extract_note_multi_page_ordered(build_note, tmp_output):
    """Pages are concatenated in numeric order regardless of dict ordering."""
    note_path = build_note(
        title="Multi",
        subject="Test",
        pages={"3": "page three", "1": "page one", "2": "page two"},
    )
    result = extract_note(note_path, tmp_output["raw"])
    out_file = tmp_output["raw"] / "Test" / "Multi.md"
    content = out_file.read_text()
    body = content.split("---\n", 2)[2]
    assert body.index("page one") < body.index("page two") < body.index("page three")


def test_extract_note_missing_handwriting(build_note, tmp_output):
    """Notes without HandwritingIndex are skipped with a warning."""
    note_path = build_note(
        title="PDF Only",
        subject="Test",
        include_handwriting=False,
    )
    result = extract_note(note_path, tmp_output["raw"])
    assert result["success"] is False
    assert "HandwritingIndex" in result["error"]
    out_file = tmp_output["raw"] / "Test" / "PDF Only.md"
    assert not out_file.exists()


def test_extract_note_nsdate_conversion(build_note, tmp_output):
    """NSDate epoch is correctly converted to ISO datetime."""
    # 652000000 NSDate = 652000000 + 978307200 = 1630307200 Unix
    # = 2021-08-30T04:26:40 UTC
    note_path = build_note(
        title="Dated",
        subject="Test",
        last_modified=652000000.0,
    )
    result = extract_note(note_path, tmp_output["raw"])
    out_file = tmp_output["raw"] / "Test" / "Dated.md"
    content = out_file.read_text()
    meta = yaml.safe_load(content.split("---\n", 2)[1])
    assert meta["last_modified"].startswith("2021-08-30")


def test_extract_all_processes_directory(build_note, tmp_output):
    """extract_all processes all .note files in a directory tree."""
    build_note(title="Note1", subject="SubjectA", pages={"1": "text a"})
    build_note(title="Note2", subject="SubjectB", pages={"1": "text b"})
    build_note(title="Bad", subject="SubjectC", include_handwriting=False)

    results = extract_all(tmp_output["base"], tmp_output["raw"])
    successes = [r for r in results if r["success"]]
    failures = [r for r in results if not r["success"]]
    assert len(successes) == 2
    assert len(failures) == 1


def test_extract_all_writes_log(build_note, tmp_output):
    """extract_all writes extraction_log.json to parent of raw dir."""
    build_note(title="Bad", subject="Test", include_handwriting=False)
    extract_all(tmp_output["base"], tmp_output["raw"])

    log_path = tmp_output["raw"].parent / "extraction_log.json"
    assert log_path.exists()
    log = json.loads(log_path.read_text())
    assert len(log["failures"]) == 1
    assert "HandwritingIndex" in log["failures"][0]["error"]
    assert "timestamp" in log["failures"][0]


def test_extract_all_limit(build_note, tmp_output):
    """--limit flag restricts number of files processed."""
    for i in range(5):
        build_note(title=f"Note{i}", subject="Batch", pages={"1": f"text {i}"})

    results = extract_all(tmp_output["base"], tmp_output["raw"], limit=3)
    assert len(results) == 3
