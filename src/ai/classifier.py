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
  "type": "task|idea|note|resource|contact",
  "title": "краткое название",
  "due_at_raw": "текст даты если есть",
  "due_at_iso": "ISO дата если есть",
  "priority": "high|medium|low|null",
  "tags": ["#тег1"],
  "entities": {"people": [], "urls": [], "phones": [], "places": []}
}

ТИПЫ:
- task (задача): требует конкретного действия или исполнения в будущем. 
  Маркеры: глаголы в повелительном наклонении (купить, сходить, написать, скачать, сделать), наличие дедлайнов, слова "надо", "нужно", "не забыть", "написать".
  Примеры: "купить хлеб", "позвонить маме завтра", "подготовить отчет к пн", "сделать домашнее задание".

- idea (идея): гипотеза, проект или мысль, которая не требует немедленного действия, но ценна как концепт.
  Маркеры: "а что если", "идея:", "проект:", "может быть сделать", "в будущем", "хочу как нибудь".
  Примеры: "идея для приложения про котов", "а что если поехать в Исландию летом", "проект нового интерьера", "хочу как нибудь открыть стартап".

- note (заметка): любая полезная информация для хранения. Это "база знаний".
  ВАЖНО: сюда относятся черновики сообщений другим людям например ("Александр Здравствуй, я буду поздно"), учебные материалы, конспекты лекций, распознанный текст с досок, цитаты, мысли вслух без призыва к действию.
  Если сообщение выглядит как кусок разговора или справочный факт — это заметка.

- resource (ресурс): внешний источник информации.
  Маркеры: URL-ссылки, упоминание файлов (PDF, docx), скриншоты статей, списки литературы.
  Если в сообщении есть ссылка или вложение, которое нужно "посмотреть позже" — это ресурс.

- contact (контакт): данные о людях или организациях.
  Маркеры: имена, номера телефонов, адреса электронной почты, ссылки на соцсети (TG, Instagram).
  Примеры: "Иван +7999...", "Мастер по ремонту @nickname".

ОПРЕДЕЛЕНИЕ ВРЕМЕНИ ПО КОНТЕКСТУ:
Если дата указана, но время НЕ указано явно, определи время по типу задачи:
- встреча, созвон, митинг, звонок → 10:00
- обед, ланч → 13:00
- купить, забрать, заехать, магазин → 18:00
- сдать, дедлайн, отчёт, документы → 23:59
- напомни, не забыть, напоминание → 09:00
- по умолчанию → 12:00

ВАЖНО: 
1. Если сообщение — это просто приветствие, вежливость или вопрос о твоих функциях без полезной информации для сохранения, установи type: "chat".
2. Если интент не ясен, но текст несет информацию — всегда выбирай "note".

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
