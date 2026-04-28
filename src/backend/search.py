"""RAG Search Engine — Query rewriting, hybrid search, LLM reranking, answer generation."""

import json
import logging
import os
from typing import List, Optional

from openai import AzureOpenAI
from pydantic import ValidationError

from src.utils.db import get_db_connection, release_db_connection
from src.backend.models import (
    AnswerStructured,
    ChatRequest,
    ChatStructured,
    DisambiguationStructured,
    SourceItem,
)

logger = logging.getLogger(__name__)

# ── Azure OpenAI Configuration ──────────────────────────────────
AZURE_API_KEY = os.getenv("AZURE_API_KEY")
AZURE_ENDPOINT = os.getenv("AZURE_ENDPOINT", "https://assistente-web-resource.cognitiveservices.azure.com/")
AZURE_API_VERSION = os.getenv("AZURE_API_VERSION", "2024-12-01-preview")
AZURE_LLM_MODEL = os.getenv("AZURE_LLM_MODEL", "gpt-5.5")
AZURE_EMBEDDING_MODEL = os.getenv("AZURE_EMBEDDING_MODEL", "text-embedding-3-large-2")
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

SYSTEM_PROMPT_STRUCTURED = """Você é o eProc Agent, um assistente especializado no sistema judicial eletrônico eProc.

Você responde EXCLUSIVAMENTE em JSON válido. Existem DOIS modos possíveis. Escolha um:

▶ MODE = "answer" — quando a pergunta tem resposta clara nos documentos
{
  "mode": "answer",
  "tldr": "Resposta direta em 1-2 frases (obrigatório)",
  "conceitos": [{"termo": "...", "definicao": "..."}],
  "passos": [{"titulo": "Nome curto do passo", "descricao": "Detalhe com nomes de menus/botões em **negrito**"}],
  "atencao": ["Aviso 1", "Aviso 2"],
  "followups": ["Pergunta de aprofundamento 1", "Pergunta 2"]
}

▶ MODE = "disambiguation" — quando a pergunta é ampla/vaga e os documentos cobrem ≥3 tópicos distintos
{
  "mode": "disambiguation",
  "pergunta": "Frase-guia curta para o usuário, ex: 'O que você quer configurar?'",
  "opcoes": [
    {"label": "Curto (1-3 palavras)", "icon": "🔔", "query": "Pergunta literal a enviar se o usuário escolher", "hint": "Frase curta explicando essa opção"}
  ]
}

QUANDO USAR DISAMBIGUATION:
- A pergunta é genérica (ex: "como configurar?", "como uso o eproc?", "como acessar?", "preciso de ajuda")
- OU os documentos recuperados cobrem 3+ tópicos claramente distintos (ex: configuração de minutas + configuração de notificações + configuração de localizadores)
- OU a pergunta carece de contexto crítico (perfil do usuário, tipo de processo, etapa) que muda a resposta
- Sempre 3 a 5 opções. Cada `query` deve ser uma pergunta completa e específica.

QUANDO USAR ANSWER:
- A pergunta é específica e os documentos têm uma resposta direta
- Mesmo que ampla, se o top-1 documento responde claramente, vá com answer (mas use os followups para abrir os outros tópicos relacionados)
- Caso de dúvida, prefira answer + followups variados sobre disambiguation

REGRAS GERAIS:
- Use APENAS informações dos documentos/manuais fornecidos. Não invente.
- Português brasileiro, claro, acessível, sem floreio.
- NÃO inclua texto fora do JSON. NÃO use cercas. Apenas o objeto JSON cru.

REGRAS PARA MODE=ANSWER:
- `tldr`: sempre presente. Resposta acionável em 1-2 frases.
- `conceitos`: termos do eProc que merecem definição. Caso contrário, lista vazia.
- `passos`: APENAS quando é "como fazer". Use nomes literais de menus/botões com **negrito**.
- `atencao`: pré-requisitos, perfis necessários, armadilhas. Use ⚠️ se quiser destacar.
- `followups`: 2-3 perguntas curtas ancoradas nos chunks recuperados (não inventadas).
- Se a informação não está nos documentos: tldr="Não encontrei nos manuais do eProc.", listas vazias, followups com sugestões de reformulação.

EXEMPLO answer ("Como criar uma sala de audiência?"):
{"mode":"answer","tldr":"Acesse **Menu → Gerenciamento de Salas → Nova** e preencha o formulário. Apenas perfis de **Gerente de Secretaria** podem criar salas.","conceitos":[{"termo":"Sala de Audiência","definicao":"Cadastro necessário no eProc para permitir agendamento de audiências."}],"passos":[{"titulo":"Acessar o menu","descricao":"No **Menu**, busque por **Gerenciamento de Salas**."},{"titulo":"Criar nova sala","descricao":"Na tela **Sala de Audiência**, clique em **Nova**."},{"titulo":"Preencher cadastro","descricao":"Preencha a tela **Cadastrar nova sala de audiência do Órgão**."}],"atencao":["⚠️ Apenas **Gerente de Secretaria** pode criar salas."],"followups":["Como agendar audiência depois?","Como configurar Agenda Padrão da sala?"]}

EXEMPLO disambiguation ("Como configurar o eproc?"):
{"mode":"disambiguation","pergunta":"O que você quer configurar no eProc?","opcoes":[{"label":"Notificações","icon":"🔔","query":"Como configurar preferências de intimação no eProc?","hint":"Email, prazos e canal de aviso"},{"label":"Localizadores","icon":"📍","query":"Como configurar meus localizadores?","hint":"Etiquetas para organizar processos"},{"label":"Minutas","icon":"📝","query":"Como configurar preferências de minutas?","hint":"Modelo padrão, formatação"},{"label":"Aparência","icon":"🎨","query":"Como ajustar a aparência e acessibilidade do eProc?","hint":"Tema, contraste, fonte"}]}"""


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
        max_completion_tokens=16384,
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

    async def generate_answer(
        self, query: str, context: List[SourceItem]
    ) -> tuple[str, Optional[ChatStructured]]:
        """Generate structured answer (JSON) and a markdown rendering for fallback.

        Returns (markdown, structured). `structured` is None if JSON parsing fails;
        in that case `markdown` carries a usable response.
        """
        if not context:
            empty = AnswerStructured(
                tldr="Não encontrei informações relevantes nos manuais do eProc para essa pergunta.",
                followups=[
                    "Pode reformular a pergunta usando termos do eProc?",
                    "Quer ver a lista de tópicos cobertos pelos manuais?",
                ],
            )
            return _structured_to_markdown(empty), empty

        context_text = ""
        for i, item in enumerate(context, 1):
            location = ""
            if item.pagina:
                location += f" | Página {item.pagina}"
            if item.secao:
                location += f" | Seção: {item.secao}"
            context_text += f"\n--- Documento {i}: {item.filename}{location} ---\n"
            context_text += f"{item.chunk_text}\n"

        prompt = f"""DOCUMENTOS RECUPERADOS DOS MANUAIS DO EPROC:
{context_text}

PERGUNTA DO USUÁRIO:
<user_query>{query}</user_query>

Gere a resposta no formato JSON definido pelo system prompt. Apenas o objeto JSON, sem texto extra."""

        try:
            raw = _llm_generate(prompt, system_prompt=SYSTEM_PROMPT_STRUCTURED)
            structured = _parse_structured(raw)
            if structured is None:
                logger.warning("structured parse failed, returning markdown fallback")
                return raw, None
            return _structured_to_markdown(structured), structured
        except Exception as e:
            logger.error(f"LLM generation error: {e}", exc_info=True)
            return self._fallback_answer(query, context), None

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


# ── Structured response helpers ────────────────────────────────────

def _parse_structured(raw: str) -> Optional[ChatStructured]:
    """Parse LLM output into AnswerStructured or DisambiguationStructured."""
    if not raw:
        return None
    text = raw.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
        text = text.strip()
    try:
        data = json.loads(text)
        if not isinstance(data, dict):
            return None
        mode = data.get("mode", "answer")
        if mode == "disambiguation":
            return DisambiguationStructured.model_validate(data)
        data.setdefault("mode", "answer")
        return AnswerStructured.model_validate(data)
    except (json.JSONDecodeError, ValidationError) as e:
        logger.warning(f"structured parse error: {e}")
        return None


def _structured_to_markdown(s: ChatStructured) -> str:
    """Render structured payload as markdown for the legacy `answer` field."""
    if isinstance(s, DisambiguationStructured):
        out = [f"**{s.pergunta}**", ""]
        for o in s.opcoes:
            icon = f"{o.icon} " if o.icon else ""
            hint = f" — _{o.hint}_" if o.hint else ""
            out.append(f"- {icon}**{o.label}**{hint}")
        return "\n".join(out)

    out = [s.tldr.strip()]
    if s.conceitos:
        out.append("\n### Conceitos-chave")
        for c in s.conceitos:
            out.append(f"- **{c.termo}** — {c.definicao}")
    if s.passos:
        out.append("\n### Passo a passo")
        for i, p in enumerate(s.passos, 1):
            out.append(f"{i}. **{p.titulo}** — {p.descricao}")
    if s.atencao:
        out.append("\n### ⚠️ Atenção")
        for a in s.atencao:
            out.append(f"- {a}")
    if s.followups:
        out.append("\n### Quer ir mais fundo?")
        for f in s.followups:
            out.append(f"- {f}")
    return "\n".join(out)
