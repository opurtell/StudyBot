from fastapi.testclient import TestClient
from src.python.main import app


client = TestClient(app)


def test_list_services_includes_both():
    """GET /services returns both ACTAS and Ambulance Tasmania."""
    r = client.get("/services")
    assert r.status_code == 200
    ids = {s["id"] for s in r.json()}
    assert ids == {"actas", "at"}


def test_list_services_strips_all_backend_only_fields():
    """Response excludes backend-only fields: adapter, scope_source_doc, category_mapping_doc, source_hierarchy."""
    r = client.get("/services")
    assert r.status_code == 200
    backend_only = {"adapter", "scope_source_doc", "category_mapping_doc", "source_hierarchy"}
    for service in r.json():
        service_keys = set(service.keys())
        assert backend_only.isdisjoint(service_keys), (
            f"Service {service.get('id')} contains backend-only fields: "
            f"{backend_only & service_keys}"
        )


def test_list_services_includes_public_fields():
    """Response includes all public-facing fields."""
    r = client.get("/services")
    assert r.status_code == 200
    public_fields = {"id", "display_name", "region", "accent_colour", "source_url", "qualifications"}
    for service in r.json():
        service_keys = set(service.keys())
        assert public_fields.issubset(service_keys), (
            f"Service {service.get('id')} missing fields: {public_fields - service_keys}"
        )


def test_list_services_qualifications_structure():
    """Qualifications object contains 'bases' and 'endorsements' arrays with proper structure."""
    r = client.get("/services")
    assert r.status_code == 200
    for service in r.json():
        quals = service["qualifications"]
        assert "bases" in quals
        assert "endorsements" in quals
        assert isinstance(quals["bases"], list)
        assert isinstance(quals["endorsements"], list)

        # Each base must have id, display, implies
        for base in quals["bases"]:
            assert set(base.keys()) == {"id", "display", "implies"}
            assert isinstance(base["implies"], list)

        # Each endorsement must have id, display, requires_base
        for endorsement in quals["endorsements"]:
            assert set(endorsement.keys()) == {"id", "display", "requires_base"}
            assert isinstance(endorsement["requires_base"], list)


def test_list_services_actas_properties():
    """ACTAS service has correct properties."""
    r = client.get("/services")
    assert r.status_code == 200
    services = {s["id"]: s for s in r.json()}
    actas = services["actas"]

    assert actas["display_name"] == "ACT Ambulance Service"
    assert actas["region"] == "Australian Capital Territory"
    assert actas["accent_colour"] == "#2D5A54"
    assert actas["source_url"] == "https://cmg.ambulance.act.gov.au"

    # ACTAS has AP and ICP bases
    base_ids = {b["id"] for b in actas["qualifications"]["bases"]}
    assert base_ids == {"AP", "ICP"}


def test_list_services_at_properties():
    """Ambulance Tasmania service has correct properties."""
    r = client.get("/services")
    assert r.status_code == 200
    services = {s["id"]: s for s in r.json()}
    at = services["at"]

    assert at["display_name"] == "Ambulance Tasmania"
    assert at["region"] == "Tasmania"
    assert at["accent_colour"] == "#005a96"
    assert at["source_url"] == "https://cpg.ambulance.tas.gov.au"

    # AT has VAO and PARAMEDIC bases
    base_ids = {b["id"] for b in at["qualifications"]["bases"]}
    assert base_ids == {"VAO", "PARAMEDIC"}

    # AT has endorsements
    endorsement_ids = {e["id"] for e in at["qualifications"]["endorsements"]}
    assert "ICP" in endorsement_ids
