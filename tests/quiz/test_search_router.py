from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


class TestSearchEndpoint:
    def test_search_returns_results(self):
        mock_retriever = MagicMock()
        from quiz.models import RetrievedChunk

        mock_retriever.retrieve.return_value = [
            RetrievedChunk(
                content="Adrenaline 1mg IV for cardiac arrest.",
                source_type="cmg",
                source_file="cmg_4.json",
                source_rank=0,
                category="Cardiac",
                cmg_number="4",
                chunk_type="protocol",
                relevance_score=-0.1,
            )
        ]

        with patch("search.router._get_retriever", return_value=mock_retriever):
            response = client.get("/search?q=adrenaline+cardiac+arrest")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["content"] == "Adrenaline 1mg IV for cardiac arrest."
        assert data[0]["source_type"] == "cmg"
        assert data[0]["cmg_number"] == "4"

    def test_search_empty_query_returns_400(self):
        response = client.get("/search?q=")
        assert response.status_code == 400

    def test_search_missing_query_returns_400(self):
        response = client.get("/search")
        assert response.status_code == 400
