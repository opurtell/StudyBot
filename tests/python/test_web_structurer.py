from __future__ import annotations

import json


def test_structure_crawled_guideline_parses_html(tmp_path):
    from pipeline.actas.web_structurer import structure_crawled_guideline

    crawled = {
        "cmg_title": "Pain Management",
        "category": "Pain Management",
        "html": "<h1>Pain Management</h1><p>Assess pain using appropriate scale.</p><table><tr><td>Drug</td><td>Dose</td></tr><tr><td>Methoxyflurane</td><td>3 mL</td></tr></table>",
        "text": "Pain Management\nAssess pain using appropriate scale.\nDrug Dose\nMethoxyflurane 3 mL",
        "extracted_at": "2026-04-07T10:00:00+00:00",
    }

    crawled_file = tmp_path / "Pain_Management.json"
    with open(crawled_file, "w") as f:
        json.dump(crawled, f)

    output_dir = tmp_path / "structured"
    output_dir.mkdir()

    result = structure_crawled_guideline(
        crawled_path=str(crawled_file),
        output_dir=str(output_dir),
    )

    assert result is not None
    assert result["title"] == "Pain Management"
    assert "pain" in result["content_markdown"].lower()
    assert result["section"] == "Pain Management"


def test_structure_crawled_guideline_skips_on_missing_file(tmp_path):
    from pipeline.actas.web_structurer import structure_crawled_guideline

    result = structure_crawled_guideline(
        crawled_path=str(tmp_path / "nonexistent.json"),
        output_dir=str(tmp_path),
    )
    assert result is None
