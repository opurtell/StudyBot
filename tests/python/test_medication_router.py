from __future__ import annotations

import json

from medication import router as medication_router


def test_medication_index_payload_is_normalised(tmp_path, monkeypatch):
    index_path = tmp_path / "medications-index.json"
    index_path.write_text(
        json.dumps(
            {
                "items": [
                    {
                        "name": "Adrenaline",
                        "indication": "Cardiac arrest",
                        "contraindications": "See clinical management guideline",
                        "adverse_effects": "See clinical management guideline",
                        "precautions": "See clinical management guideline",
                        "dose": "#### Cardiac arrest##### Adult\n- **ICP:**** With cardiac output:**2mg IV",
                        "cmg_reference": "CMG 03",
                        "is_icp_only": False,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    medication_router.invalidate_medication_cache()
    monkeypatch.setattr(medication_router, "_resolve_medication_index_path", lambda: index_path)

    items = medication_router.get_doses()

    assert items[0]["dose"] == (
        "#### Cardiac arrest\n\n##### Adult\n- **ICP:** **With cardiac output:** 2mg IV"
    )
