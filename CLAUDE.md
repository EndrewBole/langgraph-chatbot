# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

WhatsApp customer service chatbot for a motorcycle parts store (**Temporalis AI**).
Receives messages (text, audio, images) via Evolution API webhook, processes with LangGraph + GPT-4o-mini, and responds via Evolution API (WhatsApp) or Chatwoot API (Instagram DM).

## Stack

- **Python 3.12** — primary language
- **LangGraph** — agent orchestration (StateGraph with nodes/edges)
- **LangChain** — LLM integration (ChatOpenAI) + tools + embeddings
- **FastAPI** — webhook receiver (Evolution API WhatsApp + Chatwoot)
- **httpx** — async HTTP client (Evolution API, Whisper, Chatwoot)
- **Supabase pgvector** — vector store for RAG (RPC `match_documents` via supabase-py)
- **Supabase PostgreSQL** — conversation memory (PostgresSaver from langgraph-checkpoint-postgres)
- **OpenAI** — LLM (gpt-4o-mini), embeddings (text-embedding-3-small), transcription (whisper-1), vision (gpt-4o)
- **Evolution API** — WhatsApp messaging API (self-hosted, open-source)
- **Chatwoot** — customer support platform (conversation management, agent handoff, Instagram DM bridge)
- **LangSmith** — observability and graph tracing
- **Docker Compose** — service orchestration (chatbot + Evolution API + Chatwoot + Cloudflare Tunnel)

## Commands

```bash
# Run tests (253 tests, 95% coverage)
python -m pytest tests/ -v

# Run a specific test
python -m pytest tests/test_rag_indexer.py::test_indexer_creates_vectorstore -v

# Run with coverage
python -m pytest tests/ --cov=src --cov-report=term-missing

# Start FastAPI server
uvicorn src.main:app --reload --port 8000

# Interactive CLI mode
python -m src.main

# RAG document ingestion
python scripts/ingest.py
python scripts/ingest.py --clear              # clear and reindex
python scripts/ingest.py --data-dir /path     # custom data directory

# Docker Compose (production)
docker compose up -d

# Test webhook locally
curl -X POST http://localhost:8000/webhook/whatsapp \
  -H "Content-Type: application/json" \
  -H "apikey: your-api-key" \
  -d '{"event":"messages.upsert","instance":"your-instance","data":{"key":{"remoteJid":"5500000000000@s.whatsapp.net","fromMe":false,"id":"test1"},"message":{"conversation":"need oil filter for cb300"},"messageType":"conversation"}}'
```

## LangGraph Architecture

```
START -> (human active? skip -> END)
      -> chatbot (classify) -> tools (RAG search) -> respond -> human_handoff -> send_response -> END
                                   | (no tools)
                             human_handoff -> send_response -> END
```

- **START** — conditional edge checks `em_atendimento_humano`, skips if active
- **chatbot (classify_node)** — `src/graph/classify.py` — LLM with bound tools classifies intent
- **tools (tool_node)** — executes ToolNode with the `buscar` tool (RAG)
- **respond (respond_node)** — `src/graph/respond.py` — LLM without tools generates response using RAG results
- **human_handoff** — `src/graph/handoff.py` — detects `#HUMANO#` tag, counts attempts, escalates after 3x
- **send_response** — `src/graph/send.py` — dispatches response via Evolution API (WhatsApp) or Chatwoot API (Instagram)

### Graph Modules (split from nodes.py)

| Module | Responsibility |
|--------|---------------|
| `prompt.py` | SYSTEM_PROMPT (single source of truth) |
| `sentiment.py` | Frustration detection + message helpers |
| `llm.py` | LLM singletons with lazy loading + thread safety |
| `classify.py` | classify_node + language detection |
| `respond.py` | respond_node |
| `handoff.py` | human_handoff_node + handoff constants |
| `send.py` | send_response_node + [BTN:] block parsing |
| `nodes.py` | Facade — re-exports everything for backward compat |

**Patching in tests:** use canonical module (e.g., `src.graph.classify._get_llm_classify`, `src.graph.handoff.send_message`)

## Agent Categories

- **A** (parts) — must use `buscar` tool (RAG with Supabase pgvector)
- **B** (general) — direct response, no search
- **C** (pickup) — fixed address: Rua P R A, 313
- **D** (returns) — identifies purchase channel, directs to marketplace or store
- **E** (human) — responds + `#HUMANO#` tag, escalates after 3 attempts

## RAG Pipeline

1. **Loaders** (`src/rag/loaders.py`) — PDF, CSV, XLSX, DOCX
2. **Splitters** (`src/rag/splitters.py`) — products (256 chars) vs documents (512 chars)
3. **Indexer** (`src/rag/indexer.py`) — MD5 deduplication (cross-execution via Supabase), OpenAI embeddings, Supabase pgvector
4. **Retriever** (`src/rag/retriever.py`) — RPC `match_documents` + threshold (0.65) + rerank top 3
5. **Tool** (`src/tools/buscar.py`) — `@tool buscar(query)` used by the agent

### Supabase Setup

Run in Supabase SQL Editor:

1. `scripts/supabase_setup.sql` — `documents` table, HNSW/GIN indexes, `match_documents` function, RLS
2. `scripts/supabase_checkpointer.sql` — conversation memory tables (checkpoints), RLS

## Conversation Memory

- **PostgresSaver** (production) — persists graph state in Supabase PostgreSQL via `psycopg`
- **MemorySaver** (dev) — in-memory, activated when `DATABASE_URL` is empty
- **Auto-detection** — `builder.py` uses `bool(settings.DATABASE_URL)` to choose

## FastAPI — Webhooks & Lifespan

- **WhatsApp endpoint:** `POST /webhook/whatsapp` (`src/api/routes/whatsapp.py`)
- **Chatwoot endpoint:** `POST /webhook/chatwoot` (`src/api/routes/chatwoot.py`) — handles `conversation_status_changed` (resets handoff) and `message_created` (Instagram DM)
- **Chatwoot outgoing proxy:** `POST /webhook/chatwoot/outgoing` — intercepts agent messages, filters `#BOT#` command, strips trailing newlines
- **Payload:** Evolution API JSON (fields: `event`, `data.key.remoteJid`, `data.message.conversation`, `data.message.audioMessage.url`)
- **Validation:** `apikey` header (skipped when `EVOLUTION_API_KEY` is empty)
- **Filters:** ignores `fromMe=true` (prevents loop), `isGroup=true`, and events != `messages.upsert`
- **Lifespan:** shared `httpx.AsyncClient` via `app.state.http_client`
- **Async integrations:** `send_whatsapp_message(client, to_phone, body)` and `transcribe_audio(client, media_url)`
- **Graph execution:** `asyncio.to_thread(graph.invoke, ...)` — runs sync graph in thread pool without blocking the event loop
- **Graph node sync:** `send_message(to_phone, body)` kept sync inside graph.invoke (runs in thread)

## Human Handoff — Full Loop

### A) Store owner notification
When `tentativas_categoria_e` reaches the threshold (3) for the **first time** in `human_handoff_node`, sends WhatsApp message to `STORE_OWNER_PHONE` via `send_message()`. Does not resend if `em_atendimento_humano` was already `True`.

### B) Human agent reply forwarding
In the webhook (`src/api/routes/whatsapp.py`), `fromMe=True` messages are no longer ignored unconditionally. If the customer's phone has `em_atendimento_humano=True` in the graph state, the message is forwarded to the customer via `send_whatsapp_message()`.

### C) Release back to bot
If the `fromMe=True` message contains the release command (`HUMAN_RELEASE_COMMAND`, default `#BOT#`), the graph state is updated with `em_atendimento_humano=False` and `requer_humano=False` via `graph.update_state()`, and the owner receives confirmation. The command is not forwarded to the customer.

## Chatwoot Integration

Evolution API mirrors all WhatsApp messages to Chatwoot natively. The bot processes messages normally. When `em_atendimento_humano=True`, the bot stops responding and the Chatwoot agent takes over. When the agent resolves the conversation in Chatwoot, a `conversation_status_changed` webhook fires to `POST /webhook/chatwoot`, which resets the handoff flag and notifies the customer.

## Instagram DM via Chatwoot Bridge

Evolution API v2 does not support Instagram DM natively. Instagram DMs are handled via Chatwoot bridge:

1. **Chatwoot receives Instagram DMs** via native Instagram inbox integration
2. **Webhook `message_created`** fires to `POST /webhook/chatwoot` with `channel: "Channel::Instagram"`
3. **Bot processes** through same LangGraph pipeline with `channel="instagram"`, `thread_id="ig_{contact_id}"`
4. **Responses sent** via Chatwoot API (`send_chatwoot_message()`) instead of Evolution API
5. **Resolved handler** is channel-aware — Instagram uses Chatwoot API, WhatsApp uses Evolution API

Key files: `src/api/routes/chatwoot.py` (webhook), `src/graph/send.py` (dispatch), `src/integrations/chatwoot.py` (API client)

## Catalog Auto-Reindex

Background scheduler (`src/scheduler/catalog_reindex.py`) that periodically re-runs the RAG ingestion pipeline (load -> split -> dedup -> index). Controlled by `CATALOG_REINDEX_ENABLED` (default `true`) and `CATALOG_REINDEX_INTERVAL_HOURS` (default `24`). Delegates dedup to `create_vectorstore` (MD5 hash-based). Started as `asyncio.create_task` in `src/main.py` lifespan.

## Docker Compose

```yaml
services:
  chatbot        # FastAPI app (port 8000)
  evolution-api  # Evolution API self-hosted (port 8080)
  cloudflared    # Cloudflare Tunnel (automatic public URL)
  postgres       # PostgreSQL 15 with pgvector
  redis          # Redis 7 for Chatwoot
  chatwoot       # Chatwoot web (port 3000)
  chatwoot-worker # Chatwoot Sidekiq worker
```

- `docker compose up -d` — starts all services
- Cloudflare Tunnel generates public URL `*.trycloudflare.com` automatically
- Evolution API data persisted in `evolution_data` volume
- Chatwoot data persisted in `postgres_data`, `redis_data`, `chatwoot_storage` volumes

## Environment Variables

```
OPENAI_API_KEY, MODEL_NAME, WHISPER_MODEL
SUPABASE_URL, SUPABASE_SERVICE_KEY
DATABASE_URL
EVOLUTION_API_URL, EVOLUTION_API_KEY, EVOLUTION_INSTANCE_NAME
LANGSMITH_TRACING, LANGCHAIN_API_KEY, LANGCHAIN_PROJECT
EMBEDDING_MODEL, RAG_SIMILARITY_THRESHOLD, RAG_TOP_K, RAG_RERANK_TOP_N
DATA_DIR
STORE_OWNER_PHONE, HUMAN_RELEASE_COMMAND
CHATWOOT_API_URL, CHATWOOT_API_KEY, CHATWOOT_ACCOUNT_ID
CATALOG_REINDEX_ENABLED, CATALOG_REINDEX_INTERVAL_HOURS
POSTGRES_PASSWORD, CHATWOOT_SECRET_KEY_BASE
```

## Conventions

- **TDD always** — write tests first, confirm RED, implement, confirm GREEN
- **Commit + push** after each successful implementation with all tests passing
- **Async for I/O** — httpx.AsyncClient, never `requests`
- **Logging** — `logging.getLogger(__name__)`, never `print()`
- **Type hints** — on all functions
- **Lazy loading** — LLMs and vectorstore loaded on demand (`_get_llm_classify()`, `_get_llm_respond()`, `_get_vectorstore()`)
- **Thread safety** — `threading.Lock` with double-checked locking for lazy-loaded LLMs

## Sales Channels

- Mercado Livre: https://www.mercadolivre.com.br/
- Shopee: https://shopee.com.br/
- Amazon: https://www.amazon.com.br/
- Physical store: Rua P R A, 313
- WhatsApp and Instagram are customer service ONLY, not sales channels
