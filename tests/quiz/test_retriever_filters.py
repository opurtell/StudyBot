from unittest.mock import MagicMock

from quiz.retriever import Retriever


def test_build_where_ap_uses_visibility_filter():
    mock_client = MagicMock()
    retriever = Retriever(client=mock_client)

    filters = {"section": {"$in": ["Cardiac", "Trauma"]}}
    where = retriever._build_where(
        filters, exclude=None, collection="cmgs", skill_level="AP"
    )

    assert where == {
        "$and": [
            {"section": {"$in": ["Cardiac", "Trauma"]}},
            {"visibility": {"$in": ["both", "ap"]}},
        ]
    }


def test_build_where_icp_uses_visibility_filter():
    mock_client = MagicMock()
    retriever = Retriever(client=mock_client)

    where = retriever._build_where(
        None, exclude=None, collection="cmgs", skill_level="ICP"
    )

    assert where == {"visibility": {"$in": ["both", "icp"]}}


def test_build_where_notes_ap_uses_visibility_filter():
    mock_client = MagicMock()
    retriever = Retriever(client=mock_client)

    where = retriever._build_where(
        None, exclude=None, collection="notes", skill_level="AP"
    )

    assert where == {"visibility": {"$in": ["both", "ap"]}}


def test_build_where_notes_icp_uses_visibility_filter():
    mock_client = MagicMock()
    retriever = Retriever(client=mock_client)

    where = retriever._build_where(
        None, exclude=None, collection="notes", skill_level="ICP"
    )

    assert where == {"visibility": {"$in": ["both", "icp"]}}
