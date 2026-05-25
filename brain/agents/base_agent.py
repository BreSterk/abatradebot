import anthropic
import logging
import json
from config import settings

logger = logging.getLogger(__name__)

class BaseAgent:
    def __init__(self, name: str, temperature: float):
        self.name = name
        self.temperature = temperature
        self.client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

    def load_prompt(self, prompt_file: str) -> str:
        try:
            with open(f"prompts/{prompt_file}", "r") as f:
                return f.read()
        except FileNotFoundError:
            logger.error(f"Prompt dosyası bulunamadı: {prompt_file}")
            return ""

    def call_claude(self, system_prompt: str, user_message: str) -> str:
        try:
            response = self.client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=1000,
                temperature=self.temperature,
                system=system_prompt,
                messages=[
                    {"role": "user", "content": user_message}
                ]
            )
            return response.content[0].text
        except Exception as e:
            logger.error(f"{self.name} Claude hatası: {e}")
            return ""

    def analyze(self, ticker: str, signals: list, context: dict = {}) -> dict:
        raise NotImplementedError