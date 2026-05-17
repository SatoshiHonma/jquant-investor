"""
GeminiClient: Gemini APIを叩くだけのステートレスなラッパー。
状態管理は一切しない。Sessionクラスが会話履歴を渡してくる。
"""

import os
import logging
from google import genai
from google.genai import types
from tenacity import retry, stop_after_attempt, wait_exponential
from src.agent.prompt import SYSTEM_PROMPT

logger = logging.getLogger(__name__)


class GeminiClient:
    DEFAULT_MODEL = "gemini-2.5-flash"

    def __init__(self, persona: str = ""):
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY is not set in .env")

        self.model = os.getenv("GEMINI_MODEL", self.DEFAULT_MODEL)
        self.client = genai.Client(api_key=api_key)
        self.system_instruction = f"{SYSTEM_PROMPT}\n\nペルソナ:\n{persona}" if persona else SYSTEM_PROMPT
        logger.info(f"Using model: {self.model}")

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=30, max=90), reraise=True)
    def generate(self, conversation: list[dict]) -> str:
        """
        会話履歴を受け取り、Geminiの応答テキストを返す。
        会話の管理は呼び出し元（Session）の責務。
        """
        contents = [
            types.Content(role=msg["role"], parts=[types.Part(text=msg["parts"])])
            for msg in conversation
        ]

        response = self.client.models.generate_content(
            model=self.model,
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=self.system_instruction,
                temperature=0.7,
            ),
        )
        return response.text
