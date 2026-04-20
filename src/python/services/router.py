from fastapi import APIRouter
from services.registry import REGISTRY


router = APIRouter(prefix="/services", tags=["services"])


@router.get("")
def list_services() -> list[dict]:
    """
    List all available services with their qualifications and metadata.

    Backend-only fields (adapter, scope_source_doc, category_mapping_doc, source_hierarchy)
    are stripped from the response.
    """
    out = []
    for s in REGISTRY:
        out.append({
            "id": s.id,
            "display_name": s.display_name,
            "region": s.region,
            "accent_colour": s.accent_colour,
            "source_url": s.source_url,
            "qualifications": {
                "bases": [
                    {
                        "id": b.id,
                        "display": b.display,
                        "implies": list(b.implies),
                    }
                    for b in s.qualifications.bases
                ],
                "endorsements": [
                    {
                        "id": e.id,
                        "display": e.display,
                        "requires_base": list(e.requires_base),
                    }
                    for e in s.qualifications.endorsements
                ],
            },
        })
    return out
