"""
HR Voice Bot — LiveKit Voice Agent

Entrypoint for the LiveKit agent that conducts HR screening interviews.
The agent uses:
  - Silero VAD for voice activity detection
  - ElevenLabs Scribe v2 (realtime) for STT
  - N8nHRBotLLM (custom) as the "LLM" — delegates to n8n workflow
  - ElevenLabs Flash v2.5 for TTS

Run:
  python agent.py dev       # Development (connects to LiveKit Cloud)
  python agent.py console   # Local terminal test (no frontend needed)
"""

import logging
import uuid
from dotenv import load_dotenv

from livekit.agents import (
    Agent,
    AgentSession,
    JobContext,
    JobProcess,
    RoomOutputOptions,
    WorkerOptions,
    cli,
)
from livekit.plugins import elevenlabs, silero
from livekit.plugins.turn_detector.multilingual import MultilingualModel

from n8n_llm import N8nHRBotLLM
import config

load_dotenv(dotenv_path=".env.local")
load_dotenv()

logger = logging.getLogger("hr-voice-agent")
logger.setLevel(logging.INFO)


class HRScreeningAgent(Agent):
    """
    The Agent subclass for HR screening interviews.

    - on_enter(): Triggers the intro greeting (first n8n call, no user audio)
    """

    def __init__(self):
        super().__init__(
            instructions=(
                "You are an AI HR screening assistant conducting a phone interview. "
                "Keep responses natural and conversational. "
                "Do not use markdown, bullet points, or special characters. "
                "Spell out all numbers as words."
            )
        )

    async def on_enter(self):
        """Called when the agent joins the room. Triggers the intro greeting."""
        self.session.generate_reply(
            instructions="Greet the candidate and begin the screening interview."
        )


def prewarm(proc: JobProcess):
    """Pre-load heavy models once per worker process."""
    proc.userdata["vad"] = silero.VAD.load()
    logger.info("VAD model pre-loaded")


async def entrypoint(ctx: JobContext):
    """Per-room entrypoint. Creates session and starts the agent."""
    await ctx.connect()
    logger.info(f"Connected to room: {ctx.room.name}")

    # Generate a unique session ID for this interview
    # In production, this could come from room metadata or a query param
    session_id = f"lk-{uuid.uuid4().hex[:8]}"
    logger.info(f"Session ID: {session_id}")

    # --- STT: ElevenLabs Scribe v2 Realtime ---
    stt = elevenlabs.STT(
        model_id=config.ELEVENLABS_STT_MODEL,
        language_code="en",
        tag_audio_events=False,  # No "(laughter)" tags — cleaner for LLM parsing
    )

    # --- TTS: ElevenLabs Flash v2.5 ---
    tts = elevenlabs.TTS(
        voice_id=config.ELEVENLABS_VOICE_ID,
        model=config.ELEVENLABS_TTS_MODEL,
        language="en",
        auto_mode=True,
        voice_settings=elevenlabs.VoiceSettings(
            stability=0.7,
            similarity_boost=0.75,
            style=0.0,
            use_speaker_boost=True,
        ),
    )

    # --- LLM: Custom n8n webhook adapter ---
    n8n_llm = N8nHRBotLLM(
        session_id=session_id,
        webhook_url=config.N8N_WEBHOOK_URL,
        room=ctx.room,  # For data channel publishing in PR 5
    )

    # --- Assemble the session ---
    session = AgentSession(
        stt=stt,
        llm=n8n_llm,
        tts=tts,
        vad=ctx.proc.userdata["vad"],
        turn_detection=MultilingualModel(),
    )

    await session.start(
        agent=HRScreeningAgent(),
        room=ctx.room,
        room_output_options=RoomOutputOptions(transcription_enabled=True),
    )

    logger.info("Agent session started — waiting for candidate")


if __name__ == "__main__":
    cli.run_app(
        WorkerOptions(
            entrypoint_fnc=entrypoint,
            prewarm_fnc=prewarm,
        )
    )
