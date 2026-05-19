"""Read path for the Qdrant motorsport ontology.

The compiler in `docling_compiler.py` writes vectors and payloads into the
`motorsport_ontology` collection. This module reads them back. The
explainability worker uses this retriever to ground Granite explanations in
real motorsport literature, so a reasoning paragraph can be checked against
the source passages that informed it.
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from typing import List, Optional

from src.backend.config import get_settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RetrievedPassage:
    document_title: str
    source_path: str
    chunk_index: int
    text: str
    score: float


def _embed_query(query: str) -> List[float]:
    """Embed a short query string into the same 768 dim space as the compiler.

    Uses sentence transformers when available and falls back to the same
    deterministic hashing embedder the compiler uses when the model is not
    installed. The embedder choice is logged so debugging is straightforward.
    """
    try:
        from sentence_transformers import SentenceTransformer

        model = SentenceTransformer("sentence-transformers/all-mpnet-base-v2")
        vector = model.encode([query], normalize_embeddings=True)
        return vector[0].tolist()
    except Exception as exc:
        logger.debug("Retriever using hashing embedder: %s", exc)
        digest = hashlib.sha512(query.encode("utf-8")).digest()
        values: List[float] = []
        while len(values) < 768:
            digest = hashlib.sha512(digest).digest()
            values.extend(b / 255.0 - 0.5 for b in digest)
        return values[:768]


def top_k_passages(
    query: str,
    limit: int = 3,
    collection: str = "motorsport_ontology",
    *,
    client_factory=None,
) -> List[RetrievedPassage]:
    """Return the top k passages by cosine similarity for the given query.

    The function gracefully degrades to an empty list if Qdrant is offline,
    if the collection is empty, or if the optional embedding library is not
    installed and the hashing fallback returns no relevant matches. Callers
    should treat the empty list as "no grounding available" rather than
    "system broken".
    """
    settings = get_settings()
    try:
        if client_factory is None:
            from qdrant_client import QdrantClient

            client = QdrantClient(host=settings.qdrant_host, port=settings.qdrant_port)
        else:
            client = client_factory()
    except Exception as exc:
        logger.info("Qdrant unavailable, retrieval skipped: %s", exc)
        return []

    vector = _embed_query(query)
    results = []
    try:
        # qdrant-client 1.7 used `search`, 1.10+ uses `query_points`. Try new
        # first, fall back to old. Both return objects with `.payload` and
        # `.score` so the downstream loop is identical.
        if hasattr(client, "query_points"):
            response = client.query_points(
                collection_name=collection,
                query=vector,
                limit=limit,
                with_payload=True,
            )
            results = getattr(response, "points", response) or []
        else:
            results = client.search(collection_name=collection, query_vector=vector, limit=limit)
    except Exception as exc:
        logger.debug("Qdrant retrieval skipped: %s", exc)
        return []

    passages: List[RetrievedPassage] = []
    for hit in results:
        payload = getattr(hit, "payload", None) or {}
        passages.append(
            RetrievedPassage(
                document_title=str(payload.get("document_title", "")),
                source_path=str(payload.get("source_path", "")),
                chunk_index=int(payload.get("chunk_index", 0) or 0),
                text=str(payload.get("text", "")),
                score=float(getattr(hit, "score", 0.0) or 0.0),
            )
        )
    return passages


def build_grounding_summary(passages: List[RetrievedPassage], char_budget: int = 600) -> Optional[str]:
    """Compose a short grounding summary that fits inside a prompt."""
    if not passages:
        return None
    bullets: List[str] = []
    budget = char_budget
    for passage in passages:
        snippet = passage.text.strip().replace("\n", " ")
        if len(snippet) > 220:
            snippet = snippet[:217].rstrip() + "..."
        line = f"- {passage.document_title}: {snippet}"
        if len(line) > budget:
            break
        bullets.append(line)
        budget -= len(line)
    if not bullets:
        return None
    return "Reference passages:\n" + "\n".join(bullets)
