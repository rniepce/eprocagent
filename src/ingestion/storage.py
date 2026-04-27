"""Document and chunk storage in PostgreSQL."""

import logging
from src.utils.db import get_db_connection, release_db_connection

logger = logging.getLogger(__name__)


class DocumentStorage:
    """Handles persisting documents and their chunks to PostgreSQL."""

    async def document_exists(self, filename: str) -> bool:
        """Return True if a document with this filename is already ingested."""
        conn = await get_db_connection()
        try:
            row = await conn.fetchval(
                "SELECT 1 FROM documentos WHERE filename = $1 LIMIT 1",
                filename,
            )
            return row is not None
        finally:
            await release_db_connection(conn)

    async def save_document_and_chunks(
        self,
        filename: str,
        metadata: dict,
        chunks: list[dict],
    ) -> int:
        """Save a document and its embedded chunks to the database.

        Args:
            filename: Original filename.
            metadata: Document metadata (titulo, tipo, secao, assunto_resumo, tags).
            chunks: List of dicts with keys: conteudo_texto, embedding, chunk_index.

        Returns:
            The document ID.
        """
        conn = await get_db_connection()
        try:
            # Insert document record
            doc_id = await conn.fetchval(
                """INSERT INTO documentos (filename, titulo, tipo, secao, assunto_resumo, tags, total_chunks)
                   VALUES ($1, $2, $3, $4, $5, $6, $7)
                   RETURNING id""",
                filename,
                metadata.get("titulo", filename),
                metadata.get("tipo", "Manual"),
                metadata.get("secao", ""),
                metadata.get("assunto_resumo", ""),
                metadata.get("tags", []),
                len(chunks),
            )

            # Insert chunks with embeddings
            for chunk in chunks:
                embedding_str = str(chunk["embedding"])
                await conn.execute(
                    """INSERT INTO chunks (documento_id, conteudo_texto, chunk_index, embedding)
                       VALUES ($1, $2, $3, $4::vector)""",
                    doc_id,
                    chunk["conteudo_texto"],
                    chunk.get("chunk_index", 0),
                    embedding_str,
                )

            logger.info(f"Document saved: id={doc_id} | filename={filename} | chunks={len(chunks)}")
            return doc_id

        finally:
            await release_db_connection(conn)
