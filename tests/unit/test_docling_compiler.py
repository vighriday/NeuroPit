"""Unit tests for the Docling backed knowledge compiler.

Focuses on the deterministic helpers that do not require Docling or
sentence-transformers to be installed. The Qdrant upsert path is covered in
the integration tests because it needs a running Qdrant instance.
"""

from __future__ import annotations

from src.backend.knowledge import docling_compiler


def test_chunk_text_handles_empty_input():
    assert docling_compiler._chunk_text("") == []


def test_chunk_text_respects_chunk_size_and_overlap():
    text = "a" * 2500
    chunks = docling_compiler._chunk_text(text, chunk_size=1000, overlap=150)
    assert len(chunks) >= 3
    assert all(len(chunk) <= 1000 for chunk in chunks)


def test_chunk_text_round_trips_short_input():
    text = "short paragraph"
    assert docling_compiler._chunk_text(text) == [text]


def test_doc_id_is_stable_for_same_path():
    a = docling_compiler._doc_id("/tmp/foo.pdf")
    b = docling_compiler._doc_id("/tmp/foo.pdf")
    assert a == b


def test_doc_id_changes_with_path():
    a = docling_compiler._doc_id("/tmp/foo.pdf")
    b = docling_compiler._doc_id("/tmp/bar.pdf")
    assert a != b


def test_hash_embed_returns_768_dimensional_vector():
    vector = docling_compiler._hash_embed("hello world")
    assert len(vector) == 768
    assert all(isinstance(v, float) for v in vector)


def test_hash_embed_is_deterministic():
    assert docling_compiler._hash_embed("driver stress") == docling_compiler._hash_embed("driver stress")


def test_load_passages_returns_empty_for_missing_dir(tmp_path):
    assert docling_compiler.load_passages(str(tmp_path / "does-not-exist")) == []


def test_load_passages_reads_plain_text(tmp_path):
    sample = tmp_path / "sample.md"
    sample.write_text("NeuroPit cognitive inference seed paragraph.", encoding="utf-8")
    passages = docling_compiler.load_passages(str(tmp_path))
    assert len(passages) == 1
    assert passages[0].document_title == "sample"
    assert "NeuroPit" in passages[0].text
