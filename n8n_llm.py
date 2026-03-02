"""
Custom LLM that delegates to the n8n HR Bot workflow.

PR 1: Stub — returns hardcoded text.
PR 3: Real — POSTs to n8n webhook and parses response.
"""

from __future__ import annotations

import logging
from typing import Any

from livekit.agents import llm

logger = logging.getLogger("n8n-llm")


class N8nHRBotLLM(llm.LLM):
    """
    Custom LLM that replaces the normal LLM step with an HTTP call
    to the n8n HR Bot webhook.

    The n8n workflow is the "brain" — it manages conversation state,
    question routing, LLM parsing, and flag logic. This class is a
    thin adapter that:
      1. Extracts the latest user transcript from ChatContext
      2. POSTs {session_id, user_message} to n8n
      3. Emits response_text as a ChatChunk for TTS
      4. Stores metadata (current_question, flags, etc.) for the frontend
    """

    def __init__(
        self,
        *,
        session_id: str,
        webhook_url: str,
        room: Any = None,  # livekit.rtc.Room — for data channel publishing (PR 5)
    ):
        super().__init__()
        self._session_id = session_id
        self._webhook_url = webhook_url
        self._room = room

        # Metadata from the last n8n response (published to frontend in PR 5)
        self.current_question: str = "intro"
        self.flags: list[str] = []
        self.answers: dict = {}
        self.summary_report: dict | None = None
        self._turn_count: int = 0

    def chat(
        self,
        *,
        chat_ctx: llm.ChatContext,
        tools: list | None = None,
        **kwargs,
    ) -> "N8nLLMStream":
        return N8nLLMStream(self, chat_ctx)


class N8nLLMStream(llm.LLMStream):
    def __init__(self, llm_instance: N8nHRBotLLM, chat_ctx: llm.ChatContext):
        super().__init__(llm_instance, chat_ctx=chat_ctx, tools=[])
        self._n8n = llm_instance

    async def _run(self):
        self._n8n._turn_count += 1
        turn = self._n8n._turn_count

        # --- Extract latest user message from ChatContext ---
        user_message = ""
        for item in reversed(self._chat_ctx.items):
            if hasattr(item, "role") and item.role == "user":
                if hasattr(item, "content") and isinstance(item.content, str):
                    user_message = item.content
                    break

        logger.info(
            f"Turn {turn} | session={self._n8n._session_id} | "
            f"question={self._n8n.current_question} | "
            f"user_message={user_message[:80]!r}"
        )

        # =====================================================
        # STUB (PR 1) — Replace with real n8n call in PR 3
        # =====================================================
        if turn == 1:
            response_text = (
                "Hi there! I'm an AI assistant calling about an exciting "
                "opportunity. This is a stub response — the real n8n integration "
                "comes in PR three. How are you today?"
            )
            self._n8n.current_question = "Q1"
        else:
            response_text = (
                f"I heard you say: {user_message[:100]}. "
                "This is still the stub. N8n integration is coming in PR three. "
                "Tell me more!"
            )
        # =====================================================

        # Emit response as a single ChatChunk → pipeline feeds to TTS
        self._event_ch.send_nowait(
            llm.ChatChunk(
                id=f"n8n-turn-{turn}",
                delta=llm.ChoiceDelta(role="assistant", content=response_text),
            )
        )

        logger.info(
            f"Turn {turn} | response={response_text[:80]!r} | "
            f"next_question={self._n8n.current_question}"
        )
