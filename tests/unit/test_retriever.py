"""Unit tests for the Qdrant retriever.

We do not touch a real Qdrant instance. A small fake client returns canned
hits so the search path and the grounding summary are both exercised. We
also confirm the function degrades cleanly when the backing client is
unavailable.
"""

from __future__ import annotations

from src.backend.knowledge import retriever


class _FakeHit:
    def __init__(self, payload, score):
        self.payload = payload
        self.score = score


class _FakeClient:
    def __init__(self, hits):
        self.hits = hits
        self.calls = []

    def search(self, collection_name, query_vector, limit):
        self.calls.append({"collection": collection_name, "limit": limit})
        return self.hits[:limit]


def test_top_k_passages_returns_payload():
    hits = [
        _FakeHit({"document_title": "FIA", "source_path": "/tmp/fia.pdf", "chunk_index": 1, "text": "stress increases steering"}, 0.91),
        _FakeHit({"document_title": "Neuroscience", "source_path": "/tmp/n.pdf", "chunk_index": 0, "text": "fatigue compresses HRV"}, 0.82),
    ]
    client = _FakeClient(hits)
    results = retriever.top_k_passages("driver fatigue", limit=2, client_factory=lambda: client)

    assert len(results) == 2
    assert results[0].document_title == "FIA"
    assert results[0].score > results[1].score
    assert client.calls[0]["limit"] == 2


def test_top_k_passages_returns_empty_when_client_raises():
    def _raise():
        raise RuntimeError("qdrant down")

    results = retriever.top_k_passages("anything", client_factory=_raise)
    assert results == []


def test_build_grounding_summary_skips_when_empty():
    assert retriever.build_grounding_summary([]) is None


def test_build_grounding_summary_truncates_long_passages():
    passage = retriever.RetrievedPassage(
        document_title="Long doc",
        source_path="/x.txt",
        chunk_index=0,
        text="A" * 500,
        score=0.5,
    )
    summary = retriever.build_grounding_summary([passage], char_budget=300)
    assert summary is not None
    assert "Long doc" in summary
    assert "..." in summary
