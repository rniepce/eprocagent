# eProc Agent — Assistente Judicial Inteligente

Aplicativo web com chatbot RAG que auxilia usuários do sistema judicial eProc, respondendo dúvidas e fornecendo guias passo-a-passo com base nos manuais vetorizados.

## Stack

| Componente | Tecnologia |
|---|---|
| Frontend | React + TypeScript + Vite |
| Backend | FastAPI (Python) |
| LLM | OpenAI (GPT) |
| Embeddings | OpenAI text-embedding-3-large |
| Vector DB | PostgreSQL + pgvector |
| Deploy | Docker → Railway |

## Setup Local

### 1. Pré-requisitos
- Docker e Docker Compose
- Python 3.11+
- Node.js 20+

### 2. Configurar variáveis de ambiente
```bash
cp .env.example .env
# Edite .env com sua OPENAI_API_KEY
```

### 3. Iniciar PostgreSQL
```bash
docker-compose up -d
```

### 4. Instalar dependências Python
```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 5. Iniciar o Backend
```bash
PYTHONPATH=. uvicorn src.backend.main:app --reload --port 8080
```

### 6. Iniciar o Frontend (dev)
```bash
cd src/frontend
npm install
npm run dev
```

### 7. Acessar
- Frontend: http://localhost:5173
- Backend API: http://localhost:8080/docs

## Como usar

1. **Envie manuais** do eProc (PDF/DOCX) pelo botão de upload na sidebar
2. **Faça perguntas** no chat — o sistema busca nos manuais e gera respostas com passo-a-passo
3. **Veja as fontes** — cada resposta mostra os trechos dos manuais consultados

## Deploy no Railway

1. Crie um projeto no Railway com PostgreSQL addon (habilite pgvector)
2. Configure as variáveis de ambiente (DATABASE_URL é automático)
3. Conecte o repositório — o `railway.toml` já configura o build
