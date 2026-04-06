import yaml
from pathlib import Path

from pipeline.structurer import validate_and_normalise


def _write_cleaned_md(path: Path, front_matter: dict, body: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    fm = yaml.dump(front_matter, default_flow_style=False, allow_unicode=True)
    path.write_text(f"---\n{fm}---\n{body}\n")
    return path


def test_valid_file_passes(tmp_path):
    """A file with all required front matter fields passes validation."""
    fm = {
        "title": "Week 2",
        "subject": "CSA236 Pharmacology",
        "categories": ["Pharmacology"],
        "source_file": "CSA236 Pharmacology/Week 2.note",
        "last_modified": "2021-08-30T04:26:40+00:00",
        "review_flags": [],
    }
    md_path = _write_cleaned_md(tmp_path / "test.md", fm, "Some cleaned text.")
    result = validate_and_normalise(md_path)
    assert result["valid"] is True


def test_missing_categories_fails(tmp_path):
    """A file missing 'categories' fails validation."""
    fm = {
        "title": "Week 2",
        "subject": "CSA236 Pharmacology",
        "source_file": "CSA236 Pharmacology/Week 2.note",
        "last_modified": "2021-08-30T04:26:40+00:00",
    }
    md_path = _write_cleaned_md(tmp_path / "test.md", fm, "text")
    result = validate_and_normalise(md_path)
    assert result["valid"] is False
    assert "categories" in result["error"]


def test_missing_review_flags_defaults_to_empty(tmp_path):
    """A file missing 'review_flags' passes and defaults to []."""
    fm = {
        "title": "Week 2",
        "subject": "CSA236 Pharmacology",
        "categories": ["Pharmacology"],
        "source_file": "CSA236 Pharmacology/Week 2.note",
        "last_modified": "2021-08-30T04:26:40+00:00",
    }
    md_path = _write_cleaned_md(tmp_path / "test.md", fm, "Some cleaned text.")
    result = validate_and_normalise(md_path)
    assert result["valid"] is True
    assert result["has_review_flag"] is False
    content = md_path.read_text()
    assert "review_flags: []\n" in content


def test_normalises_whitespace(tmp_path):
    """Excessive blank lines in body are collapsed to double newlines."""
    fm = {
        "title": "Test",
        "subject": "Test",
        "categories": ["General Paramedicine"],
        "source_file": "Test/Test.note",
        "last_modified": "2021-08-30T04:26:40+00:00",
        "review_flags": [],
    }
    body = "Line one.\n\n\n\n\nLine two.\n\n\nLine three."
    md_path = _write_cleaned_md(tmp_path / "test.md", fm, body)
    result = validate_and_normalise(md_path)
    assert result["valid"] is True
    content = md_path.read_text()
    body_part = content.split("---\n", 2)[2]
    assert "\n\n\n" not in body_part
    assert "Line one.\n\nLine two.\n\nLine three." in body_part


def test_returns_metadata(tmp_path):
    """Result includes parsed metadata for downstream use."""
    fm = {
        "title": "Week 2",
        "subject": "CSA236 Pharmacology",
        "categories": ["Pharmacology", "Clinical Skills"],
        "source_file": "CSA236 Pharmacology/Week 2.note",
        "last_modified": "2021-08-30T04:26:40+00:00",
        "review_flags": ["mldazolam → midazolam"],
    }
    md_path = _write_cleaned_md(tmp_path / "test.md", fm, "text")
    result = validate_and_normalise(md_path)
    assert result["categories"] == ["Pharmacology", "Clinical Skills"]
    assert result["has_review_flag"] is True
    assert result["source_file"] == "CSA236 Pharmacology/Week 2.note"
