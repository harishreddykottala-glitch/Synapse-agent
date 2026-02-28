"""LLM Provider abstraction for Synapse Agent.

Supports:
- Google Gemini via google-genai SDK
- Ollama via OpenAI-compatible API (local, no rate limits)
- Groq via OpenAI-compatible API

Includes retry logic with exponential backoff for rate limits.
"""

import asyncio
import json
import logging
import os

import aiohttp
import json_repair

logger = logging.getLogger(__name__)

# Retry settings for rate limiting
MAX_RETRIES = 5
BASE_DELAY = 2.0  # seconds


class LLMProvider:
    """Unified LLM interface supporting Gemini, Ollama, and Groq."""

    def __init__(self, model: str = None, api_key: str = None, provider: str = None):
        self.provider = provider or os.getenv("LLM_PROVIDER", "ollama")
        self.model = model or os.getenv("LLM_MODEL", "llama3.2")
        self.api_key = api_key or os.getenv("GOOGLE_API_KEY", "")
        self.ollama_base = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        self.groq_api_key = os.getenv("GROQ_API_KEY", "")

        # Only import google genai if using gemini
        self._gemini_client = None

    def _get_gemini_client(self):
        if self._gemini_client is None:
            from google import genai
            self._gemini_client = genai.Client(api_key=self.api_key)
        return self._gemini_client

    async def chat(
        self,
        messages: list[dict],
        temperature: float = 0.3,
        response_format: str = None,
    ) -> str:
        """Send a chat completion request and return the response text."""
        if self.provider == "ollama":
            return await self._chat_ollama(messages, temperature, response_format)
        elif self.provider == "groq":
            return await self._chat_openai_compatible(
                messages, temperature, response_format,
                base_url="https://api.groq.com/openai/v1",
                api_key=self.groq_api_key,
            )
        else:
            return await self._chat_gemini(messages, temperature, response_format)

    # ═══════════════════════════════════════
    # Ollama (local, no rate limits!)
    # ═══════════════════════════════════════

    async def _chat_ollama(
        self, messages: list[dict], temperature: float, response_format: str
    ) -> str:
        """Chat via Ollama's OpenAI-compatible API."""
        url = f"{self.ollama_base}/api/chat"
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": {"temperature": temperature},
        }
        if response_format == "json":
            payload["format"] = "json"

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url, json=payload, timeout=aiohttp.ClientTimeout(total=300)
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return data.get("message", {}).get("content", "")
                    else:
                        error_text = await resp.text()
                        raise Exception(f"Ollama error {resp.status}: {error_text}")
        except aiohttp.ClientConnectorError:
            raise Exception(
                "Cannot connect to Ollama. Make sure it's running: 'ollama serve'\n"
                "Install from https://ollama.com and pull a model: 'ollama pull llama3.2'"
            )

    # ═══════════════════════════════════════
    # OpenAI-compatible (Groq, etc.)
    # ═══════════════════════════════════════

    async def _chat_openai_compatible(
        self, messages: list[dict], temperature: float, response_format: str,
        base_url: str = "", api_key: str = "",
    ) -> str:
        """Chat via OpenAI-compatible API (Groq, etc.)."""
        url = f"{base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
        }
        if response_format == "json":
            payload["response_format"] = {"type": "json_object"}

        last_error = None
        for attempt in range(MAX_RETRIES):
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        url, json=payload, headers=headers,
                        timeout=aiohttp.ClientTimeout(total=60),
                    ) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            return data["choices"][0]["message"]["content"]
                        elif resp.status == 429:
                            delay = BASE_DELAY * (2 ** attempt)
                            logger.warning(f"Rate limited (attempt {attempt+1}/{MAX_RETRIES}). Waiting {delay:.0f}s...")
                            await asyncio.sleep(delay)
                            last_error = Exception(f"Rate limited: {await resp.text()}")
                        else:
                            raise Exception(f"API error {resp.status}: {await resp.text()}")
            except aiohttp.ClientConnectorError as e:
                raise Exception(f"Cannot connect to {base_url}: {e}")

        raise last_error or Exception("Max retries exceeded")

    # ═══════════════════════════════════════
    # Google Gemini
    # ═══════════════════════════════════════

    async def _chat_gemini(
        self, messages: list[dict], temperature: float, response_format: str
    ) -> str:
        """Chat via Google Gemini."""
        from google.genai import types

        client = self._get_gemini_client()
        contents = []
        system_instruction = None

        for msg in messages:
            role = msg["role"]
            content = msg["content"]
            if role == "system":
                system_instruction = content
            else:
                gemini_role = "user" if role == "user" else "model"
                contents.append(
                    types.Content(
                        role=gemini_role,
                        parts=[types.Part.from_text(text=content)],
                    )
                )

        config = types.GenerateContentConfig(
            temperature=temperature,
            max_output_tokens=8192,
        )
        if system_instruction:
            config.system_instruction = system_instruction
        if response_format == "json":
            config.response_mime_type = "application/json"

        last_error = None
        for attempt in range(MAX_RETRIES):
            try:
                response = await client.aio.models.generate_content(
                    model=self.model,
                    contents=contents,
                    config=config,
                )
                return response.text
            except Exception as e:
                last_error = e
                if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
                    delay = BASE_DELAY * (2 ** attempt)
                    logger.warning(f"Rate limited (attempt {attempt+1}/{MAX_RETRIES}). Waiting {delay:.0f}s...")
                    await asyncio.sleep(delay)
                else:
                    raise

        raise last_error

    # ═══════════════════════════════════════
    # JSON helper
    # ═══════════════════════════════════════

    async def chat_json(self, messages: list[dict], temperature: float = 0.3) -> dict:
        """Chat and parse the response as JSON."""
        response = await self.chat(messages, temperature=temperature, response_format="json")
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            try:
                return json_repair.loads(response)
            except Exception:
                logger.warning(f"Failed to parse JSON response: {response[:200]}...")
                return {"error": "Failed to parse LLM response", "raw": response}
