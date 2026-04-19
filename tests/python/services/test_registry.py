from src.python.services.registry import REGISTRY, get_service


def test_actas_registered():
    svc = get_service("actas")
    assert svc.id == "actas"
    assert svc.display_name.startswith("ACT")
    assert any(b.id == "AP" for b in svc.qualifications.bases)
    assert any(b.id == "ICP" for b in svc.qualifications.bases)


def test_at_registered():
    svc = get_service("at")
    assert svc.id == "at"
    assert any(b.id == "PARAMEDIC" for b in svc.qualifications.bases)
    assert any(b.id == "VAO" for b in svc.qualifications.bases)
    endorsement_ids = {e.id for e in svc.qualifications.endorsements}
    assert {"ICP", "PACER", "CP_ECP"} <= endorsement_ids


def test_unknown_service_raises():
    import pytest
    with pytest.raises(KeyError):
        get_service("nswa")
