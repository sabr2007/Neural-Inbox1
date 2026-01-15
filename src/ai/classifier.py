# neural-inbox1/src/ai/classifier.py
# Классификация типа контента
"""Content Classifier - determines item type."""
import json
import logging
from datetime import datetime
from dataclasses import dataclass, field
from typing import Optional, List

from openai import AsyncOpenAI
from src.config import config

logger = logging.getLogger(__name__)


@dataclass
class ClassificationResult:
    type: str
    title: str
    due_at: Optional[datetime] = None
    due_at_raw: Optional[str] = None
    priority: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    entities: dict = field(default_factory=dict)


CLASSIFIER_PROMPT = """Проанализируй текст и определи тип. Ответь JSON:

{
  "type": "task|idea|note|resource|contact|event",
  "title": "краткое название",
  "due_at_raw": "текст даты если есть",
  "due_at_iso": "ISO дата если есть",
  "priority": "high|medium|low|null",
  "tags": ["#тег1"],
  "entities": {"people": [], "urls": [], "phones": [], "places": []}
}

ТИПЫ:
- task: требует действия (купить, сделать, позвонить)
- idea: мысль на будущее (идея:, а что если)
- note: справочная информация
- resource: ссылка/файл
- contact: человек с контактами
- event: событие с датой/временем

ОПРЕДЕЛЕНИЕ ВРЕМЕНИ ПО КОНТЕКСТУ:
Если дата указана, но время НЕ указано явно, определи время по типу задачи:
- встреча, созвон, митинг, звонок → 10:00
- обед, ланч → 13:00
- купить, забрать, заехать, магазин → 18:00
- сдать, дедлайн, отчёт, документы → 23:59
- напомни, не забыть, напоминание → 09:00
- по умолчанию → 12:00

Сегодня: {today}"""


class ContentClassifier:
    def __init__(self):
        self.client = AsyncOpenAI(api_key=config.openai.api_key)
        self.model = config.openai.model

    async def classify(self, text: str) -> ClassificationResult:
        today = datetime.now().strftime("%Y-%m-%d")
        prompt = CLASSIFIER_PROMPT.replace("{today}", today)

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": text}
                ],
                temperature=0.2,
                max_tokens=500,
                response_format={"type": "json_object"}
            )

            result = json.loads(response.choices[0].message.content)

            due_at = None
            if result.get("due_at_iso"):
                try:
                    due_at = datetime.fromisoformat(result["due_at_iso"].replace("Z", "+00:00"))
                except (ValueError, TypeError):
                    pass

            return ClassificationResult(
                type=result.get("type", "note"),
                title=result.get("title", text[:100]),
                due_at=due_at,
                due_at_raw=result.get("due_at_raw"),
                priority=result.get("priority"),
                tags=result.get("tags", []),
                entities=result.get("entities", {})
            )
        except Exception as e:
            logger.error(f"Classification error: {e}")
            return self._fallback(text)

    def _fallback(self, text: str) -> ClassificationResult:
        text_lower = text.lower()

        if "http://" in text or "https://" in text:
            return ClassificationResult(type="resource", title=text[:100])

        if any(m in text_lower for m in ["идея", "а что если"]):
            return ClassificationResult(type="idea", title=text[:100])

        if any(m in text_lower for m in ["купить", "сделать", "позвонить", "завтра", "нужно"]):
            return ClassificationResult(type="task", title=text[:100])

        return ClassificationResult(type="note", title=text[:100])
