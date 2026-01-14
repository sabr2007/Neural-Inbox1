# neural-inbox1/src/ai/extractor.py
# Извлечение entities + даты
"""Entity Extractor - extracts structured data from messages."""
import json
import logging
from datetime import datetime
from dataclasses import dataclass, field
from typing import Optional, List
from zoneinfo import ZoneInfo

from openai import AsyncOpenAI
from src.config import config

logger = logging.getLogger(__name__)

DEFAULT_TIMEZONE = "Asia/Almaty"


@dataclass
class ExtractionResult:
    """Результат извлечения сущностей из текста."""
    title: str
    due_at: Optional[datetime] = None
    due_at_iso: Optional[str] = None
    due_at_raw: Optional[str] = None
    people: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)


EXTRACTOR_PROMPT = """Ты — помощник для извлечения структурированных данных из сообщений.

Проанализируй текст и извлеки:
1. title — краткая суть (что нужно сделать/запомнить), 3-7 слов
2. due_at_iso — дата и время в формате ISO 8601 (если указаны)
3. due_at_raw — оригинальный текст даты/времени из сообщения
4. people — список упомянутых людей (имена)
5. tags — релевантные теги (без #, на русском)

ВАЖНО для дат:
- Сейчас: {current_datetime}
- Часовой пояс: {timezone}
- "завтра" = следующий день от текущей даты
- "через час" = текущее время + 1 час
- "в 15:00" без даты = сегодня в 15:00 (или завтра, если время уже прошло)
- Всегда возвращай due_at_iso с учётом часового пояса

Ответь ТОЛЬКО валидным JSON:
{{
  "title": "краткое название задачи",
  "due_at_iso": "2024-01-15T15:00:00+05:00 или null",
  "due_at_raw": "завтра в 15:00 или null",
  "people": ["Иван", "Мария"],
  "tags": ["работа", "важное"]
}}

Если даты нет — due_at_iso и due_at_raw = null.
Если людей нет — пустой список.
Придумай 1-3 релевантных тега по контексту."""


class EntityExtractor:
    """Извлекает структурированные данные из текста сообщений."""

    def __init__(self):
        self.client = AsyncOpenAI(api_key=config.openai.api_key)
        self.model = config.openai.model

    async def extract(
        self,
        text: str,
        timezone: str = DEFAULT_TIMEZONE
    ) -> ExtractionResult:
        """
        Извлекает сущности из текста.

        Args:
            text: Текст сообщения для анализа
            timezone: Часовой пояс пользователя (например, 'Asia/Almaty')
                      Используется для корректного расчёта относительных дат

        Returns:
            ExtractionResult с извлечёнными данными
        """
        try:
            tz = ZoneInfo(timezone)
        except Exception:
            logger.warning(f"Invalid timezone '{timezone}', using default")
            tz = ZoneInfo(DEFAULT_TIMEZONE)
            timezone = DEFAULT_TIMEZONE

        now = datetime.now(tz)
        current_datetime = now.strftime("%Y-%m-%d %H:%M:%S %Z")

        prompt = EXTRACTOR_PROMPT.format(
            current_datetime=current_datetime,
            timezone=timezone
        )

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": text}
                ],
                temperature=0.1,
                max_tokens=500,
                response_format={"type": "json_object"}
            )

            result = json.loads(response.choices[0].message.content)
            return self._parse_result(result, text, tz)

        except Exception as e:
            logger.error(f"Extraction error: {e}")
            return self._fallback(text)

    def _parse_result(
        self,
        result: dict,
        original_text: str,
        tz: ZoneInfo
    ) -> ExtractionResult:
        """Парсит JSON-ответ от модели."""
        due_at = None
        due_at_iso = result.get("due_at_iso")

        if due_at_iso:
            try:
                due_at = datetime.fromisoformat(due_at_iso)
                if due_at.tzinfo is None:
                    due_at = due_at.replace(tzinfo=tz)
            except (ValueError, TypeError) as e:
                logger.warning(f"Failed to parse due_at_iso '{due_at_iso}': {e}")
                due_at_iso = None

        people = result.get("people", [])
        if not isinstance(people, list):
            people = []

        tags = result.get("tags", [])
        if not isinstance(tags, list):
            tags = []
        tags = [str(t).lstrip("#") for t in tags if t]

        return ExtractionResult(
            title=result.get("title") or original_text[:100],
            due_at=due_at,
            due_at_iso=due_at_iso,
            due_at_raw=result.get("due_at_raw"),
            people=people,
            tags=tags
        )

    def _fallback(self, text: str) -> ExtractionResult:
        """Возвращает базовый результат при ошибке API."""
        return ExtractionResult(
            title=text[:100] if len(text) > 100 else text,
            people=[],
            tags=[]
        )
