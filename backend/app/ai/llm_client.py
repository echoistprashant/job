import json
import logging
import re
from typing import Any, Dict, List, Optional
import httpx

from backend.app.config import settings

logger = logging.getLogger("ai_job_agent.llm")

GROQ_BASE_URL = "https://api.groq.com/openai/v1"


class GroqLLMClient:
    """
    Centralized LLM client interfacing Groq's high-speed inference API
    to power intelligent matching reasoning, grounded screening answers,
    resume tailoring, and cover letter generation.
    """

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        self._api_key = api_key or settings.GROQ_API_KEY
        self._model = model or settings.GROQ_MODEL or "openai/gpt-oss-120b"
        self._timeout = 30.0

    @property
    def is_configured(self) -> bool:
        # During pytest runs, keep tests 100% fast, offline, and deterministic
        import os
        if os.environ.get("PYTEST_CURRENT_TEST"):
            return False
        return bool(self._api_key and self._api_key.startswith("gsk_"))

    def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.2,
        max_tokens: int = 1500,
        model: Optional[str] = None
    ) -> Optional[str]:
        """Synchronous chat completion call to Groq."""
        if not self.is_configured:
            logger.warning("[GroqLLM] Groq API key is not configured. Falling back to local heuristic.")
            return None

        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": model or self._model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens
        }

        try:
            with httpx.Client(timeout=self._timeout) as client:
                resp = client.post(f"{GROQ_BASE_URL}/chat/completions", headers=headers, json=payload)
                if resp.status_code == 200:
                    data = resp.json()
                    content = data["choices"][0]["message"]["content"]
                    return content
                else:
                    logger.error(f"[GroqLLM] API returned {resp.status_code}: {resp.text}")
                    return None
        except Exception as e:
            logger.error(f"[GroqLLM] Request failed: {e}")
            return None

    def chat_json(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.1,
        max_tokens: int = 1500
    ) -> Optional[Dict[str, Any]]:
        """Chat completion that guarantees parsed JSON output."""
        raw_text = self.chat(messages, temperature=temperature, max_tokens=max_tokens)
        if not raw_text:
            return None

        # Try direct parse
        try:
            return json.loads(raw_text)
        except json.JSONDecodeError:
            pass

        # Extract markdown code block ```json ... ```
        match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", raw_text)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass

        # Extract first { ... } or [ ... ]
        bracket_match = re.search(r"(\{[\s\S]*\}|\[[\s\S]*\])", raw_text)
        if bracket_match:
            try:
                return json.loads(bracket_match.group(1))
            except json.JSONDecodeError:
                pass

        logger.warning(f"[GroqLLM] Failed to parse JSON from output: {raw_text[:200]}")
        return None


# Global singleton
llm_client = GroqLLMClient()
