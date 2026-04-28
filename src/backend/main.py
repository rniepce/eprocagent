"""eProc Agent — FastAPI Backend Application."""

from dotenv import load_dotenv
load_dotenv()

from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, UploadFile, File, Request, Header, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from starlette.responses import JSONResponse, StreamingResponse

from src.backend.models import ChatRequest, ChatResponse, FeedbackRequest, UploadResponse
from src.backend.search import SearchService, get_active_llm_info, _llm_generate, _generate_embeddings_batch
from src.ingestion.extraction import extract_text_from_pdf, extract_text_from_doc_docx
from src.ingestion.chunking import chunk_text
from src.ingestion.storage import DocumentStorage
from src.utils.db import init_pool, close_pool

import logging
import os
import json
import tempfile
from pathlib import Path

# ── Structured Logging ───────────────────────────────────────────
LOG_FORMAT = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
logging.basicConfig(
    level=logging.INFO,
    format=LOG_FORMAT,
    datefmt="%Y-%m-%dT%H:%M:%S%z",
)
logger = logging.getLogger(__name__)

# ── Rate Limiting ────────────────────────────────────────────────
RATE_LIMIT = os.getenv("RATE_LIMIT", "30/minute")
limiter = Limiter(key_func=get_remote_address, default_limits=[RATE_LIMIT])

# ── Security Configuration ──────────────────────────────────────
UPLOAD_API_KEY = os.getenv("UPLOAD_API_KEY", "")
CORS_ORIGINS = [
    o.strip()
    for o in os.getenv("CORS_ORIGINS", "http://localhost:5173,http://localhost:8080").split(",")
]
MAX_UPLOAD_SIZE_MB = int(os.getenv("MAX_UPLOAD_SIZE_MB", "50"))


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: create DB pool. Shutdown: close it."""
    await init_pool(min_size=2, max_size=10)
    logger.info("DB connection pool initialized")
    yield
    await close_pool()
    logger.info("DB connection pool closed")


app = FastAPI(
    title="eProc Agent API",
    description="Assistente inteligente para o sistema judicial eProc",
    version="1.0.0",
    lifespan=lifespan,
)
app.state.limiter = limiter


# ── Error Handlers ───────────────────────────────────────────────

@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    client_ip = request.client.host if request.client else "unknown"
    logger.warning(f"Rate limit exceeded | ip={client_ip} | path={request.url.path}")
    return JSONResponse(
        status_code=429,
        content={"detail": "Muitas requisições. Tente novamente em breve."},
    )


# ── Middleware ───────────────────────────────────────────────────

app.add_middleware(SlowAPIMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "X-API-Key"],
)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    client_ip = request.client.host if request.client else "unknown"
    logger.info(f"request_start | ip={client_ip} | method={request.method} | path={request.url.path}")
    response = await call_next(request)
    logger.info(
        f"request_end | ip={client_ip} | method={request.method} "
        f"| path={request.url.path} | status={response.status_code}"
    )
    return response


# ── Service Instance ─────────────────────────────────────────────

search_service = SearchService()


# ── Auth Dependency ──────────────────────────────────────────────

async def verify_api_key(x_api_key: str = Header(None)):
    """Verify API key for protected endpoints. Skips if no key is configured."""
    if not UPLOAD_API_KEY:
        return  # No key configured — dev mode
    if x_api_key != UPLOAD_API_KEY:
        raise HTTPException(
            status_code=401,
            detail="Chave de API inválida ou ausente. Envie o header X-API-Key.",
        )


# ── API Endpoints ────────────────────────────────────────────────

@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok"}


@app.get("/api/model-info")
async def model_info():
    """Return the active LLM provider and model name."""
    return get_active_llm_info()


@app.post("/api/chat", response_model=ChatResponse)
@limiter.limit(RATE_LIMIT)
async def chat_endpoint(request: Request, body: ChatRequest):
    """Main chat endpoint — RAG search + LLM answer generation."""
    client_ip = request.client.host if request.client else "unknown"
    try:
        logger.info(f"chat_start | ip={client_ip} | query={body.query[:80]}")

        # 1. RAG Search
        results = await search_service.search(body)

        if not results:
            return ChatResponse(
                answer="Não encontrei informações relevantes nos manuais do eProc para sua pergunta. "
                       "Tente reformular usando termos mais específicos do sistema.",
                sources=[],
                session_id=body.session_id,
            )

        # 2. Generate Answer
        answer_md, structured = await search_service.generate_answer(
            body.query, results, language_mode=body.language_mode
        )

        logger.info(
            f"chat_success | ip={client_ip} | sources={len(results)} "
            f"| structured={'yes' if structured else 'no'}"
        )

        return ChatResponse(
            answer=answer_md,
            structured=structured,
            sources=results,
            session_id=body.session_id,
        )

    except Exception as e:
        logger.error(f"chat_error | ip={client_ip} | query={body.query[:80]} | error={e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Erro interno na busca. Tente novamente.")


@app.post("/api/chat/stream")
@limiter.limit(RATE_LIMIT)
async def chat_stream(request: Request, body: ChatRequest):
    """Streaming chat endpoint — emits SSE events as the pipeline progresses.

    Events:
      - status   {state: 'searching'|'thinking'}
      - sources  {sources: [...]}      # right after search, ~2s
      - answer   {answer, structured}  # after LLM finishes
      - done     {}
      - error    {detail}
    """
    client_ip = request.client.host if request.client else "unknown"
    logger.info(f"chat_stream_start | ip={client_ip} | query={body.query[:80]}")

    async def event_gen():
        def sse(event: str, payload: dict) -> str:
            return f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"

        try:
            yield sse("status", {"state": "searching"})

            results = await search_service.search(body)

            yield sse(
                "sources",
                {"sources": [r.model_dump() for r in results]},
            )

            if not results:
                empty_md = (
                    "Não encontrei informações relevantes nos manuais do eProc para sua pergunta. "
                    "Tente reformular usando termos mais específicos."
                )
                yield sse("answer", {"answer": empty_md, "structured": None})
                yield sse("done", {})
                return

            yield sse("status", {"state": "thinking"})

            answer_md, structured = await search_service.generate_answer(
                body.query, results, language_mode=body.language_mode
            )
            payload = {
                "answer": answer_md,
                "structured": structured.model_dump() if structured else None,
            }
            yield sse("answer", payload)
            yield sse("done", {})
            logger.info(
                f"chat_stream_success | ip={client_ip} | sources={len(results)} "
                f"| structured={'yes' if structured else 'no'}"
            )
        except Exception as e:
            logger.error(f"chat_stream_error | ip={client_ip} | error={e}", exc_info=True)
            yield sse("error", {"detail": "Erro interno na busca."})

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@app.post("/api/feedback")
@limiter.limit("60/minute")
async def submit_feedback(request: Request, body: FeedbackRequest):
    """Persist user 👍/👎 feedback on an assistant answer."""
    from src.utils.db import get_db_connection, release_db_connection

    if body.vote not in (-1, 1):
        raise HTTPException(status_code=400, detail="Voto inválido (use -1 ou 1).")

    conn = await get_db_connection()
    try:
        await conn.execute(
            """INSERT INTO feedback
                 (session_id, query, answer, structured, sources_doc_ids,
                  vote, comment, language_mode)
               VALUES ($1, $2, $3, $4::jsonb, $5, $6, $7, $8)""",
            body.session_id,
            body.query,
            body.answer,
            json.dumps(body.structured) if body.structured else None,
            body.sources_doc_ids or [],
            body.vote,
            body.comment,
            body.language_mode,
        )
        return {"status": "ok"}
    finally:
        await release_db_connection(conn)


@app.post("/api/upload", response_model=UploadResponse)
@limiter.limit("10/minute")
async def upload_document(
    request: Request,
    file: UploadFile = File(...),
    _auth=Depends(verify_api_key),
):
    """Upload and process a PDF/DOCX file for RAG ingestion."""
    client_ip = request.client.host if request.client else "unknown"
    logger.info(f"upload_start | ip={client_ip} | filename={file.filename}")

    allowed_ext = (".pdf", ".doc", ".docx")
    if not file.filename or not file.filename.lower().endswith(allowed_ext):
        raise HTTPException(
            status_code=400,
            detail=f"Formatos suportados: {', '.join(allowed_ext)}",
        )

    try:
        content = await file.read()

        # File size validation
        max_bytes = MAX_UPLOAD_SIZE_MB * 1024 * 1024
        if len(content) > max_bytes:
            raise HTTPException(
                status_code=400,
                detail=f"Arquivo excede o limite de {MAX_UPLOAD_SIZE_MB}MB.",
            )

        # MIME type validation via magic bytes
        ext = Path(file.filename).suffix.lower()
        magic_bytes = content[:8]
        is_pdf = magic_bytes[:4] == b"%PDF"
        is_docx = magic_bytes[:4] == b"PK\x03\x04"
        is_doc = magic_bytes[:8] == b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"
        if not (is_pdf or is_docx or is_doc):
            logger.warning(f"upload_rejected | ip={client_ip} | filename={file.filename}")
            raise HTTPException(
                status_code=400,
                detail="Tipo de arquivo inválido. Envie PDF, DOC ou DOCX.",
            )

        # Save to temp file
        suffix = os.path.splitext(file.filename)[1]
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(content)
            tmp_path = tmp.name

        try:
            # 1. Extract text
            lower_suffix = suffix.lower()
            if lower_suffix == ".pdf":
                text = extract_text_from_pdf(tmp_path)
            elif lower_suffix in (".doc", ".docx"):
                text = extract_text_from_doc_docx(tmp_path)
            else:
                text = None

            if not text:
                raise HTTPException(
                    status_code=400,
                    detail="Não foi possível extrair texto do arquivo.",
                )

            # 2. Classify document using LLM
            classify_prompt = f"""Analise o texto abaixo e extraia metadados em formato JSON:
{{
  "titulo": "string — título do documento",
  "tipo": "Manual|FAQ|Tutorial|Guia|Outro",
  "secao": "string — seção principal",
  "assunto_resumo": "Resumo conciso do conteúdo",
  "tags": ["tag1", "tag2", "tag3"]
}}

Texto (primeiros 5.000 caracteres):
<user_query>{text[:5000]}</user_query>

Responda APENAS com JSON válido:"""

            try:
                metadata_text = _llm_generate(classify_prompt, system_prompt=None)
                metadata_text = metadata_text.replace("```json", "").replace("```", "").strip()
                metadata = json.loads(metadata_text)
            except Exception as e:
                logger.warning(f"classification_failed | filename={file.filename} | error={e}")
                metadata = {
                    "titulo": file.filename,
                    "tipo": "Manual",
                    "secao": "",
                    "assunto_resumo": "Classificação pendente",
                    "tags": [],
                }

            # 3. Chunk text
            chunks_text = chunk_text(text)

            # 4. Generate embeddings
            embeddings = _generate_embeddings_batch(chunks_text)

            # 5. Store in database
            chunks_data = []
            for i, (chunk, emb) in enumerate(zip(chunks_text, embeddings)):
                chunks_data.append({
                    "conteudo_texto": chunk,
                    "embedding": emb,
                    "chunk_index": i,
                })

            storage = DocumentStorage()
            await storage.save_document_and_chunks(
                filename=file.filename,
                metadata=metadata,
                chunks=chunks_data,
            )

            logger.info(
                f"upload_success | ip={client_ip} | filename={file.filename} | chunks={len(chunks_data)}"
            )

            return UploadResponse(
                status="success",
                filename=file.filename,
                metadata=metadata,
                chunks_created=len(chunks_data),
            )

        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"upload_error | ip={client_ip} | filename={file.filename} | error={e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=500,
            detail="Erro interno ao processar o arquivo. Tente novamente.",
        )


@app.get("/api/documents")
async def list_documents():
    """List all ingested documents."""
    from src.utils.db import get_db_connection, release_db_connection

    conn = await get_db_connection()
    try:
        rows = await conn.fetch(
            """SELECT id, filename, titulo, tipo, secao, assunto_resumo, tags, total_chunks, created_at
               FROM documentos ORDER BY created_at DESC"""
        )
        return [
            {
                "id": row["id"],
                "filename": row["filename"],
                "titulo": row["titulo"],
                "tipo": row["tipo"],
                "secao": row["secao"],
                "assunto_resumo": row["assunto_resumo"],
                "tags": row["tags"] or [],
                "total_chunks": row["total_chunks"],
                "created_at": row["created_at"].isoformat() if row["created_at"] else None,
            }
            for row in rows
        ]
    finally:
        await release_db_connection(conn)


# ── Mount Frontend (Production) ──────────────────────────────────

frontend_dist_path = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "frontend",
    "dist",
)
if os.path.exists(frontend_dist_path):
    app.mount("/", StaticFiles(directory=frontend_dist_path, html=True), name="frontend")
else:
    logger.warning(
        f"Frontend dist folder not found at {frontend_dist_path}. "
        "Run 'npm run build' inside src/frontend."
    )


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
