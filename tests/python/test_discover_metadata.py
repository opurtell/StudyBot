from __future__ import annotations

import json
from unittest.mock import patch, MagicMock


def test_discover_metadata_extracts_titles_and_versions(tmp_path):
    from pipeline.actas.discover_metadata import discover_metadata

    mock_item_0 = MagicMock()
    mock_item_0.inner_text.return_value = "Pain Management\n22/03/2024 Version 1.0.2.1"
    mock_item_1 = MagicMock()
    mock_item_1.inner_text.return_value = "Cardiac Arrest\n15/01/2024 Version 2.0.1.0"

    mock_items = MagicMock()
    mock_items.count.return_value = 2
    mock_items.nth.side_effect = [mock_item_0, mock_item_1]

    mock_page = MagicMock()
    mock_page.locator.return_value = mock_items
    mock_page.wait_for_selector.return_value = True
    mock_page.goto.return_value = None

    mock_browser = MagicMock()
    mock_browser.new_context.return_value.new_page.return_value = mock_page
    mock_pw_instance = MagicMock()
    mock_pw_instance.chromium.launch.return_value = mock_browser

    mock_playwright = MagicMock()
    mock_playwright.return_value.__enter__.return_value = mock_pw_instance

    with patch("pipeline.actas.discover_metadata.sync_playwright", mock_playwright):
        with patch("pipeline.actas.discover_metadata._dismiss_modals"):
            result = discover_metadata(output_dir=str(tmp_path))

    assert "guidelines" in result
    assert len(result["guidelines"]) == 2
    assert result["guidelines"][0]["title"] == "Pain Management"
    assert result["guidelines"][0]["version"] == "1.0.2.1"


def test_discover_metadata_compares_against_existing(tmp_path):
    from pipeline.actas.discover_metadata import discover_metadata

    structured_dir = tmp_path / "structured"
    structured_dir.mkdir()
    existing = {
        "id": "pain_management",
        "title": "Pain Management",
        "version_date": "22/03/2024 Version 1.0.2.1",
    }
    with open(structured_dir / "pain_management.json", "w") as f:
        json.dump(existing, f)

    mock_item = MagicMock()
    mock_item.inner_text.return_value = "Pain Management\n22/03/2024 Version 1.0.2.1"

    mock_items = MagicMock()
    mock_items.count.return_value = 1
    mock_items.nth.return_value = mock_item

    mock_page = MagicMock()
    mock_page.locator.return_value = mock_items
    mock_page.wait_for_selector.return_value = True
    mock_page.goto.return_value = None

    mock_browser = MagicMock()
    mock_browser.new_context.return_value.new_page.return_value = mock_page
    mock_pw_instance = MagicMock()
    mock_pw_instance.chromium.launch.return_value = mock_browser

    mock_playwright = MagicMock()
    mock_playwright.return_value.__enter__.return_value = mock_pw_instance

    with patch("pipeline.actas.discover_metadata.sync_playwright", mock_playwright):
        with patch("pipeline.actas.discover_metadata._dismiss_modals"):
            result = discover_metadata(
                output_dir=str(tmp_path),
                structured_dir=str(structured_dir),
            )

    assert result["changed_ids"] == []
    assert result["unchanged_count"] == 1
