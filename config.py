"""Centralized configuration loaded from environment variables."""

import os
from dotenv import load_dotenv

load_dotenv(dotenv_path=".env.local")
load_dotenv()  # fallback to .env

# LiveKit
LIVEKIT_URL = os.environ.get("LIVEKIT_URL", "")
LIVEKIT_API_KEY = os.environ.get("LIVEKIT_API_KEY", "")
LIVEKIT_API_SECRET = os.environ.get("LIVEKIT_API_SECRET", "")

# ElevenLabs
ELEVEN_API_KEY = os.environ.get("ELEVEN_API_KEY", "")
ELEVENLABS_VOICE_ID = "gJx1vCzNCD1EQHT212Ls"          # Production voice
ELEVENLABS_TTS_MODEL = "eleven_flash_v2_5"              # Lowest latency
ELEVENLABS_STT_MODEL = "scribe_v2_realtime"             # Streaming STT

# n8n
N8N_WEBHOOK_URL = os.environ.get(
    "N8N_WEBHOOK_URL",
    "https://lallu-lalla-123.app.n8n.cloud/webhook/hr-bot",
)
