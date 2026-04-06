import json
import subprocess
import sys
import yaml
from pathlib import Path


PIPELINE_DIR = Path(__file__).resolve().parents[2] / "src" / "python" / "pipeline"
RUN_SCRIPT = PIPELINE_DIR / "run.py"


def _run_cli(*args, cwd=None):
    """Run the pipeline CLI and return (returncode, stdout, stderr)."""
    result = subprocess.run(
        [sys.executable, str(RUN_SCRIPT), *args],
        capture_output=True,
        text=True,
        cwd=cwd or str(PIPELINE_DIR.parents[1]),  # src/python
    )
    return result.returncode, result.stdout, result.stderr


def _write_cleaned_md(path: Path, title="Note", subject="Test"):
    fm = {
        "title": title,
        "subject": subject,
        "categories": ["General Paramedicine"],
        "source_file": f"{subject}/{title}.note",
        "last_modified": "2021-08-30T04:26:40+00:00",
        "review_flags": [],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    fm_str = yaml.dump(fm, default_flow_style=False, allow_unicode=True)
    path.write_text(f"---\n{fm_str}---\nSome cleaned text for testing.\n")


def test_status_command(tmp_path, build_note):
    """status command reports counts correctly."""
    raw_dir = tmp_path / "raw"
    cleaned_dir = tmp_path / "cleaned"
    raw_dir.mkdir()
    cleaned_dir.mkdir()

    # Create 2 raw files
    for i in range(2):
        (raw_dir / f"note{i}.md").write_text("raw")
    # Create 1 cleaned file
    _write_cleaned_md(cleaned_dir / "note0.md")

    code, stdout, _ = _run_cli(
        "status",
        "--raw-dir", str(raw_dir),
        "--cleaned-dir", str(cleaned_dir),
        "--db-path", str(tmp_path / "chroma"),
    )
    assert code == 0
    assert "2" in stdout  # raw count
    assert "1" in stdout  # cleaned count
