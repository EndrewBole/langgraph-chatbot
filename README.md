# Temporalis AI — WhatsApp Customer Service Chatbot

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.12-blue?logo=python&logoColor=white" />
  <img src="https://img.shields.io/badge/LangGraph-Agent-purple?logo=langchain&logoColor=white" />
  <img src="https://img.shields.io/badge/FastAPI-async-009688?logo=fastapi&logoColor=white" />
  <img src="https://img.shields.io/badge/WhatsApp-Evolution_API-25D366?logo=whatsapp&logoColor=white" />
  <img src="https://img.shields.io/badge/Instagram-Chatwoot_Bridge-E4405F?logo=instagram&logoColor=white" />
  <img src="https://github.com/EndrewBole/langgraph-chatbot/actions/workflows/ci.yml/badge.svg" alt="CI" />
  <img src="https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker&logoColor=white" />
</p>

AI-powered customer service chatbot for a motorcycle parts store, built with **LangGraph** + **GPT-4o-mini**. The virtual assistant **Lis** handles WhatsApp and Instagram DM messages — classifying intent, searching the product catalog via RAG, and responding automatically.

## Demo

> Sample conversation showing the bot in action (WhatsApp)

```
👤 Customer: oi, preciso de filtro para cb300

🤖 Lis: Olá! Sou a Lis, atendente virtual da Temporalis AI! 😊
         Encontrei estas opções para você:

         *1. Filtro de Combustível*
         - Descrição: Filtro de combustível Honda CB 300F
         - 💰 Preço: R$ 18,90
         - 📅 Anos: 2009-2015
         - 🏷️ Marca: Vedamotors
         - 🏍️ Modelo: CB 300F

         *2. Filtro de Óleo*
         - Descrição: Filtro de óleo original Honda CB 300F
         - 💰 Preço: R$ 22,50
         - 📅 Anos: 2009-2023
         - 🏷️ Marca: HiFlo
         - 🏍️ Modelo: CB 300F

         Qual dessas peças você precisa? 🔧

👤 Customer: o filtro de óleo. como compro?

🤖 Lis: Ótima escolha! Nossos canais de compra:
         🛒 Mercado Livre: mercadolivre.com.br
         🛒 Shopee: shopee.com.br
         🛒 Amazon: amazon.com.br
         🏪 Loja física: Rua P R A, 313

         Posso ajudar com mais alguma coisa? 🔧

👤 Customer: quero falar com atendente

🤖 Lis: Entendo! Vou encaminhar você para um de nossos
         atendentes. Aguarde um momento, por favor! 🙏
         → [Human agent notified via Chatwoot]
```

## Features

- **Multi-channel support** — WhatsApp (Evolution API) + Instagram DM (Chatwoot bridge)
- **RAG product search** — semantic search over the parts catalog using Supabase pgvector
- **Intent classification** — 5 categories: parts lookup, general questions, store pickup, returns, human handoff
- **Audio transcription** — processes voice messages via OpenAI Whisper
- **Image analysis** — processes product photos via GPT-4o vision
- **Human handoff loop** — escalates to a human agent after 3 failed attempts, with full Chatwoot integration
- **Conversation memory** — persistent state via PostgreSQL (Supabase) with session timeout
- **Message buffering** — aggregates rapid messages before processing
- **Catalog auto-reindex** — background scheduler keeps the RAG index fresh
- **Follow-up scheduler** — sends follow-up messages for idle conversations
- **Observability** — full tracing via LangSmith

## Architecture

### Tech Stack

| Layer | Technology |
|-------|-----------|
| Language | Python 3.12 |
| Agent Framework | LangGraph (StateGraph) |
| LLM | OpenAI GPT-4o-mini |
| Embeddings | OpenAI text-embedding-3-small |
| Transcription | OpenAI Whisper |
| Vector Store | Supabase pgvector |
| API | FastAPI + httpx (async) |
| WhatsApp | Evolution API v2 (self-hosted, open-source) |
| Customer Support | Chatwoot (conversation management, agent handoff) |
| Memory | PostgresSaver (prod) / MemorySaver (dev) |
| Observability | LangSmith |
| Infrastructure | Docker Compose + Cloudflare Tunnel |

### LangGraph Flow

```
START → (human active? skip → END)
      → chatbot (classify) → tools (RAG search) → respond → human_handoff → send_response → END
                                   ↓ (no tools)
                             human_handoff → send_response → END
```

| Node | Responsibility |
|------|---------------|
| **START** | Checks if human agent is active (`em_atendimento_humano`) |
| **chatbot** (classify) | LLM with tools classifies intent, may invoke `buscar` |
| **tools** | Executes RAG tool `buscar` (Supabase pgvector) |
| **respond** | LLM without tools generates response using RAG results |
| **human_handoff** | Detects `#HUMANO#` tag, escalates after 3 attempts |
| **send_response** | Dispatches response — WhatsApp via Evolution API or Instagram via Chatwoot API |

### Intent Categories

| Category | Triggers | Action |
|----------|----------|--------|
| **A — Parts** | part name, price, stock, model, brand | RAG search in catalog |
| **B — General** | greetings, questions, shipping, payment | Direct response |
| **C — Pickup** | address, pick up, directions | Store address |
| **D — Returns** | return, exchange, defect, complaint | Identifies purchase channel |
| **E — Human** | request for agent, extreme frustration | Empathy + `#HUMANO#` → escalate |

### RAG Pipeline

```
PDF/CSV/XLSX/DOCX → Loaders → Splitters (256/512 chars) → MD5 Dedup → Embeddings → Supabase pgvector
                                                                                          ↓
                                              User query → Embedding → RPC match_documents → Rerank top 3 → Response
```

### Docker Compose Services

```
┌─────────────────────────────────────────────────────┐
│                  Docker Compose                      │
│                                                      │
│  ┌──────────┐  ┌───────────────┐  ┌──────────────┐  │
│  │ chatbot  │  │ evolution-api │  │  cloudflared  │  │
│  │ :8000    │←→│ :8080         │  │  (tunnel)     │  │
│  └────┬─────┘  └───────┬───────┘  └──────────────┘  │
│       │                │                              │
│  ┌────┴────┐    ┌──────┴──────┐                      │
│  │chatwoot │    │  postgres   │                      │
│  │ :3000   │    │ (pgvector)  │                      │
│  └────┬────┘    └─────────────┘                      │
│       │                                              │
│  ┌────┴─────────┐  ┌───────┐                         │
│  │chatwoot-worker│  │ redis │                         │
│  └──────────────┘  └───────┘                         │
└─────────────────────────────────────────────────────┘
```

## Project Structure

```
chatbot/
├── docker-compose.yml
├── Dockerfile
├── pyproject.toml
├── .env.example
├── scripts/
│   ├── ingest.py                     # RAG document ingestion
│   ├── supabase_setup.sql            # documents table + match_documents RPC
│   ├── supabase_checkpointer.sql     # conversation memory tables
│   └── supabase_search_log.sql       # search analytics table
├── src/
│   ├── main.py                       # FastAPI app + CLI mode
│   ├── state.py                      # AgentState (TypedDict)
│   ├── config/
│   │   └── settings.py               # Environment config
│   ├── graph/
│   │   ├── builder.py                # Graph compilation
│   │   ├── classify.py               # Intent classification node
│   │   ├── respond.py                # Response generation node
│   │   ├── handoff.py                # Human handoff logic
│   │   ├── send.py                   # Message dispatch (WhatsApp/Instagram)
│   │   ├── sentiment.py              # Frustration detection
│   │   ├── llm.py                    # LLM singletons (thread-safe)
│   │   ├── prompt.py                 # System prompt (single source of truth)
│   │   ├── edges.py                  # Conditional routing
│   │   └── nodes.py                  # Backward-compat facade
│   ├── tools/
│   │   └── buscar.py                 # @tool buscar(query) — RAG search
│   ├── rag/
│   │   ├── loaders.py                # PDF, CSV, XLSX, DOCX loaders
│   │   ├── splitters.py              # Product (256) vs document (512) splitters
│   │   ├── indexer.py                # MD5 dedup + embeddings + pgvector
│   │   └── retriever.py              # Similarity search + rerank
│   ├── integrations/
│   │   ├── evolution.py              # Evolution API (WhatsApp send/receive)
│   │   ├── chatwoot.py               # Chatwoot API (Instagram + handoff)
│   │   ├── whisper.py                # Audio transcription
│   │   └── vision.py                 # Image analysis via GPT-4o
│   ├── memory/
│   │   └── checkpointer.py           # PostgresSaver / MemorySaver auto-detect
│   ├── scheduler/
│   │   ├── follow_up.py              # Follow-up message scheduler
│   │   └── catalog_reindex.py        # Periodic RAG re-ingestion
│   └── api/
│       └── routes/
│           ├── whatsapp.py           # POST /webhook/whatsapp
│           ├── chatwoot.py           # POST /webhook/chatwoot
│           └── health.py             # GET /health
└── tests/                            # 229 tests
    ├── test_new_graph.py
    ├── test_new_nodes.py
    ├── test_chatwoot_integration.py
    ├── test_instagram_chatwoot.py
    ├── test_human_handoff_loop.py
    ├── test_rag_*.py
    └── ...
```

## Getting Started

### Prerequisites

- Python 3.12+
- Docker & Docker Compose
- OpenAI API key
- Supabase project (for pgvector + PostgreSQL)

### Quick Start (Docker)

```bash
git clone https://github.com/your-username/temporalis-chatbot.git
cd temporalis-chatbot

cp .env.example .env
# Edit .env with your API keys

docker compose up -d
```

### Local Development

```bash
python -m venv .venv
source .venv/bin/activate    # Linux/Mac
.venv\Scripts\activate       # Windows

pip install -e ".[dev]"

cp .env.example .env
# Edit .env with your API keys

# Run Supabase SQL scripts (in order):
# 1. scripts/supabase_setup.sql
# 2. scripts/supabase_checkpointer.sql

# Ingest catalog data
python scripts/ingest.py

# Start server
uvicorn src.main:app --reload --port 8000

# Or interactive CLI mode
python -m src.main
```

### Running Tests

```bash
# All tests
python -m pytest tests/ -v

# Specific test
python -m pytest tests/test_rag_indexer.py -v

# With coverage
python -m pytest tests/ --cov=src --cov-report=term-missing
```

## Environment Variables

See [`.env.example`](.env.example) for the full list.

| Variable | Description |
|----------|------------|
| `OPENAI_API_KEY` | OpenAI API key |
| `SUPABASE_URL` | Supabase project URL |
| `SUPABASE_SERVICE_KEY` | Supabase service role key |
| `DATABASE_URL` | PostgreSQL connection string |
| `EVOLUTION_API_URL` | Evolution API URL |
| `EVOLUTION_API_KEY` | Evolution API authentication key |
| `CHATWOOT_API_URL` | Chatwoot instance URL |
| `CHATWOOT_API_KEY` | Chatwoot API access token |
| `STORE_OWNER_PHONE` | Store owner phone for handoff notifications |

## Sales Channels

The bot directs customers to the appropriate sales channel:

- **Mercado Livre** — https://www.mercadolivre.com.br/
- **Shopee** — https://shopee.com.br/
- **Amazon** — https://www.amazon.com.br/
- **Physical store** — Rua P R A, 313
- **WhatsApp / Instagram** — customer service only, not a sales channel

## License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.
