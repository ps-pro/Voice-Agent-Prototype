# HR Voice Bot — LiveKit Migration Progress

> **Last updated:** 2026-03-03
> **Owner:** Akash
> **Status:** 🟡 PR 1 — In Progress

---

## Architecture Overview

```
┌──────────────────────────────────────────────────────┐
│  LiveKit Cloud (wss://your-project.livekit.cloud)    │
│  WebRTC rooms, audio routing, agent dispatch         │
└───────────┬──────────────────────┬───────────────────┘
            │                      │
  ┌─────────▼──────────┐  ┌──────▼───────────────────┐
  │  Python Agent       │  │  React Frontend          │
  │  (livekit-agents)   │  │  (@livekit/components)   │
  │                     │  │                          │
  │  VAD: Silero        │  │  SessionProvider         │
  │  STT: ElevenLabs    │  │  useAgent() → state      │
  │    scribe_v2_rt     │  │  RoomAudioRenderer       │
  │  LLM: N8nHRBotLLM  │  │  BarVisualizer           │
  │    (custom class)   │  │  ControlBar (mic only)   │
  │  TTS: ElevenLabs    │  │                          │
  │    flash_v2_5       │  │  Data channel listener   │
  │                     │  │  for metadata (flags, Q#)│
  └─────────┬───────────┘  └──────────────────────────┘
            │
            │  HTTP POST JSON {session_id, user_message}
            ▼
  ┌─────────────────────────────────────┐
  │  n8n Workflow                       │
  │  (Modified: accepts JSON text-only) │
  │  State machine + Gemma 3 27B       │
  │  Returns: response_text,           │
  │  current_question, flags,          │
  │  answers, summary_report           │
  └─────────────────────────────────────┘

  + FastAPI Token Server (JWT generation for React clients)
```

---

## PR Tracker

| PR | Title | Status | Depends On | Notes |
|----|-------|--------|------------|-------|
| 1 | Project Scaffold + Agent Skeleton | 🟡 In Progress | — | Stub LLM, ElevenLabs STT/TTS wired, console mode testable |
| 2 | STT + TTS Verification | ⬜ Not Started | PR 1 | Verify ElevenLabs round-trip works in console mode |
| 3 | n8n Integration (The Brain) | ⬜ Not Started | PR 2 | Custom LLM calls n8n webhook, full conversation loop |
| 4 | n8n Webhook Modification | ⬜ Not Started | PR 3 | Accept JSON `{session_id, user_message}`, skip STT/TTS |
| 5 | React Frontend | ⬜ Not Started | PR 3 | LiveKit React client + data channel metadata display |
| 6 | Token Server + Deployment | ⬜ Not Started | PR 5 | FastAPI token endpoint, Docker, end-to-end testing |

---

## PR 1 — Project Scaffold + Agent Skeleton

### Objective
Create a runnable LiveKit voice agent with stub logic. Agent connects to LiveKit, uses Silero VAD + ElevenLabs STT/TTS, and includes a custom LLM class (`N8nHRBotLLM`) that returns hardcoded responses.

### Files
```
hr-voice-agent/
├── agent.py              # Main entrypoint — AgentSession + HRScreeningAgent
├── n8n_llm.py            # N8nHRBotLLM + N8nLLMStream (stub for PR1)
├── config.py             # Env var loader
├── requirements.txt      # Pinned deps
├── .env.example          # Template
├── PROGRESS.md           # This file
└── README.md             # Setup & run guide
```

### Key Decisions
- **AgentSession + Agent** pattern (v1.x) — NOT deprecated VoicePipelineAgent
- **N8nHRBotLLM** subclasses `llm.LLM`, overrides `chat()` → returns `N8nLLMStream`
- **N8nLLMStream** overrides `_run()` where the n8n HTTP call happens
- **session_id** generated as `lk-{uuid}` at room creation — passed to n8n every turn
- **ChatContext ignored** — n8n manages its own state in Supabase
- **MultilingualModel** for turn detection — critical for interview scenarios where candidates pause mid-thought
- **tag_audio_events=False** on STT — keeps transcripts clean for n8n's LLM parser
- **ElevenLabs voice_id:** `gJx1vCzNCD1EQHT212Ls` (production voice)
- **TTS model:** `eleven_flash_v2_5` (~75ms latency)
- **STT model:** `scribe_v2_realtime` (WebSocket streaming)

### Verification
- [ ] `pip install -r requirements.txt` succeeds
- [ ] `python agent.py console` runs without errors
- [ ] Agent speaks stub greeting via TTS
- [ ] Agent transcribes user speech via STT
- [ ] Agent echoes back with stub response
- [ ] No hardcoded secrets

---

## PR 2 — STT + TTS Verification

### Objective
Verify that the ElevenLabs STT and TTS pipeline works correctly end-to-end in console mode. Fix any issues with audio encoding, latency, or transcription quality.

### Scope
- Test STT accuracy with various accents and speaking speeds
- Verify TTS voice quality matches existing n8n bot
- Confirm VAD + turn detection works for interview-style conversation (long pauses between answers)
- Tune `VoiceSettings` if needed (stability, similarity_boost)
- Benchmark latency: time from end-of-speech to start-of-agent-response

### Verification
- [ ] STT accurately transcribes conversational English
- [ ] TTS voice matches the voice used in the current React app
- [ ] Turn detection doesn't cut off candidate mid-thought
- [ ] End-to-end latency is acceptable (target: <2s from end-of-speech to start-of-response)

---

## PR 3 — n8n Integration (The Brain)

### Objective
Wire `N8nHRBotLLM` to actually call the n8n webhook. Full conversation loop: user speaks → STT → transcript sent to n8n → n8n response text → TTS → agent speaks.

### What Changes
`n8n_llm.py` — Replace stub with real HTTP call:

```
_run() flow:
  1. Extract user_message from ChatContext (latest user item)
  2. POST {session_id, user_message} to N8N_WEBHOOK_URL
     - First turn: user_message = "" (intro)
     - Subsequent turns: user_message = STT transcript
  3. Parse n8n response JSON
  4. Store metadata on instance: current_question, flags, answers, summary_report
  5. Emit response_text as ChatChunk → TTS pipeline
  6. Handle edge cases: ended session, parse errors, network failures
```

### n8n Response Contract
```json
{
  "session_id": "lk-abc12345",
  "response_text": "Hi there! I'm an AI assistant calling about...",
  "current_question": "Q1",
  "flags": [],
  "answers": {},
  "summary_report": null,
  "audio_base64": "...",        // Ignored by agent (agent does own TTS)
  "audio_mime_type": "audio/mpeg"  // Ignored by agent
}
```

### Edge Cases to Handle
1. **Intro turn** — user_message is empty string, n8n returns greeting + sets Q1
2. **Ended session** — n8n returns canned "already completed" message, current_question stays "ended"
3. **Gibberish** — n8n returns reask_text, current_question stays the same (re-asks)
4. **Network error** — agent should speak a fallback "I'm having trouble connecting, one moment please" and retry
5. **JSON parse error** — log error, speak fallback message
6. **Q9 completion** — n8n returns summary_report (non-null), store it for frontend

### Request Format Decision
**For PR 3, send multipart form-data** (same as current React app) since n8n webhook hasn't been modified yet:
```
POST /webhook/hr-bot
Content-Type: multipart/form-data

session_id=lk-abc12345
(no audio_file on first call, empty user_message implied)
```

**After PR 4**, switch to JSON:
```
POST /webhook/hr-bot
Content-Type: application/json

{"session_id": "lk-abc12345", "user_message": "I'm based in Mumbai"}
```

### Verification
- [ ] Full interview loop works in console mode (intro → Q1 → ... → Q9 → ended)
- [ ] State persists across turns (n8n Supabase session works)
- [ ] Gibberish detection triggers re-ask
- [ ] Ended session returns graceful message
- [ ] Network errors don't crash the agent
- [ ] All 20 question branches are reachable

---

## PR 4 — n8n Webhook Modification

### Objective
Modify the n8n workflow to accept JSON `{session_id, user_message}` alongside the existing multipart audio path. When text is provided, skip STT and TTS nodes.

### What Changes in n8n
Add a new path after the Webhook node:

```
Webhook receives request
  → Check: is request JSON with user_message field?
    → YES (LiveKit agent path):
        - Extract session_id and user_message from JSON body
        - Skip "Forward Audio" → "ElevenLabs STT" entirely
        - Go directly to Supabase session check
        - After Process Response → Save State, skip "ElevenLabs TTS" and "Build Final Response"
        - Return text-only JSON: {session_id, response_text, current_question, flags, answers, summary_report}
    → NO (React app path):
        - Existing flow unchanged (multipart audio → STT → ... → TTS → audio_base64)
```

### Benefits
- LiveKit agent gets faster responses (no STT/TTS overhead in n8n)
- React app continues to work unchanged
- Saves ElevenLabs API calls (agent handles its own STT/TTS)

### Verification
- [ ] LiveKit agent (JSON path) gets correct text-only responses
- [ ] React app (multipart path) still works identically
- [ ] Both paths tested via curl
- [ ] Session state is consistent regardless of which path is used

### PR 3 Update After PR 4
Once n8n accepts JSON, update `n8n_llm.py` to send JSON instead of multipart:
```python
async with session.post(webhook_url, json={"session_id": sid, "user_message": msg}) as resp:
    data = await resp.json()
```

---

## PR 5 — React Frontend

### Objective
Build a LiveKit React client that connects to a room, streams voice to/from the agent, and displays interview metadata (current question, flags, progress).

### Tech Stack
- `@livekit/components-react` — SessionProvider, useAgent, RoomAudioRenderer, ControlBar, BarVisualizer
- `@livekit/components-styles` — default theme
- `livekit-client` — RoomEvent, DataPacket_Kind for data channel listening

### Key Components
1. **App.tsx** — SessionProvider + useSession with TokenSource
2. **InterviewScreen.tsx** — main UI: agent state visualizer, question progress, mic control
3. **AgentMetadata.tsx** — data channel listener for n8n metadata (current_question, flags, answers)
4. **SummaryView.tsx** — displays summary_report when interview completes

### Data Channel Contract
Agent publishes after each n8n response:
```python
await room.local_participant.publish_data(
    json.dumps({
        "type": "turn_update",
        "current_question": "Q3",
        "flags": ["LOCATION_MISMATCH_PENDING"],
        "answers": {...},
        "summary_report": null,
    }),
    reliable=True,
    topic="hr-bot-turn",
)
```

Separate topic for interview completion:
```python
# When current_question == "ended" and summary_report is not None
await room.local_participant.publish_data(
    json.dumps({"type": "interview_complete", "summary_report": {...}}),
    reliable=True,
    topic="hr-bot-ended",
)
```

React listens:
```tsx
room.on(RoomEvent.DataReceived, (payload, participant, kind, topic) => {
    if (topic === "hr-bot-turn") { /* update progress UI */ }
    if (topic === "hr-bot-ended") { /* show summary */ }
});
```

### Reconnection Safety
Agent also sets participant attributes for `current_question` so a reconnecting client knows the interview stage:
```python
await room.local_participant.set_attributes({"current_question": "Q3"})
```

### Verification
- [ ] Client connects to LiveKit room
- [ ] Audio streams bidirectionally (mic → agent, agent TTS → speakers)
- [ ] Autoplay gate handled (Start Interview button)
- [ ] Question progress updates in real-time via data channel
- [ ] Flags display correctly
- [ ] Summary report displays when interview completes
- [ ] Reconnection picks up correct interview stage

---

## PR 6 — Token Server + Deployment

### Objective
Build a FastAPI server for generating LiveKit room tokens, and prepare deployment.

### Token Server
```python
from fastapi import FastAPI, Query
from livekit.api import AccessToken, VideoGrants
import config

app = FastAPI()

@app.get("/api/token")
async def get_token(room_name: str = Query(...), participant_name: str = Query(...)):
    token = (
        AccessToken(config.LIVEKIT_API_KEY, config.LIVEKIT_API_SECRET)
        .with_identity(participant_name)
        .with_grants(VideoGrants(room_join=True, room=room_name, can_publish=True, can_subscribe=True))
        .with_ttl(timedelta(hours=1))
        .to_jwt()
    )
    return {"token": token}
```

### Deployment
- Agent: `lk agent create` (deploys to LiveKit Cloud)
- Token server: Docker container or cloud function
- React frontend: Static hosting (Vercel, Netlify, etc.)

### Verification
- [ ] Token endpoint returns valid JWT
- [ ] React client connects using token from server
- [ ] Agent auto-dispatches when client joins room
- [ ] Full end-to-end interview works: browser → LiveKit → agent → n8n → agent → browser
- [ ] Multiple concurrent interviews work (separate rooms/sessions)

---

## Technical Reference

### External Service Credentials

| Service | Key Env Var | Notes |
|---------|-------------|-------|
| LiveKit Cloud | `LIVEKIT_URL`, `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET` | WebSocket URL + API key pair |
| ElevenLabs | `ELEVEN_API_KEY` | Prefix `sk_e6f72e1...` |
| n8n Webhook | `N8N_WEBHOOK_URL` | `https://lallu-lalla-123.app.n8n.cloud/webhook/hr-bot` |
| Supabase | Managed by n8n | Table: `sessions` (session_id TEXT PK, state_json TEXT) |
| Google Sheets | Managed by n8n | Doc ID: `1Jte7LUZr7S0LINroYVmu4V_CWmiLBVqA5C0c2JeyNtE` |
| Google Gemini | Managed by n8n | Model: `gemma-3-27b-it` |

### ElevenLabs Configuration

| Setting | Value |
|---------|-------|
| TTS Voice ID | `gJx1vCzNCD1EQHT212Ls` |
| TTS Model | `eleven_flash_v2_5` |
| TTS Stability | 0.7 |
| TTS Similarity Boost | 0.75 |
| TTS Style | 0.0 |
| TTS Speaker Boost | true |
| STT Model | `scribe_v2_realtime` |
| STT Language | `en` |
| STT Tag Audio Events | false |

### n8n Webhook Contract

**Current (multipart, used by React app):**
```
POST /webhook/hr-bot (multipart/form-data)
  session_id: string (required)
  audio_file: binary (optional — absent on intro turn)
```

**New (JSON, used by LiveKit agent after PR 4):**
```
POST /webhook/hr-bot (application/json)
  {"session_id": "...", "user_message": "..."}
  (user_message is "" on intro turn)
```

**Response (both paths):**
```json
{
  "session_id": "...",
  "response_text": "...",
  "current_question": "intro|Q1|Q1B|Q2|Q2A|Q2B|Q3|Q3B|Q4|Q4B|Q5|Q5A|Q5B|Q6|Q6B|Q7|Q8|Q8B|Q9|ended",
  "flags": ["LOCATION_MISMATCH", "SKILL_GAP", "CTC_MISMATCH", "WORK_MODE_CONFLICT", "ESCALATE_FAST_TRACK"],
  "answers": {},
  "summary_report": null | {30+ field object},
  "audio_base64": "...",          // Only in multipart path
  "audio_mime_type": "audio/mpeg"  // Only in multipart path
}
```

### Question Flow Map

```
intro → Q1 (Location)
  → match: Q2
  → mismatch: Q1B (Relocation) → Q2

Q2 (Experience)
  → fresher (0-1yr): Q2A (Projects) → Q3
  → mid (1-5yr): Q3
  → senior (6+yr): Q2B (Leadership) → Q3

Q3 (Tech Stack)
  → strong/partial: Q4
  → weak: Q3B (Skill Probe) → Q4

Q4 (CTC)
  → within/below budget: Q5
  → above budget: Q4B (Flexibility) → Q5

Q5 (Notice Period)
  → immediate/short: Q5A (Availability) → Q6
  → standard: Q6
  → long: Q5B (Buyout) → Q6

Q6 (Motivation)
  → normal: Q7
  → layoff/conflict: Q6B (Sensitive Probe) → Q7

Q7 (Work Mode) → Q8

Q8 (Other Offers)
  → no: Q9
  → yes: Q8B (Decision Timeline) → Q9

Q9 (Interest Score) → ended (with summary_report)
```

### Flag Lifecycle

| Phase | Flag | Trigger |
|-------|------|---------|
| Detected | `LOCATION_MISMATCH_PENDING` | Q1: location doesn't match JD |
| Resolved | *(removed)* | Q1B: candidate willing to relocate |
| Finalized | `LOCATION_MISMATCH` | Q1B: candidate NOT willing to relocate |
| Detected | `SKILL_GAP_PENDING` | Q3: weak skill match |
| Resolved | *(removed)* | Q3B: has experience with required skill |
| Finalized | `SKILL_GAP` | Q3B: no experience with required skill |
| Detected | `CTC_MISMATCH_PENDING` | Q4: expected CTC above budget |
| Resolved | *(removed)* | Q4B: candidate is flexible |
| Finalized | `CTC_MISMATCH` | Q4B: candidate NOT flexible |
| Direct | `WORK_MODE_CONFLICT` | Q7: preference doesn't match JD |
| Direct | `ESCALATE_FAST_TRACK` | Q8B: urgent decision deadline |
| Cleanup | All `*_PENDING` removed | Q9: end of screening |

---

## Decisions Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-03-03 | Use `AgentSession` + `Agent` (not `VoicePipelineAgent`) | VoicePipelineAgent is deprecated in livekit-agents v1.x |
| 2026-03-03 | Agent owns STT/TTS (Option A) | Lower latency, eliminates base64 overhead, agent controls streaming |
| 2026-03-03 | `scribe_v2_realtime` for STT | WebSocket streaming — lower perceived latency than batch `scribe_v2` |
| 2026-03-03 | `MultilingualModel` for turn detection | Candidates pause mid-thought during interviews; simple VAD timeout would cut them off |
| 2026-03-03 | `tag_audio_events=False` | "(laughter)" tags would confuse n8n's LLM parser |
| 2026-03-03 | Data channels for metadata, participant attributes for reconnection | Data channels for per-turn updates, attributes for persistent reconnection-safe state |
| 2026-03-03 | Keep text normalization in LLM prompts | Flash v2.5 doesn't reliably handle number normalization; pre-normalize in n8n prompts |
| 2026-03-03 | Dual-path n8n webhook (PR 4) | Both React app (multipart+audio) and LiveKit agent (JSON+text) use same workflow |

---

## Known Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| LiveKit SDK breaking changes (v1.x is relatively new) | Agent code needs updates | Pin versions in requirements.txt, test thoroughly before upgrading |
| ElevenLabs `scribe_v2_realtime` accuracy vs batch `scribe_v2` | Transcription quality may differ | Test in PR 2, fall back to Deepgram STT if needed |
| Custom LLM `chat_ctx` accumulation | Memory grows over long interviews | Monitor in PR 3, clear context if needed between turns |
| n8n webhook latency (cold starts on n8n Cloud) | Slow first response | n8n Cloud keeps active workflows warm; monitor and consider n8n self-hosted if needed |
| Data channel packet loss on unreliable networks | Frontend misses metadata update | Use `reliable=True` + participant attributes as backup |
| Concurrent interviews overloading n8n | Webhook timeouts | n8n Cloud handles concurrency; monitor at scale |
