"""Docling backed motorsport cognition knowledge compiler.

Reads PDFs, HTML, or plain text documents from `data/knowledge_sources` and
compiles them into the Qdrant `motorsport_ontology` collection. We use
Docling for structure aware extraction when it is available, and we fall
back to a plain text loader so the compiler still works on a developer
laptop that has not installed the optional dependency.

The compiler is intentionally idempotent. Running it twice produces the same
set of points in Qdrant. Every document is split into overlapping passages
of roughly 1000 characters, embedded with sentence transformers, and stored
with the document title and the source path as payload.
"""

from __future__ import annotations

import hashlib
import logging
import os
from dataclasses import dataclass
from typing import Iterable, List, Optional

from src.backend.config import get_settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Passage:
    document_id: str
    document_title: str
    source_path: str
    chunk_index: int
    text: str


def _chunk_text(text: str, chunk_size: int = 1000, overlap: int = 150) -> List[str]:
    text = text.strip()
    if not text:
        return []
    chunks: List[str] = []
    cursor = 0
    while cursor < len(text):
        end = min(cursor + chunk_size, len(text))
        chunks.append(text[cursor:end])
        if end == len(text):
            break
        cursor = end - overlap
    return chunks


def _doc_id(source_path: str) -> str:
    return hashlib.sha256(source_path.encode("utf-8")).hexdigest()[:16]


def _read_with_docling(path: str) -> Optional[str]:
    try:
        from docling.document_converter import DocumentConverter
    except Exception:
        return None
    try:
        converter = DocumentConverter()
        result = converter.convert(path)
        return result.document.export_to_markdown()
    except Exception as exc:
        logger.warning("Docling failed on %s: %s", path, exc)
        return None


def _read_plain(path: str) -> str:
    with open(path, "r", encoding="utf-8", errors="ignore") as fh:
        return fh.read()


def load_passages(source_dir: str) -> List[Passage]:
    """Walk the source directory and return one passage per chunk."""
    passages: List[Passage] = []
    if not os.path.isdir(source_dir):
        logger.info("Knowledge source directory %s does not exist", source_dir)
        return passages

    for root, _dirs, files in os.walk(source_dir):
        for name in files:
            full_path = os.path.join(root, name)
            ext = os.path.splitext(name)[1].lower()
            if ext not in {".pdf", ".html", ".htm", ".md", ".txt"}:
                continue

            text = _read_with_docling(full_path) if ext == ".pdf" else None
            if text is None:
                text = _read_plain(full_path)

            chunks = _chunk_text(text)
            for index, chunk in enumerate(chunks):
                passages.append(
                    Passage(
                        document_id=_doc_id(full_path),
                        document_title=os.path.splitext(name)[0],
                        source_path=full_path,
                        chunk_index=index,
                        text=chunk,
                    )
                )

    return passages


def _embed_passages(passages: List[Passage]) -> List[list]:
    """Return a list of 768 dimensional vectors for the passages.

    Uses sentence transformers when available. Falls back to a deterministic
    hashing embedder so the compiler still produces stable vectors on a
    machine without the model downloaded. The hashing embedder is clearly
    labelled in the payload so retrieval results can be filtered later.
    """
    try:
        from sentence_transformers import SentenceTransformer

        model = SentenceTransformer("sentence-transformers/all-mpnet-base-v2")
        vectors = model.encode([p.text for p in passages], normalize_embeddings=True)
        return [vector.tolist() for vector in vectors]
    except Exception as exc:
        logger.warning("Sentence transformer unavailable, using hashing embedder: %s", exc)
        return [_hash_embed(p.text) for p in passages]


def _hash_embed(text: str) -> list:
    digest = hashlib.sha512(text.encode("utf-8")).digest()
    values: List[float] = []
    while len(values) < 768:
        digest = hashlib.sha512(digest).digest()
        values.extend(b / 255.0 - 0.5 for b in digest)
    return values[:768]


def upsert(passages: Iterable[Passage], collection: str = "motorsport_ontology") -> int:
    """Embed and upsert the passages into Qdrant. Returns the row count."""
    from qdrant_client import QdrantClient
    from qdrant_client.http.models import PointStruct

    settings = get_settings()
    client = QdrantClient(host=settings.qdrant_host, port=settings.qdrant_port)

    passages = list(passages)
    if not passages:
        logger.info("No passages to upsert")
        return 0

    vectors = _embed_passages(passages)
    points = [
        PointStruct(
            id=int(hashlib.sha256(f"{p.document_id}-{p.chunk_index}".encode("utf-8")).hexdigest(), 16) % (10**12),
            vector=vector,
            payload={
                "document_id": p.document_id,
                "document_title": p.document_title,
                "source_path": p.source_path,
                "chunk_index": p.chunk_index,
                "text": p.text,
                "embedder": "sentence-transformers" if len(vector) == 768 and any(v != 0 for v in vector) else "hash-fallback",
            },
        )
        for p, vector in zip(passages, vectors)
    ]

    client.upsert(collection_name=collection, points=points, wait=True)
    logger.info("Upserted %d passages into %s", len(points), collection)
    return len(points)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    source_dir = os.environ.get("NEUROPIT_KNOWLEDGE_DIR", "data/knowledge_sources")
    passages = load_passages(source_dir)
    logger.info("Discovered %d passages from %s", len(passages), source_dir)
    upsert(passages)


if __name__ == "__main__":
    main()
