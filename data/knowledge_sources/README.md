# Knowledge Sources

This directory holds the source documents that Docling compiles into the `motorsport_ontology` collection in Qdrant. Drop a PDF, an HTML page, a Markdown file, or a plain text file in here and run `python -m src.backend.knowledge.docling_compiler` to ingest it.

The compiler is idempotent. Running it twice produces the same set of vectors. Each chunk carries the source path in its payload so retrieval results can be traced back to a real document.

Useful starting sources to add when they are available:

- FIA technical and sporting regulations PDFs.
- Driver fatigue and cognitive load studies from open access journals.
- Crash analysis reports from public archives.
- Race engineering manuals.
- Public driver interview transcripts.

Do not commit copyrighted material here. The repository ships with a small seed file so the compiler has something to chew on out of the box.
