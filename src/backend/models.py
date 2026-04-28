"""Pydantic models for API request/response schemas."""

from pydantic import BaseModel, Field
from typing import Optional, Union


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


class Conceito(BaseModel):
    termo: str
    definicao: str


class Passo(BaseModel):
    titulo: str
    descricao: str


class AnswerStructured(BaseModel):
    """Structured payload for a regular answer (Fase 1)."""
    mode: str = "answer"
    tldr: str = Field(..., description="Resposta direta em 1-2 frases")
    conceitos: list[Conceito] = []
    passos: list[Passo] = []
    atencao: list[str] = []
    followups: list[str] = Field(default_factory=list, description="2-3 perguntas para aprofundar")


class DisambiguationOption(BaseModel):
    label: str = Field(..., description="Texto curto da opção (1-3 palavras)")
    icon: Optional[str] = Field(None, description="Emoji opcional para ilustrar a opção")
    query: str = Field(..., description="Pergunta literal a ser enviada se o usuário escolher")
    hint: Optional[str] = Field(None, description="Frase curta explicando o que essa opção cobre")


class DisambiguationStructured(BaseModel):
    """Structured payload when the user query is ambiguous (Fase 3)."""
    mode: str = "disambiguation"
    pergunta: str = Field(..., description="Pergunta-guia exibida ao usuário, ex: 'Você quer configurar:'")
    opcoes: list[DisambiguationOption] = Field(..., min_length=2, max_length=6)


ChatStructured = Union[AnswerStructured, DisambiguationStructured]


class ChatResponse(BaseModel):
    """Response body for the chat endpoint."""
    answer: str
    structured: Optional[ChatStructured] = None
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
