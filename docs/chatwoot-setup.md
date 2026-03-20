# Chatwoot Setup Guide

Step-by-step instructions to integrate Chatwoot with the Temporalis AI chatbot.

## Prerequisites

- Docker and Docker Compose installed
- Evolution API instance configured and running
- Chatbot running and receiving WhatsApp messages

## 1. Start all services

```bash
docker compose up -d --build
```

This starts: chatbot, evolution-api, cloudflared, postgres, redis, chatwoot, chatwoot-worker.

## 2. Run Chatwoot database migrations

```bash
docker compose exec chatwoot bundle exec rails db:chatwoot_prepare
```

Wait for the migration to complete before proceeding.

## 3. Create admin account

Open http://localhost:3000 in your browser and create the initial admin account.

## 4. Create API inbox

1. Go to **Settings > Inboxes > Add Inbox**
2. Select **API** as the channel type
3. Name it **WhatsApp Temporalis**
4. Note the **inbox ID** from the URL after creation (e.g., `/app/accounts/1/settings/inboxes/1` means inbox_id = 1)

## 5. Configure Evolution API Chatwoot integration

1. Open the Evolution API manager at http://localhost:8080/manager
2. Select the **temporalis** instance
3. Go to the **Chatwoot** integration settings
4. Configure:
   - **Chatwoot URL**: `http://chatwoot:3000`
   - **Chatwoot Token**: (get from Chatwoot admin > Settings > Account Settings > Access Token)
   - **Account ID**: 1 (or whatever your account ID is)
   - **Inbox ID**: the inbox ID from step 4
5. Enable the integration and save

This makes Evolution API mirror all WhatsApp messages to Chatwoot automatically.

## 6. Configure Chatwoot webhook

1. In Chatwoot, go to **Settings > Integrations > Webhooks**
2. Add a new webhook:
   - **URL**: `http://chatbot:8000/webhook/chatwoot`
   - **Events**: select `conversation_resolved`
3. Save the webhook

This ensures that when a Chatwoot agent resolves a conversation, the bot is reactivated for that customer.

## 7. Update environment variables

Edit your `.env` file:

```
CHATWOOT_API_URL=http://chatwoot:3000
CHATWOOT_API_KEY=<your-chatwoot-access-token>
CHATWOOT_ACCOUNT_ID=<your-account-id>
```

Get the access token from Chatwoot: **Settings > Account Settings > Access Token**.

## 8. Restart chatbot

```bash
docker compose restart chatbot
```

## 9. Verify

Check the health endpoint:

```bash
curl http://localhost:8000/health
```

Expected response:

```json
{
  "status": "ok",
  "version": "0.12.0",
  "database": "connected",
  "evolution": "configured",
  "chatwoot": "configured"
}
```

## How it works

1. Customer sends WhatsApp message
2. Evolution API receives and forwards to both the chatbot webhook and Chatwoot
3. Chatbot processes normally via LangGraph
4. When `em_atendimento_humano=True` (after 3 category E attempts), bot stops responding
5. Chatwoot agent sees the conversation and responds directly
6. When agent resolves the conversation in Chatwoot, the `conversation_resolved` webhook fires
7. Chatbot resets the handoff flag and notifies the customer that the bot is back
