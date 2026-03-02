# HR Voice Bot — LiveKit Voice Agent

An AI-powered HR screening voice bot built on [LiveKit Agents](https://docs.livekit.io/agents/) and [n8n](https://n8n.io/). The agent conducts phone interviews over WebRTC — LiveKit handles real-time voice I/O (VAD, STT, TTS), while an n8n workflow manages the interview logic, question routing, and candidate state in Supabase.

## Prerequisites

- Python 3.11+
- A [LiveKit Cloud](https://cloud.livekit.io/) account (or self-hosted LiveKit server)
- An [ElevenLabs](https://elevenlabs.io/) API key
- An n8n workflow with the HR Bot webhook (used starting PR 3)

## Setup

```bash
# Clone the repo
git clone https://github.com/ps-pro/Voice-Agent-Prototype.git
cd Voice-Agent-Prototype

# Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
# .venv\Scripts\activate   # Windows

# Install dependencies
pip install -r requirements.txt

# Copy the env template and fill in your keys
cp .env.example .env.local
# Edit .env.local with your LiveKit, ElevenLabs, and n8n credentials
```

## Running

### Console mode (local terminal test — no frontend needed)

```bash
python agent.py console
```

Speak into your microphone; the agent responds through your speakers. This is the primary testing mode for early PRs.

### Development mode (connects to LiveKit Cloud)

```bash
python agent.py dev
```

The agent registers with LiveKit Cloud and waits for a participant to join a room. Requires a valid `LIVEKIT_URL`, `LIVEKIT_API_KEY`, and `LIVEKIT_API_SECRET` in `.env.local`.

## Architecture

```
Browser/Phone ←→ LiveKit Cloud ←→ Python Agent ←→ n8n Workflow ←→ Supabase
                   (WebRTC)       (VAD+STT+TTS)   (Interview Brain)  (State)
```

- **LiveKit Agent** — Handles voice activity detection (Silero VAD), speech-to-text (ElevenLabs Scribe v2), text-to-speech (ElevenLabs Flash v2.5), and turn detection.
- **N8nHRBotLLM** — A custom `llm.LLM` subclass that replaces the normal LLM step with an HTTP call to the n8n webhook. The n8n workflow manages all conversation state, question branching, flag logic, and LLM parsing.
- **React Frontend** (PR 5) — Connects to the LiveKit room, streams audio, and displays interview metadata via data channels.
- **Token Server** (PR 6) — FastAPI endpoint for generating LiveKit room JWTs.

## Project Structure

```
├── agent.py              # Main entrypoint — AgentSession + HRScreeningAgent
├── n8n_llm.py            # Custom LLM class (stub in PR 1, real in PR 3)
├── config.py             # Centralized config from env vars
├── requirements.txt      # Pinned dependencies
├── .env.example          # Template for required env vars
├── PROGRESS.md           # Full project tracking and PR details
└── README.md             # This file
```

## PR Status

See [PROGRESS.md](PROGRESS.md) for detailed tracking of all 6 PRs, architecture decisions, and technical reference.

| PR | Title | Status |
|----|-------|--------|
| 1 | Project Scaffold + Agent Skeleton | In Progress |
| 2 | STT + TTS Verification | Not Started |
| 3 | n8n Integration (The Brain) | Not Started |
| 4 | n8n Webhook Modification | Not Started |
| 5 | React Frontend | Not Started |
| 6 | Token Server + Deployment | Not Started |
