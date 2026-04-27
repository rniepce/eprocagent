"""Text chunking with legal/judicial document separators."""

import logging
from langchain_text_splitters import RecursiveCharacterTextSplitter

logger = logging.getLogger(__name__)

# Legal/judicial document separators (ordered by priority)
LEGAL_SEPARATORS = [
    "\nCAPÍTULO",
    "\nSeção",
    "\nSubseção",
    "\nArt.",
    "\nParágrafo",
    "\n§",
    "\n\n",
    "\n",
    ". ",
    " ",
]


def chunk_text(
    text: str,
    chunk_size: int = 1000,
    chunk_overlap: int = 200,
    separators: list[str] | None = None,
) -> list[str]:
    """Split text into chunks using legal-aware separators.

    Args:
        text: Full document text.
        chunk_size: Maximum chunk size in characters.
        chunk_overlap: Overlap between chunks.
        separators: Custom separators (defaults to LEGAL_SEPARATORS).

    Returns:
        List of text chunks.
    """
    if not text or not text.strip():
        return []

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=separators or LEGAL_SEPARATORS,
        length_function=len,
    )

    chunks = splitter.split_text(text)
    logger.info(f"Text chunked: {len(text)} chars -> {len(chunks)} chunks (size={chunk_size}, overlap={chunk_overlap})")
    return chunks
