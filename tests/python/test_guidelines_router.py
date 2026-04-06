from __future__ import annotations

import pytest
from httpx import AsyncClient, ASGITransport

from main import app
from guidelines.markdown import normalise_markdown_payload, normalise_markdown_syntax
from guidelines import router as guidelines_router


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.mark.anyio
async def test_list_guidelines(client: AsyncClient):
    resp = await client.get("/guidelines")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    if data:
        first = data[0]
        assert "id" in first
        assert "cmg_number" in first
        assert "title" in first
        assert "section" in first
        assert "source_type" in first


@pytest.mark.anyio
async def test_list_guidelines_type_filter(client: AsyncClient):
    resp = await client.get("/guidelines", params={"type": "med"})
    assert resp.status_code == 200
    data = resp.json()
    for item in data:
        assert item["source_type"] == "med"


@pytest.mark.anyio
async def test_list_guidelines_section_filter(client: AsyncClient):
    resp = await client.get("/guidelines", params={"section": "Cardiac"})
    assert resp.status_code == 200
    data = resp.json()
    for item in data:
        assert item["section"] == "Cardiac"


@pytest.mark.anyio
async def test_get_guideline_detail(client: AsyncClient):
    list_resp = await client.get("/guidelines")
    items = list_resp.json()
    if not items:
        pytest.skip("No guidelines data available")
    first_id = items[0]["id"]
    resp = await client.get(f"/guidelines/{first_id}")
    assert resp.status_code == 200
    detail = resp.json()
    assert detail["id"] == first_id
    assert "content_markdown" in detail


@pytest.mark.anyio
async def test_get_guideline_detail_not_found(client: AsyncClient):
    resp = await client.get("/guidelines/nonexistent_id")
    assert resp.status_code == 404


def test_guideline_summaries_are_cached(monkeypatch, tmp_path):
    calls = {"count": 0}

    def fake_load_all_raw() -> list[dict]:
        calls["count"] += 1
        return [
            {
                "id": "CMG_1_Test",
                "cmg_number": "1",
                "title": "Test",
                "section": "General Care",
                "_source_type": "cmg",
                "is_icp_only": False,
            }
        ]

    guidelines_router.invalidate_guideline_cache()
    monkeypatch.setattr(guidelines_router, "GUIDELINES_INDEX_PATH", tmp_path / "missing.json")
    monkeypatch.setattr(guidelines_router, "_load_all_raw", fake_load_all_raw)

    first = guidelines_router.list_guidelines()
    second = guidelines_router.list_guidelines()

    assert first == second
    assert calls["count"] == 1


def test_normalise_markdown_syntax_breaks_joined_headings():
    content = "#### Cardiac arrest##### Adult\n- 1mg IV"

    result = normalise_markdown_syntax(content)

    assert result == "#### Cardiac arrest\n\n##### Adult\n- 1mg IV"


def test_normalise_markdown_syntax_repairs_malformed_bold_labels():
    content = "- **ICP: **1mMol/kg IV\n- ** With cardiac output:** 2.5g IV/IO"

    result = normalise_markdown_syntax(content)

    assert result == "- **ICP:** 1mMol/kg IV\n- **With cardiac output:** 2.5g IV/IO"


def test_normalise_markdown_syntax_separates_adjacent_bold_labels():
    content = "- **ICP:**** With cardiac output:**2.5g IV/IO"

    result = normalise_markdown_syntax(content)

    assert result == "- **ICP:** **With cardiac output:** 2.5g IV/IO"


def test_normalise_markdown_syntax_splits_same_line_headings():
    content = "#### Hyperkalaemia with cardiac output ##### Adult and Paediatric"

    result = normalise_markdown_syntax(content)

    assert result == "#### Hyperkalaemia with cardiac output\n\n##### Adult and Paediatric"


def test_normalise_markdown_syntax_splits_glued_list_items_and_bold_tokens():
    content = (
        "medications- **Non-rebreather mask (NRBM):**15 litres/min "
        "T**Tone:** uterine atonia"
    )

    result = normalise_markdown_syntax(content)

    assert result == (
        "medications\n- **Non-rebreather mask (NRBM):** 15 litres/min "
        "T **Tone:** uterine atonia"
    )


def test_normalise_markdown_payload_recurses_without_touching_valid_headings():
    payload = {
        "content": "#### Doses##### Adult",
        "items": ["Figure 1\n##### Nasal Prongs", {"text": "#### Uses##### Paediatric"}],
    }

    result = normalise_markdown_payload(payload)

    assert result["content"] == "#### Doses\n\n##### Adult"
    assert result["items"][0] == "Figure 1\n\n##### Nasal Prongs"
    assert result["items"][1]["text"] == "#### Uses\n\n##### Paediatric"


@pytest.mark.anyio
async def test_get_guideline_detail_normalises_broken_markdown(client: AsyncClient):
    guidelines_router.invalidate_guideline_cache()
    list_resp = await client.get("/guidelines", params={"type": "med"})
    med_items = list_resp.json()
    target = next((item for item in med_items if item["id"] == "CMG_03_Adrenaline"), None)

    if target is None:
        pytest.skip("Medication guideline CMG_03_Adrenaline not available")

    resp = await client.get(f"/guidelines/{target['id']}")

    assert resp.status_code == 200
    detail = resp.json()
    assert "#### Cardiac arrest##### Adult" not in detail["content_markdown"]
    assert "#### Cardiac arrest\n\n##### Adult" in detail["content_markdown"]
