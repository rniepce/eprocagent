"""Batch ingestion CLI — extract, classify, chunk, embed and store all manuals.

Usage:
    PYTHONPATH=. python -m src.ingestion.batch_ingest --root manuais --skip-existing

Reuses the existing pipeline (extraction, chunking, Azure embeddings, storage)
to ingest every PDF/DOCX in a directory tree without going through the HTTP
upload endpoint.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from src.backend.search import _generate_embeddings_batch, _llm_generate
from src.ingestion.chunking import chunk_text
from src.ingestion.extraction import extract_text_from_doc_docx, extract_text_from_pdf
from src.ingestion.storage import DocumentStorage
from src.utils.db import close_pool, init_pool

logger = logging.getLogger("batch_ingest")

SUPPORTED_EXTS = {".pdf", ".docx", ".doc"}

CLASSIFY_PROMPT_TEMPLATE = """Analise o texto abaixo e extraia metadados em formato JSON:
{{
  "titulo": "string — título do documento",
  "tipo": "Manual|FAQ|Tutorial|Guia|Outro",
  "secao": "string — seção principal",
  "assunto_resumo": "Resumo conciso do conteúdo",
  "tags": ["tag1", "tag2", "tag3"]
}}

Texto (primeiros 5.000 caracteres):
<user_query>{snippet}</user_query>

Responda APENAS com JSON válido:"""


def _path_metadata(file_path: Path, root: Path, filename: str) -> dict:
    """Build a fallback metadata dict from the file path (subfolder = secao)."""
    try:
        rel = file_path.relative_to(root)
        parts = rel.parts[:-1]  # drop the filename itself
    except ValueError:
        parts = ()
    secao = parts[0] if parts else ""
    tags = list(parts) if parts else []
    return {
        "titulo": file_path.stem,
        "tipo": "Manual",
        "secao": secao,
        "assunto_resumo": "",
        "tags": tags,
    }


def _classify_with_llm(text: str, fallback: dict) -> dict:
    """Call gpt-5.5 to extract document metadata. Falls back to path-based dict on failure."""
    try:
        prompt = CLASSIFY_PROMPT_TEMPLATE.format(snippet=text[:5000])
        raw = _llm_generate(prompt, system_prompt=None)
        raw = raw.replace("```json", "").replace("```", "").strip()
        meta = json.loads(raw)
        # Merge: keep path tags so taxonomia das pastas é preservada
        meta_tags = meta.get("tags") or []
        merged_tags = list(dict.fromkeys([*meta_tags, *fallback["tags"]]))
        meta["tags"] = merged_tags
        if not meta.get("secao"):
            meta["secao"] = fallback["secao"]
        if not meta.get("titulo"):
            meta["titulo"] = fallback["titulo"]
        return meta
    except Exception as e:
        logger.warning(f"classify_failed | error={e} | usando metadata do path")
        return fallback


def _extract(file_path: Path) -> str | None:
    ext = file_path.suffix.lower()
    if ext == ".pdf":
        return extract_text_from_pdf(str(file_path))
    if ext in (".doc", ".docx"):
        return extract_text_from_doc_docx(str(file_path))
    return None


async def _process_file(
    file_path: Path,
    root: Path,
    storage: DocumentStorage,
    classify: bool,
    skip_existing: bool,
) -> tuple[str, int]:
    """Process one file. Returns (status, chunk_count). Status: ok|skipped|empty|failed."""
    filename = file_path.name
    if skip_existing and await storage.document_exists(filename):
        logger.info(f"skip_existing | {filename}")
        return ("skipped", 0)

    text = _extract(file_path)
    if not text or not text.strip():
        logger.warning(f"empty_extract | {filename}")
        return ("empty", 0)

    fallback_meta = _path_metadata(file_path, root, filename)
    metadata = _classify_with_llm(text, fallback_meta) if classify else fallback_meta

    chunks_text = chunk_text(text)
    if not chunks_text:
        logger.warning(f"empty_chunks | {filename}")
        return ("empty", 0)

    embeddings = _generate_embeddings_batch(chunks_text)
    chunks_data = [
        {"conteudo_texto": c, "embedding": e, "chunk_index": i}
        for i, (c, e) in enumerate(zip(chunks_text, embeddings))
    ]

    doc_id = await storage.save_document_and_chunks(
        filename=filename,
        metadata=metadata,
        chunks=chunks_data,
    )
    logger.info(
        f"ingest_ok | doc_id={doc_id} | {filename} | chunks={len(chunks_data)} "
        f"| secao={metadata.get('secao')!r}"
    )
    return ("ok", len(chunks_data))


async def main_async(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    if not root.is_dir():
        logger.error(f"root inválida: {root}")
        return 2

    files = sorted(
        p for p in root.rglob("*")
        if p.is_file() and p.suffix.lower() in SUPPORTED_EXTS and p.name != ".DS_Store"
    )
    if args.limit:
        files = files[: args.limit]

    logger.info(f"discovered {len(files)} files under {root}")

    await init_pool(min_size=1, max_size=4)
    storage = DocumentStorage()

    counts = {"ok": 0, "skipped": 0, "empty": 0, "failed": 0}
    total_chunks = 0
    started = time.monotonic()

    try:
        for idx, fp in enumerate(files, 1):
            logger.info(f"[{idx}/{len(files)}] {fp.relative_to(root)}")
            try:
                status, n_chunks = await _process_file(
                    fp,
                    root=root,
                    storage=storage,
                    classify=args.classify,
                    skip_existing=args.skip_existing,
                )
                counts[status] = counts.get(status, 0) + 1
                total_chunks += n_chunks
            except Exception as e:
                counts["failed"] += 1
                logger.error(f"failed | {fp.name} | {e}", exc_info=True)
    finally:
        await close_pool()

    elapsed = time.monotonic() - started
    logger.info(
        "DONE | "
        f"ok={counts['ok']} skipped={counts['skipped']} empty={counts['empty']} "
        f"failed={counts['failed']} | total_chunks={total_chunks} | elapsed={elapsed:.1f}s"
    )
    return 0 if counts["failed"] == 0 else 1


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Batch ingest manuals into the eProc RAG store.")
    p.add_argument("--root", default="manuais", help="Pasta base com os manuais (default: manuais)")
    p.add_argument("--skip-existing", action="store_true", help="Pula filenames já presentes em `documentos`")
    p.add_argument("--limit", type=int, default=0, help="Processa apenas os N primeiros arquivos (smoke test)")
    classify = p.add_mutually_exclusive_group()
    classify.add_argument("--classify", dest="classify", action="store_true", help="Classifica cada doc com gpt-5.5 (default)")
    classify.add_argument("--no-classify", dest="classify", action="store_false", help="Pula LLM, usa metadados do path")
    p.set_defaults(classify=True)
    return p.parse_args(argv)


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )
    args = parse_args()
    sys.exit(asyncio.run(main_async(args)))


if __name__ == "__main__":
    main()
