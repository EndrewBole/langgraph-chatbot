# Temporalis AI Chatbot — Improvements Roadmap

## Status

| # | Improvement | Value | Complexity | Status |
|---|-------------|-------|------------|--------|
| 1 | Human Handoff | High | Medium | ✅ Done (v0.11–v0.13) |
| 2 | Cloud deployment (URL fixa) | High | Low | 🔴 Pendente — requer domínio |
| 3 | Proactive follow-up | Medium | Low | ✅ Done (v0.14) |
| 4 | Sentiment detection | Medium | Medium | ✅ Done (v0.15) |
| 5 | Catalog auto-update | Medium | Medium | ✅ Done (v0.15) |
| 6 | Search analytics | Medium | Low | ✅ Done (v0.15) |
| 7 | Image recognition | High | High | ✅ Done (v0.15) |
| 8 | Order status — Mercado Livre | High | High | 🟢 Pendente |
| 9 | Rate limiting | Low | Low | ✅ Done (v0.15) |
| 10 | Multi-language (ES/EN) | Low | Low | ✅ Done (v0.15) |
| 11 | Order status — Shopee | High | High | 🟢 Pendente |
| 12 | Order status — Amazon | High | High | 🟢 Pendente |
| 13 | Instagram DM (Chatwoot bridge) | High | Medium | ✅ Done (v0.16) |
| 14 | Auto-resposta ML (perguntas) | High | Medium | 🟡 Pendente |

---

## Pendentes — Phase 2: Marketplace Integrations

### 2. Cloud Deployment (URL fixa)

Cloudflare Quick Tunnel (atual) muda URL a cada restart. Named Tunnel requer domínio registrado no Cloudflare. Alternativas: Railway (~$5/mês), Render (~$7/mês), VPS (~$6/mês).

### 8. Order Status — Mercado Livre

- ML Seller API OAuth 2.0 (access_token 6h, refresh_token 6 meses)
- Tool `buscar_pedido(order_id)` → `GET /orders/{id}`
- Env: `ML_APP_ID`, `ML_SECRET_KEY`, `ML_ACCESS_TOKEN`, `ML_REFRESH_TOKEN`, `ML_SELLER_ID`
- Compartilha OAuth com item #14
- Effort: ~3-5 dias

### 11. Order Status — Shopee

- Shopee Open Platform (OAuth 2.0 + HMAC-SHA256 por request)
- Token expira a cada 4h (mais curto que ML)
- Tool `buscar_pedido_shopee(order_sn)` → `/api/v2/order/get_order_detail`
- Env: `SHOPEE_PARTNER_ID`, `SHOPEE_PARTNER_KEY`, `SHOPEE_SHOP_ID`, `SHOPEE_ACCESS_TOKEN`, `SHOPEE_REFRESH_TOKEN`
- Effort: ~3-5 dias

### 12. Order Status — Amazon

- Amazon SP-API (AWS Signature V4 + LWA OAuth 2.0) — mais complexo dos 3
- Recomendado usar lib `python-amazon-sp-api`
- Tool `buscar_pedido_amazon(order_id)` → `/orders/v0/orders/{id}`
- Env: `AMAZON_SP_CLIENT_ID`, `AMAZON_SP_CLIENT_SECRET`, `AMAZON_SP_REFRESH_TOKEN`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_ROLE_ARN`
- Effort: ~5-7 dias

### 13. Instagram DM ✅ (v0.16)

- **Via Chatwoot bridge:** Evolution API v2 não suporta Instagram DM nativamente. Chatwoot recebe DMs via inbox Instagram nativo e dispara webhook `message_created` para o bot.
- Webhook `POST /webhook/chatwoot` detecta `channel: "Channel::Instagram"` e processa pelo mesmo pipeline LangGraph
- Respostas enviadas via Chatwoot API (`send_chatwoot_message()`) em vez de Evolution API
- Thread ID: `ig_{contact_id}` — resolve handler channel-aware
- Setup: conectar Instagram Business no Chatwoot (Settings > Inboxes > Add Inbox > Instagram)

### 14. Auto-resposta Perguntas Mercado Livre

**Maior ROI da Phase 2.** Respostas rápidas convertem 3x mais e melhoram ranking ML.

- **Webhook:** `POST /webhook/mercadolivre` recebe notificação topic=questions
- **Flow:** Fetch question → LangGraph agent (RAG) → POST answer
- **Reutiliza:** catálogo já indexado no Supabase pgvector
- **Restrições ML:** sem links, telefone, email, WhatsApp nas respostas. 1 resposta por pergunta (sem edição). ~10k req/hora.
- **Compartilha OAuth com #8**
- Env: `ML_APP_ID`, `ML_SECRET_KEY`, `ML_ACCESS_TOKEN`, `ML_REFRESH_TOKEN`, `ML_SELLER_ID`
- Effort: ~3-5 dias

---

## Ordem de implementação recomendada

### Phase 1 — Foundation ✅ (concluída)
Items 1, 3, 4, 5, 6, 7, 9, 10 — todos Done.

### Phase 2 — Marketplace (próximo)
1. **Auto-resposta ML** (#14) — maior ROI, reutiliza RAG
2. **Order status ML** (#8) — compartilha OAuth com #14
3. ~~**Instagram DM** (#13)~~ — ✅ Done via Chatwoot bridge
4. **Order status Shopee** (#11) — HMAC + token 4h
5. **Order status Amazon** (#12) — SP-API + AWS Sig V4 (mais complexo)
6. **Cloud deployment** (#2) — quando tiver domínio
