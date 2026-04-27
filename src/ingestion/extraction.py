"""Text extraction from PDF and DOCX files."""

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def extract_text_from_pdf(file_path: str) -> str | None:
    """Extract text from a PDF file using PyMuPDF."""
    try:
        import fitz  # PyMuPDF

        doc = fitz.open(file_path)
        pages_text = []
        for page_num, page in enumerate(doc, 1):
            text = page.get_text("text")
            if text.strip():
                pages_text.append(f"[Página {page_num}]\n{text}")

        doc.close()
        full_text = "\n\n".join(pages_text)
        logger.info(f"PDF extracted: {Path(file_path).name} | {len(pages_text)} pages | {len(full_text)} chars")
        return full_text if full_text.strip() else None

    except Exception as e:
        logger.error(f"PDF extraction failed for {file_path}: {e}")
        return None


def extract_text_from_doc_docx(file_path: str) -> str | None:
    """Extract text from a DOC/DOCX file using python-docx."""
    try:
        from docx import Document

        doc = Document(file_path)
        paragraphs = []
        for para in doc.paragraphs:
            text = para.text.strip()
            if text:
                paragraphs.append(text)

        full_text = "\n\n".join(paragraphs)
        logger.info(f"DOCX extracted: {Path(file_path).name} | {len(paragraphs)} paragraphs | {len(full_text)} chars")
        return full_text if full_text.strip() else None

    except Exception as e:
        logger.error(f"DOCX extraction failed for {file_path}: {e}")
        return None
