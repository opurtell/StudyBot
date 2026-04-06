from unittest.mock import MagicMock

from quiz.retriever import Retriever


def test_build_where_passes_in_filter_to_cmgs():
    mock_client = MagicMock()
    retriever = Retriever(client=mock_client)

    filters = {"section": {"$in": ["Cardiac", "Trauma"]}}
    where = retriever._build_where(filters, exclude=None, collection="cmgs")

    assert where == {
        "$and": [
            {"section": {"$in": ["Cardiac", "Trauma"]}},
            {"is_icp_only": False},
        ]
    }
