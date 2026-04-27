"""RAG Search Engine — Query rewriting, hybrid search, LLM reranking, answer generation."""

import logging
import os
from typing import List

from openai import AzureOpenAI
from src.utils.db import get_db_connection, release_db_connection
from src.backend.models import ChatRequest, SourceItem

logger = logging.getLogger(__name__)

# ── Azure OpenAI Configuration ──────────────────────────────────
AZURE_API_KEY = os.getenv("AZURE_API_KEY")
AZURE_ENDPOINT = os.getenv("AZURE_ENDPOINT", "https://assistente-web-resource.cognitiveservices.azure.com/")
AZURE_API_VERSION = os.getenv("AZURE_API_VERSION", "2024-12-01-preview")
AZURE_LLM_MODEL = os.getenv("AZURE_LLM_MODEL", "gpt-5.5")
AZURE_EMBEDDING_MODEL = os.getenv("AZURE_EMBEDDING_MODEL", "text-embedding-3-large")
AZURE_EMBEDDING_DIMENSIONS = int(os.getenv("AZURE_EMBEDDING_DIMENSIONS", "3072"))

# Cached client
_AZURE_CLIENT: AzureOpenAI | None = None


def get_azure_client() -> AzureOpenAI | None:
    """Initialize and cache the Azure OpenAI client."""
    global _AZURE_CLIENT
    if _AZURE_CLIENT is None:
        if not AZURE_API_KEY:
            logger.warning("AZURE_API_KEY not set — Azure OpenAI disabled")
            return None
        try:
            _AZURE_CLIENT = AzureOpenAI(
                api_key=AZURE_API_KEY,
                azure_endpoint=AZURE_ENDPOINT,
                api_version=AZURE_API_VERSION,
            )
            logger.info(f"Azure OpenAI client initialized (LLM: {AZURE_LLM_MODEL}, Embeddings: {AZURE_EMBEDDING_MODEL})")
        except Exception as e:
            logger.error(f"Failed to initialize Azure OpenAI client: {e}")
    return _AZURE_CLIENT


def get_active_llm_info() -> dict:
    """Return info about the currently active LLM provider and model."""
    if get_azure_client() is not None:
        return {
            "provider": "azure",
            "model": AZURE_LLM_MODEL,
            "label": f"{AZURE_LLM_MODEL} (Azure AI)",
        }
    return {"provider": "none", "model": "none", "label": "Nenhum LLM configurado"}


# ── System Prompt ────────────────────────────────────────────────

SYSTEM_PROMPT = """Você é o eProc Agent, um assistente inteligente especializado no sistema judicial eletrônico eProc.

Sua função é ajudar usuários (advogados, servidores, magistrados e partes) a utilizarem o sistema eProc de forma eficiente.

INSTRUÇÕES:
1. Responda SEMPRE com base nos documentos/manuais fornecidos no contexto
2. Forneça instruções PASSO-A-PASSO quando o usuário perguntar "como fazer" algo
3. Use formatação Markdown para melhor legibilidade (negritos, listas numeradas, títulos)
4. Cite a seção/página do manual quando possível
5. Se a informação não estiver nos documentos fornecidos, diga claramente e sugira termos de busca alternativos
6. Responda em português brasileiro, de forma clara e acessível
7. Priorize instruções práticas sobre explicações teóricas
8. Para procedimentos, use listas numeradas com cada passo claramente descrito
9. Quando relevante, mencione avisos ou cuidados importantes com ⚠️"""


def _llm_generate(prompt: str, system_prompt: str = None) -> str:
    """Generate text using Azure OpenAI (GPT-5.5)."""
    client = get_azure_client()
    if client is None:
        raise RuntimeError("Azure OpenAI client not configured (missing AZURE_API_KEY)")

    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    response = client.chat.completions.create(
        model=AZURE_LLM_MODEL,
        messages=messages,
        max_completion_tokens=2048,
        temperature=0.3,
    )
    return response.choices[0].message.content.strip()


def _generate_embedding(text: str) -> list[float]:
    """Generate embedding vector for a single text."""
    client = get_azure_client()
    if client is None:
        raise RuntimeError("Azure OpenAI client not configured (missing AZURE_API_KEY)")

    response = client.embeddings.create(
        input=[text],
        model=AZURE_EMBEDDING_MODEL,
        dimensions=AZURE_EMBEDDING_DIMENSIONS,
    )
    return response.data[0].embedding


def _generate_embeddings_batch(texts: list[str]) -> list[list[float]]:
    """Generate embeddings for a batch of texts (max 100 per call)."""
    client = get_azure_client()
    if client is None:
        raise RuntimeError("Azure OpenAI client not configured (missing AZURE_API_KEY)")

    all_embeddings = []
    for i in range(0, len(texts), 100):
        batch = texts[i:i + 100]
        response = client.embeddings.create(
            input=batch,
            model=AZURE_EMBEDDING_MODEL,
            dimensions=AZURE_EMBEDDING_DIMENSIONS,
        )
        all_embeddings.extend([d.embedding for d in response.data])

    return all_embeddings


class SearchService:
    """RAG search service with query rewriting, hybrid search, and LLM reranking."""

    def rewrite_query(self, original_query: str) -> str:
        """Rewrite query with eProc domain vocabulary for better vector search."""
        try:
            prompt = f"""Você receberá uma pergunta de um usuário do sistema judicial eProc.

Sua tarefa é EXPANDIR e REFORMULAR a query para maximizar os resultados de busca vetorial na base de manuais do eProc.

REGRAS:
1. Mantenha a intenção original da pergunta
2. Adicione sinônimos e termos técnicos do eProc que ampliem a busca
3. Expanda siglas comuns (ex: "OAB" → "OAB Ordem dos Advogados do Brasil")
4. Inclua termos correlatos do sistema eProc
5. NÃO adicione explicações — responda APENAS com a query expandida
6. A query expandida deve ter entre 15 e 50 palavras

EXEMPLOS:
- "como peticionar" → "peticionar petição inicial eProc sistema judicial protocolar documento processo eletrônico ajuizar ação distribuição"
- "prazo" → "prazo processual contagem prazo recursal intimação citação eProc calendário dias úteis"
- "certificado digital" → "certificado digital token A3 A1 ICP-Brasil assinatura eletrônica login autenticação eProc acesso sistema"
- "consulta processo" → "consulta processo pesquisa número processo partes advogado eProc acompanhamento movimentação"

Query original:
<user_query>{original_query}</user_query>

Query expandida:"""
            rewritten = _llm_generate(prompt, system_prompt=None)
            logger.info(f"Query rewritten: '{original_query}' -> '{rewritten[:100]}...'")
            return rewritten
        except Exception as e:
            logger.warning(f"Query rewrite failed: {e}")
            return original_query.strip()

    def _rerank_with_llm(self, query: str, results: List[SourceItem]) -> List[SourceItem]:
        """Use LLM to rerank results by relevance to the query."""
        if len(results) <= 3:
            return results

        try:
            docs_text = ""
            for i, item in enumerate(results):
                docs_text += f"\n[{i}] {item.tipo} — {item.filename}\n{item.chunk_text[:300]}...\n"

            prompt = f"""Analise a relevância dos seguintes trechos de manuais do eProc para a pergunta do usuário.
Retorne APENAS os números dos documentos mais relevantes, ordenados do mais ao menos relevante, separados por vírgula.
Considere: (1) relevância semântica direta, (2) utilidade prática para o usuário, (3) especificidade.

PERGUNTA:
<user_query>{query}</user_query>

DOCUMENTOS:
{docs_text}

ORDEM DE RELEVÂNCIA (números separados por vírgula):"""

            order_text = _llm_generate(prompt, system_prompt=None)

            order = []
            for num in order_text.replace(" ", "").split(","):
                try:
                    idx = int(num.strip("[]"))
                    if 0 <= idx < len(results):
                        order.append(idx)
                except ValueError:
                    continue

            if order:
                reranked = [results[i] for i in order if i < len(results)]
                remaining = [r for i, r in enumerate(results) if i not in order]
                reranked.extend(remaining)
                logger.info(f"Reranked {len(results)} results")
                return reranked

        except Exception as e:
            logger.warning(f"Reranking failed: {e}")

        return results

    async def search(self, request: ChatRequest) -> List[SourceItem]:
        """Execute hybrid search: vector similarity + keyword matching."""
        conn = await get_db_connection()
        try:
            # 1. Rewrite query for better retrieval
            rewritten_query = self.rewrite_query(request.query)

            # 2. Generate embedding for the rewritten query
            embedding = _generate_embedding(rewritten_query)
            embedding_str = str(embedding)

            # 3. Build hybrid search query
            params = [embedding_str]

            if request.use_hybrid_search:
                params.append(rewritten_query)

                query_sql = """
                    WITH vector_search AS (
                        SELECT
                            c.id,
                            c.documento_id,
                            d.filename,
                            d.titulo,
                            d.tipo,
                            d.secao AS doc_secao,
                            c.conteudo_texto,
                            c.pagina,
                            c.secao AS chunk_secao,
                            1 - (c.embedding <=> $1::vector) as vector_score
                        FROM chunks c
                        JOIN documentos d ON c.documento_id = d.id
                        WHERE 1 - (c.embedding <=> $1::vector) > 0.20
                        ORDER BY c.embedding <=> $1::vector ASC
                        LIMIT 30
                    ),
                    keyword_search AS (
                        SELECT
                            c.id,
                            ts_rank_cd(
                                to_tsvector('portuguese', c.conteudo_texto),
                                plainto_tsquery('portuguese', $2)
                            ) as keyword_score
                        FROM chunks c
                        WHERE to_tsvector('portuguese', c.conteudo_texto)
                              @@ plainto_tsquery('portuguese', $2)
                    )
                    SELECT
                        v.*,
                        COALESCE(k.keyword_score, 0) as keyword_score,
                        (0.7 * v.vector_score + 0.3 * COALESCE(k.keyword_score, 0)) as combined_score
                    FROM vector_search v
                    LEFT JOIN keyword_search k ON v.id = k.id
                    ORDER BY combined_score DESC
                    LIMIT 20
                """
            else:
                query_sql = """
                    SELECT
                        c.documento_id,
                        d.filename,
                        d.titulo,
                        d.tipo,
                        d.secao AS doc_secao,
                        c.conteudo_texto,
                        c.pagina,
                        c.secao AS chunk_secao,
                        (1 - (c.embedding <=> $1::vector)) as combined_score
                    FROM chunks c
                    JOIN documentos d ON c.documento_id = d.id
                    WHERE 1 - (c.embedding <=> $1::vector) > 0.20
                    ORDER BY combined_score DESC
                    LIMIT 20
                """

            rows = await conn.fetch(query_sql, *params)

            results = []
            for row in rows:
                results.append(SourceItem(
                    document_id=row["documento_id"],
                    filename=row["filename"],
                    titulo=row.get("titulo"),
                    tipo=row.get("tipo", "Manual"),
                    secao=row.get("chunk_secao") or row.get("doc_secao"),
                    chunk_text=row["conteudo_texto"],
                    score=float(row["combined_score"]),
                    pagina=row.get("pagina"),
                ))

            # 4. Rerank with LLM if enabled
            if request.use_reranking and len(results) > 3:
                results = self._rerank_with_llm(request.query, results)

            return results[:request.top_k]

        finally:
            await release_db_connection(conn)

    async def generate_answer(self, query: str, context: List[SourceItem]) -> str:
        """Generate answer using Azure OpenAI (GPT-5.5) with RAG context."""
        if not context:
            return "Não encontrei informações relevantes nos manuais do eProc para sua pergunta. Tente reformular usando termos mais específicos."

        context_text = ""
        for i, item in enumerate(context, 1):
            location = ""
            if item.pagina:
                location += f" | Página {item.pagina}"
            if item.secao:
                location += f" | Seção: {item.secao}"

            context_text += f"\n--- Documento {i}: {item.filename}{location} ---\n"
            context_text += f"{item.chunk_text}\n"

        try:
            prompt = f"""Com base EXCLUSIVAMENTE nos documentos/manuais do eProc abaixo, responda à pergunta do usuário.

DOCUMENTOS ENCONTRADOS:
{context_text}

PERGUNTA DO USUÁRIO:
<user_query>{query}</user_query>

INSTRUÇÕES PARA A RESPOSTA:
1. Se a pergunta é sobre "como fazer" algo, forneça um PASSO-A-PASSO numerado e detalhado
2. Cite o documento fonte quando possível (ex: "Conforme o Manual do Usuário, página X...")
3. Use formatação Markdown: **negritos** para termos importantes, listas numeradas para procedimentos
4. Se encontrar avisos ou cuidados, destaque com ⚠️
5. Se a pergunta não puder ser respondida com os documentos, diga claramente
6. Responda em português brasileiro, de forma clara e acessível
7. Priorize informações práticas e acionáveis

RESPOSTA:"""

            answer = _llm_generate(prompt, system_prompt=SYSTEM_PROMPT)
            return answer

        except Exception as e:
            logger.error(f"LLM generation error: {e}", exc_info=True)
            return self._fallback_answer(query, context)

    def _fallback_answer(self, query: str, context: List[SourceItem]) -> str:
        """Fallback when LLM is unavailable — show raw chunks."""
        answer = f"**Resultados encontrados para:** '{query}'\n\n"
        answer += "_(LLM não disponível — exibindo trechos relevantes dos manuais)_\n\n"

        for i, item in enumerate(context, 1):
            answer += f"**{i}. {item.filename}** (Relevância: {item.score:.2f})\n"
            if item.secao:
                answer += f"📌 Seção: {item.secao}\n"
            answer += f"_{item.chunk_text[:400]}..._\n\n"

        return answer
