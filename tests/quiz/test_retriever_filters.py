from unittest.mock import MagicMock

from quiz.retriever import Retriever


def test_build_where_ap_uses_visibility_filter():
    mock_client = MagicMock()
    retriever = Retriever(client=mock_client, service_id="actas")

    filters = {"section": {"$in": ["Cardiac", "Trauma"]}}
    where = retriever._build_where(
        filters, exclude=None, collection="cmgs",
        effective_qualifications=frozenset({"AP"}),
    )

    assert where == {
        "$and": [
            {"section": {"$in": ["Cardiac", "Trauma"]}},
            {"visibility": {"$in": ["both", "ap"]}},
        ]
    }


def test_build_where_icp_uses_visibility_filter():
    mock_client = MagicMock()
    retriever = Retriever(client=mock_client, service_id="actas")

    where = retriever._build_where(
        None, exclude=None, collection="cmgs",
        effective_qualifications=frozenset({"AP", "ICP"}),
    )

    assert where == {"visibility": {"$in": ["both", "icp", "ap"]}}


def test_build_where_notes_ap_uses_visibility_filter():
    mock_client = MagicMock()
    retriever = Retriever(client=mock_client, service_id="actas")

    where = retriever._build_where(
        None, exclude=None, collection="notes",
        effective_qualifications=frozenset({"AP"}),
    )

    assert where == {"visibility": {"$in": ["both", "ap"]}}


def test_build_where_notes_icp_uses_visibility_filter():
    mock_client = MagicMock()
    retriever = Retriever(client=mock_client, service_id="actas")

    where = retriever._build_where(
        None, exclude=None, collection="notes",
        effective_qualifications=frozenset({"AP", "ICP"}),
    )

    assert where == {"visibility": {"$in": ["both", "icp", "ap"]}}
