import pytest

from src.python.services.registry import get_service
from src.python.services.qualifications import effective_qualifications, is_in_scope

ACTAS = get_service("actas")
AT = get_service("at")


def test_actas_ap_does_not_include_icp():
    eff = effective_qualifications("AP", (), ACTAS)
    assert eff == frozenset({"AP"})


def test_actas_icp_implies_ap():
    eff = effective_qualifications("ICP", (), ACTAS)
    assert eff == frozenset({"AP", "ICP"})


def test_at_paramedic_plus_icp_endorsement():
    eff = effective_qualifications("PARAMEDIC", ("ICP",), AT)
    assert eff == frozenset({"PARAMEDIC", "ICP"})


def test_at_vao_does_not_roll_up():
    eff = effective_qualifications("VAO", (), AT)
    assert eff == frozenset({"VAO"})


def test_empty_required_always_in_scope():
    assert is_in_scope(frozenset(), frozenset({"AP"}))


def test_required_subset_of_effective_is_in_scope():
    assert is_in_scope(frozenset({"AP"}), frozenset({"AP", "ICP"}))


def test_required_not_subset_is_out_of_scope():
    assert not is_in_scope(frozenset({"ICP"}), frozenset({"AP"}))


def test_endorsement_requires_valid_base():
    with pytest.raises(ValueError):
        effective_qualifications("VAO", ("ICP",), AT)  # ICP endorsement requires PARAMEDIC
