"""Pydantic models for API request/response schemas."""

from pydantic import BaseModel, Field
from typing import Optional


class ChatRequest(BaseModel):
    """Request body for the chat endpoint."""
    query: str = Field(..., min_length=1, max_length=2000, description="User's question")
    session_id: Optional[str] = Field(None, description="Conversation session ID")
    use_hybrid_search: bool = Field(True, description="Enable hybrid vector + keyword search")
    use_reranking: bool = Field(True, description="Enable LLM-based result reranking")
    top_k: int = Field(5, ge=1, le=20, description="Number of results to return")


class SourceItem(BaseModel):
    """A single source document chunk returned with the answer."""
    document_id: int
    filename: str
    titulo: Optional[str] = None
    tipo: str = "Manual"
    secao: Optional[str] = None
    chunk_text: str
    score: float = 0.0
    pagina: Optional[int] = None


class ChatResponse(BaseModel):
    """Response body for the chat endpoint."""
    answer: str
    sources: list[SourceItem] = []
    session_id: Optional[str] = None


class DocumentInfo(BaseModel):
    """Info about an ingested document."""
    id: int
    filename: str
    titulo: Optional[str] = None
    tipo: str
    total_chunks: int
    assunto_resumo: Optional[str] = None
    tags: list[str] = []


class UploadResponse(BaseModel):
    """Response body for the upload endpoint."""
    status: str
    filename: str
    metadata: dict
    chunks_created: int


class HealthResponse(BaseModel):
    """Response body for the health check endpoint."""
    status: str
    db_connected: bool = False
    llm_provider: Optional[str] = None
