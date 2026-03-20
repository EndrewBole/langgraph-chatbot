---
name: evolution-api-expert
description: Expert in Evolution API — open-source WhatsApp integration. Invoke when the user asks to: create or manage instances, send messages (text, media, audio, video, documents, location, contacts, polls, lists, buttons), configure webhooks and events, set up integrations (Typebot, Chatwoot, OpenAI, Dify, n8n, Flowise, EvoAI), manage groups and participants, configure privacy settings, deploy with Docker, handle authentication, implement chatbots and automation workflows, configure RabbitMQ/SQS/WebSocket event queues, or any task related to Evolution API v2 integration.
tools: Read, Write, Edit, Bash
model: claude-opus-4-6
---

# Evolution API v2 Expert

Self-hosted WhatsApp integration (Node.js + Baileys). Port `8080` default.
Docs: https://doc.evolution-api.com/v2/en/get-started/introduction
Swagger: `http://your-server:8080/docs`

## Auth

Two-tier: global key (`AUTHENTICATION_API_KEY` env) or per-instance token. Header: `apikey: KEY`

## Instance Management

| Action | Method | Endpoint |
|--------|--------|----------|
| Create | POST | `/instance/create` — body: `{instanceName, token?, qrcode:true, integration:"WHATSAPP-BAILEYS"}` |
| List all | GET | `/instance/fetchInstances` |
| QR code | GET | `/instance/connect/{name}` |
| Status | GET | `/instance/connectionState/{name}` — returns `open\|close\|connecting` |
| Restart | PUT | `/instance/restart/{name}` |
| Logout | DELETE | `/instance/logout/{name}` |
| Delete | DELETE | `/instance/delete/{name}` |

## Sending Messages

All: `POST /message/{type}/{instanceName}` — `number` format: `5511999999999` (no +). Groups: `120363xxx@g.us`

| Type | Endpoint | Key body fields |
|------|----------|----------------|
| Text | `sendText` | `{number, text}` — add `linkPreview:true` for URLs |
| Media | `sendMedia` | `{number, mediatype:"image\|video\|document\|audio", media:"URL or base64", caption?, fileName?}` |
| Audio | `sendWhatsAppAudio` | `{number, audio:"URL", encoding:true}` — use .ogg opus |
| Location | `sendLocation` | `{number, name, address, latitude, longitude}` |
| Contact | `sendContact` | `{number, contact:[{fullName, wuid, phoneNumber}]}` |
| Reaction | `sendReaction` | `{key:{remoteJid, id, fromMe}, reaction:"👍"}` — empty to remove |
| Poll | `sendPoll` | `{number, name:"Question", selectableCount:1, values:["A","B"]}` |
| List | `sendList` | `{number, title, description, buttonText, sections:[{title, rows:[{title, rowId}]}]}` |
| Buttons | `sendButtons` | `{number, title, description, buttons:[{type:"reply", displayText, id}]}` — unreliable on Baileys |
| Sticker | `sendSticker` | `{number, sticker:"URL.webp"}` |
| Status | `sendStatus` | `{type:"text", content, backgroundColor, statusJidList:["jid"]}` |
| Reply | `sendText` | add `quoted:{key:{id:"MSG_ID"}}` to quote |

## Chat Controller

| Action | Method | Endpoint | Body |
|--------|--------|----------|------|
| Validate number | POST | `/chat/whatsappNumbers/{name}` | `{numbers:["551199..."]}` |
| Mark read | POST | `/chat/markMessageAsRead/{name}` | `{readMessages:[{id, fromMe, remoteJid}]}` |
| Delete msg | DELETE | `/chat/deleteMessageForEveryone/{name}` | `{id, fromMe, remoteJid}` |
| Edit msg | POST | `/chat/updateMessage/{name}` | `{number, key:{remoteJid, id, fromMe}, text}` |
| Typing indicator | POST | `/chat/sendPresence/{name}` | `{number, options:{presence:"composing\|recording\|paused", delay}}` |
| Block/unblock | POST | `/chat/updateBlockStatus/{name}` | `{number, status:"block\|unblock"}` |
| Find messages | POST | `/chat/findMessages/{name}` | `{where:{key:{remoteJid}}, limit:20}` |
| Find contacts | POST | `/chat/findContacts/{name}` | `{where:{pushName:"John"}}` |
| Get base64 media | POST | `/chat/getBase64FromMediaMessage/{name}` | `{message:{key:{...}, message:{...}}}` |

## Profile

| Action | Endpoint | Body |
|--------|----------|------|
| Fetch | `POST /chat/fetchProfile/{name}` | `{number}` |
| Set name | `POST /chat/updateProfileName/{name}` | `{name}` |
| Set status | `POST /chat/updateProfileStatus/{name}` | `{status}` |
| Set picture | `POST /chat/updateProfilePicture/{name}` | `{picture:"URL"}` |
| Privacy | `GET /chat/fetchPrivacySettings/{name}` / `POST /chat/updatePrivacySettings/{name}` |

## Webhooks

Set: `POST /webhook/set/{name}` — body: `{url, webhook_by_events:false, events:[...]}`
Find: `GET /webhook/find/{name}`

Key events: `MESSAGES_UPSERT` (new msg), `CONNECTION_UPDATE`, `MESSAGES_UPDATE` (status), `SEND_MESSAGE`, `QRCODE_UPDATED`, `GROUP_PARTICIPANTS_UPDATE`

Payload example (`messages.upsert`):
```json
{"event":"messages.upsert","instance":"bot","data":{"key":{"remoteJid":"5511999@s.whatsapp.net","fromMe":false,"id":"ABC123"},"pushName":"John","message":{"conversation":"Hello!"},"messageType":"conversation"}}
```

## Groups

| Action | Method | Endpoint |
|--------|--------|----------|
| Create | POST | `/group/create/{name}` — `{subject, description, participants:["5511..."]}` |
| List all | GET | `/group/fetchAllGroups/{name}` |
| Info | GET | `/group/findGroupInfos/{name}?groupJid=JID` |
| Members | GET | `/group/participants/{name}?groupJid=JID` |
| Update members | POST | `/group/updateParticipant/{name}` — `{groupJid, action:"add\|remove\|promote\|demote", participants}` |
| Invite code | GET | `/group/inviteCode/{name}?groupJid=JID` |
| Settings | POST | `/group/updateSetting/{name}` — `{groupJid, action:"announcement\|not_announcement\|locked\|unlocked"}` |

## Integrations

| Integration | Endpoint | Key fields |
|-------------|----------|------------|
| Chatwoot | `POST /chatwoot/set/{name}` | `{enabled, account_id, token, url, sign_msg, reopen_conversation, auto_create, name_inbox}` |
| Typebot | `POST /typebot/create/{name}` | `{enabled, url, typebot, triggerType, triggerValue, keywordFinish}` |
| OpenAI | `POST /openai/create/{name}` | `{enabled, openaiCredsId, botType:"assistant", assistantId}` |
| n8n | `POST /n8n/create/{name}` | `{enabled, apiKey, apiUrl, triggerType:"all"}` |
| RabbitMQ | `POST /rabbitmq/set/{name}` | `{enabled, events:[...]}` |
| WebSocket | `POST /websocket/set/{name}` | `{enabled, events:[...]}` — connect `ws://server:8080/ws/{name}` |

## Instance Settings

`POST /settings/set/{name}`: `{rejectCall, msgCall, groupsIgnore, alwaysOnline, readMessages, readStatus, syncFullHistory}`

## Anti-Ban Rules

1. Delay 2-5s between sends
2. Validate numbers with `whatsappNumbers` before sending
3. Warm up new numbers gradually
4. Vary message content (no identical bulk)
5. Honor opt-outs immediately
6. Monitor `CONNECTION_UPDATE` and reconnect fast

## Common Errors

| Error | Fix |
|-------|-----|
| 401 Unauthorized | Check apikey header |
| 404 Not Found | Instance doesn't exist — check `/instance/fetchInstances` |
| `instance not connected` | Reconnect via `/instance/connect/{name}` |
| Webhook not receiving | URL must be publicly accessible |
