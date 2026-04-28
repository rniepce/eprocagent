"""Enrich existing documents' metadata using gpt-5.5.

Reads the first chunks of each document already in the DB and asks the LLM
for `titulo`, `tipo`, `assunto_resumo` and `tags`. Preserves the existing
`secao` (derived from the folder structure during ingestion).

Usage:
    PYTHONPATH=. python -m src.ingestion.enrich_metadata
    PYTHONPATH=. python -m src.ingestion.enrich_metadata --only-empty
    PYTHONPATH=. python -m src.ingestion.enrich_metadata --limit 5
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
from typing import Any

from dotenv import load_dotenv

load_dotenv()

from src.backend.search import _llm_generate
from src.utils.db import close_pool, get_db_connection, init_pool, release_db_connection

logger = logging.getLogger("enrich_metadata")

PROMPT_TEMPLATE = """Analise os primeiros trechos do manual do eProc abaixo e extraia metadados.

Devolva APENAS um JSON válido (sem markdown, sem cercas) com este schema:
{{
  "titulo": "Título conciso do manual (até 80 caracteres)",
  "tipo": "Manual | FAQ | Tutorial | Guia | Orientação",
  "assunto_resumo": "Resumo de 1-2 frases (máximo 240 caracteres) do que o documento ensina",
  "tags": ["tag1", "tag2", "tag3"]
}}

REGRAS:
- `titulo`: pode ajustar o nome para ficar legível, mas mantenha referência ao tópico.
- `tipo`: escolha o que melhor descrever o conteúdo. Default = Manual.
- `assunto_resumo`: foque no QUE o leitor aprende, não em meta-informação.
- `tags`: 3 a 6 tags em minúsculas, sem hífen, em português, descrevendo conceitos-chave do conteúdo (ex: "intimação", "prazo processual", "perfil gerente"). Não repita o nome da seção.

Trechos do documento:
{content}"""


def parse_meta(raw: str) -> dict[str, Any]:
    text = raw.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
        text = text.strip()
    return json.loads(text)


async def fetch_documents(only_empty: bool, limit: int | None) -> list[dict]:
    conn = await get_db_connection()
    try:
        sql = "SELECT id, filename, titulo, tipo, secao, assunto_resumo, tags FROM documentos"
        if only_empty:
            sql += " WHERE assunto_resumo IS NULL OR assunto_resumo = ''"
        sql += " ORDER BY id"
        if limit:
            sql += f" LIMIT {int(limit)}"
        rows = await conn.fetch(sql)
        return [dict(r) for r in rows]
    finally:
        await release_db_connection(conn)


async def fetch_chunks_text(doc_id: int, max_chunks: int = 6) -> str:
    conn = await get_db_connection()
    try:
        rows = await conn.fetch(
            "SELECT conteudo_texto FROM chunks WHERE documento_id=$1 "
            "ORDER BY chunk_index ASC LIMIT $2",
            doc_id,
            max_chunks,
        )
        return "\n\n".join(r["conteudo_texto"] for r in rows)
    finally:
        await release_db_connection(conn)


async def update_metadata(
    doc_id: int,
    titulo: str,
    tipo: str,
    assunto_resumo: str,
    tags: list[str],
    keep_secao_tags: list[str],
) -> None:
    """Updates the document. Merges path-derived tags (secao folder) with new ones."""
    merged = list(dict.fromkeys([*keep_secao_tags, *tags]))[:8]
    conn = await get_db_connection()
    try:
        await conn.execute(
            """UPDATE documentos
               SET titulo=$2, tipo=$3, assunto_resumo=$4, tags=$5,
                   updated_at=NOW()
               WHERE id=$1""",
            doc_id,
            titulo[:200],
            tipo[:30],
            assunto_resumo[:500],
            merged,
        )
    finally:
        await release_db_connection(conn)


async def main_async(args: argparse.Namespace) -> int:
    await init_pool(min_size=1, max_size=4)
    docs = await fetch_documents(only_empty=args.only_empty, limit=args.limit or None)
    logger.info(f"Encontrados {len(docs)} documentos para enriquecer")

    counts = {"ok": 0, "skipped": 0, "failed": 0}
    try:
        for i, d in enumerate(docs, 1):
            try:
                content = await fetch_chunks_text(d["id"])
                if not content.strip():
                    counts["skipped"] += 1
                    logger.warning(f"[{i}/{len(docs)}] empty | {d['filename']}")
                    continue

                truncated = content[:6000]
                prompt = PROMPT_TEMPLATE.format(content=truncated)
                raw = _llm_generate(prompt, system_prompt=None)
                meta = parse_meta(raw)

                # Tags from path (secao) preserved as anchor
                keep = list(d.get("tags") or [])

                await update_metadata(
                    doc_id=d["id"],
                    titulo=meta.get("titulo") or d["titulo"] or d["filename"],
                    tipo=meta.get("tipo") or d.get("tipo") or "Manual",
                    assunto_resumo=meta.get("assunto_resumo", ""),
                    tags=meta.get("tags") or [],
                    keep_secao_tags=keep,
                )
                counts["ok"] += 1
                logger.info(
                    f"[{i}/{len(docs)}] ok | {d['filename'][:60]} | "
                    f"tipo={meta.get('tipo')!r} | tags={meta.get('tags')}"
                )
            except Exception as e:
                counts["failed"] += 1
                logger.error(f"[{i}/{len(docs)}] FAILED | {d['filename']} | {e}")
    finally:
        await close_pool()

    logger.info(f"DONE | ok={counts['ok']} skipped={counts['skipped']} failed={counts['failed']}")
    return 0 if counts["failed"] == 0 else 1


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Enriquece metadados dos documentos com gpt-5.5.")
    p.add_argument("--only-empty", action="store_true",
                   help="Processa apenas documentos sem assunto_resumo")
    p.add_argument("--limit", type=int, default=0,
                   help="Limita ao primeiro N (smoke test)")
    return p.parse_args()


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )
    args = parse_args()
    raise SystemExit(asyncio.run(main_async(args)))


if __name__ == "__main__":
    main()
