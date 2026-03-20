# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Projeto

ChatBot de atendimento via WhatsApp para a loja de pecas de moto **Temporalis AI**.
Recebe mensagens (texto e audio) via Evolution API webhook, processa com LangGraph + GPT-4o-mini e responde via Evolution API WhatsApp.

## Stack

- **Python 3.12** — linguagem principal
- **LangGraph** — orquestracao do agente (StateGraph com nodes/edges)
- **LangChain** — integracao LLM (ChatOpenAI) + tools + embeddings
- **FastAPI** — webhook receiver (Evolution API WhatsApp)
- **httpx** — cliente HTTP async (Evolution API, Whisper)
- **Supabase pgvector** — vector store para RAG (RPC `match_documents` via supabase-py)
- **Supabase PostgreSQL** — memoria de conversas (PostgresSaver do langgraph-checkpoint-postgres)
- **OpenAI** — LLM (gpt-4o-mini), embeddings (text-embedding-3-small), transcricao (whisper-1)
- **Evolution API** — WhatsApp messaging API (self-hosted, open-source)
- **LangSmith** — observabilidade e tracing do grafo
- **Chatwoot** — customer support platform (conversation management, agent handoff)
- **Docker Compose** — orquestracao de servicos (chatbot + Evolution API + Chatwoot + Cloudflare Tunnel)

## Comandos

```bash
# Rodar testes (229 testes)
python -m pytest tests/ -v

# Rodar um teste especifico
python -m pytest tests/test_rag_indexer.py::test_indexer_creates_vectorstore -v

# Rodar servidor FastAPI
uvicorn src.main:app --reload --port 8000

# Modo CLI interativo
python -m src.main

# Ingestao de documentos para RAG
python scripts/ingest.py
python scripts/ingest.py --clear              # limpa e reindexa
python scripts/ingest.py --data-dir /caminho  # pasta customizada

# Docker Compose (producao)
docker compose up -d

# Testar webhook localmente
curl -X POST http://localhost:8000/webhook/whatsapp \
  -H "Content-Type: application/json" \
  -H "apikey: your-api-key" \
  -d '{"event":"messages.upsert","instance":"your-instance","data":{"key":{"remoteJid":"5500000000000@s.whatsapp.net","fromMe":false,"id":"test1"},"message":{"conversation":"preciso de filtro para cb300"},"messageType":"conversation"}}'
```

## Arquitetura do Grafo LangGraph

```
START -> (humano ativo? skip -> END)
      -> chatbot (classify) -> tools (buscar RAG) -> respond -> human_handoff -> send_response -> END
                                   | (sem tools)
                             human_handoff -> send_response -> END
```

- **START** — conditional edge verifica `em_atendimento_humano`, pula se ativo
- **chatbot (classify_node)** — `src/graph/classify.py` — LLM com tools bound classifica intencao
- **tools (tool_node)** — executa ToolNode com a tool `buscar` (RAG)
- **respond (respond_node)** — `src/graph/respond.py` — LLM sem tools responde com resultados do tool
- **human_handoff** — `src/graph/handoff.py` — detecta `#HUMANO#`, conta tentativas, escalona apos 3x
- **send_response** — `src/graph/send.py` — envia resposta via Evolution API WhatsApp

### Modulos do Graph (split de nodes.py)

| Modulo | Responsabilidade |
|--------|-----------------|
| `prompt.py` | SYSTEM_PROMPT (unica fonte de verdade) |
| `sentiment.py` | Deteccao de frustracao + helpers de mensagem |
| `llm.py` | Singletons LLM lazy-loaded com thread safety |
| `classify.py` | classify_node + deteccao de idioma |
| `respond.py` | respond_node |
| `handoff.py` | human_handoff_node + constantes de handoff |
| `send.py` | send_response_node + parsing de blocos [BTN:] |
| `nodes.py` | Facade — re-exporta tudo para backward compat |

**Patching em testes:** usar modulo canonico (ex: `src.graph.classify._get_llm_classify`, `src.graph.handoff.send_message`)

## Categorias do Agente

- **A** (pecas) — obrigatorio usar tool `buscar` (RAG com Supabase pgvector)
- **B** (geral) — resposta direta, sem busca
- **C** (retirada) — endereco fixo: Rua P R A, 313
- **D** (devolucao) — identifica canal da compra, direciona para ML se online
- **E** (humano) — responde + tag `#HUMANO#`, apos 3x aciona atendimento humano

## RAG Pipeline

1. **Loaders** (`src/rag/loaders.py`) — PDF, CSV, XLSX, DOCX
2. **Splitters** (`src/rag/splitters.py`) — produtos (256 chars) vs documentos (512 chars)
3. **Indexer** (`src/rag/indexer.py`) — deduplicacao por MD5 (cross-execucao via Supabase), embeddings OpenAI, Supabase pgvector
4. **Retriever** (`src/rag/retriever.py`) — RPC `match_documents` + threshold (0.65) + rerank top 3
5. **Tool** (`src/tools/buscar.py`) — `@tool buscar(query)` usada pelo agente

### Setup Supabase

Executar no SQL Editor do Supabase os scripts:

1. `scripts/supabase_setup.sql` — tabela `documents`, indices HNSW/GIN, funcao `match_documents`, RLS
2. `scripts/supabase_checkpointer.sql` — tabelas de memoria de conversas (checkpoints), RLS

## Memoria de Conversas

- **PostgresSaver** (producao) — persiste estado do grafo no PostgreSQL do Supabase via `psycopg`
- **MemorySaver** (dev) — in-memory, ativado quando `DATABASE_URL` esta vazio
- **Auto-deteccao** — `builder.py` usa `bool(settings.DATABASE_URL)` para escolher

## FastAPI — Webhook e Lifespan

- **Endpoint WhatsApp:** `POST /webhook/whatsapp` (rota em `src/api/routes/whatsapp.py`)
- **Endpoint Chatwoot:** `POST /webhook/chatwoot` (rota em `src/api/routes/chatwoot.py`) — recebe `conversation_resolved` (reseta handoff) e `message_created` (Instagram DM)
- **Payload:** JSON da Evolution API (campos: `event`, `data.key.remoteJid`, `data.message.conversation`, `data.message.audioMessage.url`)
- **Validacao:** `apikey` header (skip quando `EVOLUTION_API_KEY` vazio)
- **Filtros:** ignora mensagens `fromMe=true` (evita loop), `isGroup=true`, e eventos != `messages.upsert`
- **Lifespan:** `httpx.AsyncClient` compartilhado via `app.state.http_client`
- **Integrations async:** `send_whatsapp_message(client, to_phone, body)` e `transcribe_audio(client, media_url)`
- **Graph execution:** `asyncio.to_thread(graph.invoke, ...)` — roda o grafo sync em thread pool sem bloquear o event loop
- **Graph node sync:** `send_message(to_phone, body)` mantido sync dentro do graph.invoke (roda na thread)

## Human Handoff — Loop Completo (v0.11.0)

### A) Notificacao ao dono da loja
Quando `tentativas_categoria_e` atinge o threshold (3) pela **primeira vez** no `human_handoff_node`, envia mensagem WhatsApp para `STORE_OWNER_PHONE` via `send_message()`. Nao reenvia se `em_atendimento_humano` ja era `True`.

### B) Encaminhamento de respostas do atendente humano
No webhook (`src/api/routes/whatsapp.py`), mensagens `fromMe=True` nao sao mais ignoradas incondicionalmente. Se o telefone do cliente tem `em_atendimento_humano=True` no estado do grafo, a mensagem e encaminhada ao cliente via `send_whatsapp_message()`.

### C) Liberacao de volta para o bot
Se a mensagem `fromMe=True` contem o comando de liberacao (`HUMAN_RELEASE_COMMAND`, padrao `#BOT#`), o estado do grafo e atualizado com `em_atendimento_humano=False` e `requer_humano=False` via `graph.update_state()`, e o dono recebe confirmacao. O comando nao e encaminhado ao cliente.

## Chatwoot Integration (v0.12.0)

Evolution API mirrors all WhatsApp messages to Chatwoot natively. The bot processes messages normally. When `em_atendimento_humano=True`, the bot stops responding and the Chatwoot agent takes over. When the agent resolves the conversation in Chatwoot, a `conversation_resolved` webhook fires to `POST /webhook/chatwoot`, which resets the handoff flag and notifies the customer.

## Instagram DM via Chatwoot Bridge (v0.16.0)

Evolution API v2 does not support Instagram DM natively. Instagram DMs are handled via Chatwoot bridge:

1. **Chatwoot receives Instagram DMs** via native Instagram inbox integration
2. **Webhook `message_created`** fires to `POST /webhook/chatwoot` with `channel: "Channel::Instagram"`
3. **Bot processes** through same LangGraph pipeline with `channel="instagram"`, `thread_id="ig_{contact_id}"`
4. **Responses sent** via Chatwoot API (`send_chatwoot_message()`) instead of Evolution API
5. **Resolved handler** is channel-aware — Instagram uses Chatwoot API, WhatsApp uses Evolution API

Key files: `src/api/routes/chatwoot.py` (webhook), `src/graph/send.py` (dispatch), `src/integrations/chatwoot.py` (API client)

## Catalog Auto-Reindex (v0.15.0)

Background scheduler (`src/scheduler/catalog_reindex.py`) that periodically re-runs the RAG ingestion pipeline (load -> split -> dedup -> index). Follows the same pattern as `follow_up_loop`. Controlled by `CATALOG_REINDEX_ENABLED` (default `true`) and `CATALOG_REINDEX_INTERVAL_HOURS` (default `24`). Delegates dedup to `create_vectorstore` (MD5 hash-based). Started as `asyncio.create_task` in `src/main.py` lifespan.

## Docker Compose (v0.12.0)

```yaml
services:
  chatbot        # FastAPI app (porta 8000)
  evolution-api  # Evolution API self-hosted (porta 8080)
  cloudflared    # Cloudflare Tunnel (URL publica automatica)
  postgres       # PostgreSQL 15 para Chatwoot
  redis          # Redis 7 para Chatwoot
  chatwoot       # Chatwoot web (porta 3000)
  chatwoot-worker # Chatwoot Sidekiq worker
```

- `docker compose up -d` — sobe todos os servicos
- Cloudflare Tunnel gera URL publica `*.trycloudflare.com` automaticamente
- Evolution API persiste dados em volume `evolution_data`
- Chatwoot persiste dados em volumes `postgres_data`, `redis_data`, `chatwoot_storage`
- Setup guide: `docs/chatwoot-setup.md`

## Variaveis de Ambiente

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
```

## Convencoes

- **TDD sempre** — escrever testes primeiro, confirmar RED, implementar, confirmar GREEN
- **Commit + push** apos cada implementacao bem sucedida com todos os testes passando
- **Async para I/O** — httpx.AsyncClient, nunca `requests`
- **Logging** — `logging.getLogger(__name__)`, nunca `print()`
- **Type hints** — em todas as funcoes
- **Lazy loading** — LLMs e vectorstore carregados sob demanda (`_get_llm_classify()`, `_get_llm_respond()`, `_get_vectorstore()`)
- **Thread safety** — `threading.Lock` com double-checked locking para LLMs lazy-loaded

## Canais de Venda

- Mercado Livre: https://www.mercadolivre.com.br/
- Shopee: https://shopee.com.br/
- Amazon: https://www.amazon.com.br/
- Loja fisica: Rua P R A, 313
- WhatsApp e APENAS atendimento, nao venda
