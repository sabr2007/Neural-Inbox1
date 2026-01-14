# neural-inbox1/src/ai/router.py
# Intention Classifier (КЛЮЧЕВОЙ)
"""AI Router - routes user inputs to appropriate handlers."""
import json
import logging
from enum import Enum
from dataclasses import dataclass
from typing import Optional

from openai import AsyncOpenAI
from src.config import config

logger = logging.getLogger(__name__)


class Intent(str, Enum):
    SAVE = "save"
    QUERY = "query"
    ACTION = "action"
    CHAT = "chat"
    UNCLEAR = "unclear"


@dataclass
class RouterResult:
    intent: Intent
    confidence: float
    reasoning: str
    raw_response: Optional[str] = None


ROUTER_SYSTEM_PROMPT = """Определи намерение пользователя. Ответь ТОЛЬКО JSON:

{
  "intent": "save|query|action|chat|unclear",
  "confidence": 0.0-1.0,
  "reasoning": "почему так решил"
}

ПРАВИЛА:
- SAVE: новая информация, задача, идея, файл, ссылка
- QUERY: вопрос, поиск записей, "что там было", "покажи", "найди"
- ACTION: изменить, удалить, отметить выполненным, создать проект, показать/список проектов, добавить в проект
- CHAT: приветствие, благодарность, small talk
- UNCLEAR: если confidence < 0.7

ВАЖНО: Запросы о ПРОЕКТАХ (не записях) всегда ACTION:
- "какие проекты" / "мои проекты" / "список проектов" → action
- "создай проект" / "добавь в проект" → action

ПРИМЕРЫ:
"купить молоко" → save
"что купить?" → query
"удали задачу про молоко" → action
"Создай проект" → action
"какие у меня проекты?" → action
"мои проекты" → action
"добавь задачу в проект Ремонт" → action
"спасибо" → chat
"поиск сотрудников" → unclear"""


class IntentRouter:
    def __init__(self):
        self.client = AsyncOpenAI(api_key=config.openai.api_key)
        self.model = config.openai.model

    async def classify(self, text: str, context: Optional[str] = None) -> RouterResult:
        messages = [{"role": "system", "content": ROUTER_SYSTEM_PROMPT}]

        if context:
            messages.append({"role": "user", "content": f"Контекст:\n{context}\n\nСообщение:\n{text}"})
        else:
            messages.append({"role": "user", "content": text})

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.1,
                max_tokens=200,
                response_format={"type": "json_object"}
            )

            raw_content = response.choices[0].message.content
            result = json.loads(raw_content)

            intent = Intent(result.get("intent", "unclear"))
            confidence = float(result.get("confidence", 0.5))

            if confidence < 0.7:
                intent = Intent.UNCLEAR

            return RouterResult(
                intent=intent,
                confidence=confidence,
                reasoning=result.get("reasoning", ""),
                raw_response=raw_content
            )
        except Exception as e:
            logger.error(f"Router error: {e}")
            return RouterResult(intent=Intent.UNCLEAR, confidence=0.0, reasoning=str(e))

    async def classify_with_clarification(self, text: str, context: Optional[str] = None) -> tuple[RouterResult, Optional[str]]:
        result = await self.classify(text, context)
        if result.intent == Intent.UNCLEAR:
            return result, "Сохранить это или найти в записях?"
        return result, None


router = IntentRouter()
