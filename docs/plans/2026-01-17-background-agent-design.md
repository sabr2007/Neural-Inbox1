# Background Intelligent Agent — Design Document

**Дата:** 2026-01-17
**Статус:** Approved
**Цель:** Переход от простого классификатора к интеллектуальному агенту-оркестратору

---

## 1. Проблемы текущей реализации

1. **One-to-Many:** 1 сообщение = 1 запись. Длинное голосовое с 3 темами создаёт одну "кашу"
2. **Dumb Assistant:** Бот не различает контент и общение. "Привет" → заметка "Привет"
3. **Слабый контекст:** Классификатор не видит историю пользователя и не понимает связи

---

## 2. Цели

| Приоритет | Цель | Описание |
|-----------|------|----------|
| 1 | Семантический поиск и связи | Related Items при открытии карточки |
| 2 | Мульти-парсинг | Атомизация: 1 сообщение → N items |
| 3 | Диалоговый режим | Умные ответы на "Привет", "Как дела?" |

---

## 3. Архитектура

```
┌─────────────────────────────────────────────────────────────────┐
│                     message.py (handler)                        │
│  1. Получает сообщение                                          │
│  2. Отвечает "⏳ Обрабатываю..."                                 │
│  3. Запускает background task → agent.process()                 │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                     agent.py (оркестратор)                      │
│                                                                 │
│  class IntelligentAgent:                                        │
│      async def process(user_id, text, source) -> AgentResult    │
│                                                                 │
│  Шаги:                                                          │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │ 1. GATHER CONTEXT (параллельно, ~200ms)                  │   │
│  │    ├─ get_user_projects(user_id) → [{id, name, emoji}]   │   │
│  │    ├─ get_recent_items(user_id, limit=20)                │   │
│  │    │   → [{id, title, type, tags, created_at}]           │   │
│  │    └─ semantic_search(text, user_id, limit=5)            │   │
│  │        → [{id, title, type, tags, score}]                │   │
│  └──────────────────────────────────────────────────────────┘   │
│                              ↓                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │ 2. ANALYZE & EXTRACT (1 LLM call, ~1-2 сек)              │   │
│  │    model = select_model(text_length, complexity)         │   │
│  │    result = await llm.analyze(text, context)             │   │
│  │    → {items: [...], chat_response: "...", links: [...]}  │   │
│  └──────────────────────────────────────────────────────────┘   │
│                              ↓                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │ 3. PERSIST & LINK (параллельно, ~500ms)                  │   │
│  │    ├─ batch_create_items(items)                          │   │
│  │    ├─ generate_embeddings(items)                         │   │
│  │    └─ create_links(items, suggested_links)               │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                     AgentResult                                 │
│  - items_created: List[Item]                                    │
│  - links_created: List[ItemLink]                                │
│  - chat_response: Optional[str]                                 │
│  - is_empty: bool  # True если items=[] и chat_response=null    │
│  - processing_time: float                                       │
└─────────────────────────────────────────────────────────────────┘
```

**Общее время:** ~2-3 секунды (лимит 4 сек)

---

## 4. Web App интеграция

### API Endpoint: GET /api/items/{id}/related

```python
@router.get("/{item_id}/related")
async def get_related_items(item_id: int, user: User = Depends(get_current_user)):
    item = await repo.get_item(item_id, user.user_id)

    # Семантически похожие (score > 0.7)
    auto_related = await search.vector_search(
        embedding=item.embedding,
        user_id=user.user_id,
        exclude_id=item_id,
        threshold=0.7,  # фильтруем мусор
        limit=10
    )

    # Явные связи от агента
    linked = await repo.get_item_links(item_id)

    return {
        "auto": [{"id": r.id, "title": r.title, "type": r.type, "score": r.score} for r in auto_related],
        "linked": [{"id": l.id, "title": l.title, "type": l.type, "reason": l.reason} for l in linked]
    }
```

### UI: Блок "Связанное"

```
┌─────────────────────────────────┐
│  📝 Идея для статьи про AI      │
│  ─────────────────────────────  │
│  Написать статью о том, как...  │
│                                 │
│  ─────────────────────────────  │
│  🔗 Связанное                   │
│                                 │
│  ┌─────────────────────────┐    │
│  │ 📚 Статья: "AI Trends"  │    │
│  │ ↳ "Обе про AI-маркетинг"│    │  ← reason от агента
│  └─────────────────────────┘    │
│                                 │
│  ┌─────────────────────────┐    │
│  │ 💡 Идея: ML для блога   │    │
│  │ ↳ 87% совпадение        │    │  ← score для auto
│  └─────────────────────────┘    │
└─────────────────────────────────┘
```

- `linked` (от агента) → показываем `reason`
- `auto` (семантические) → показываем `score` как "87% совпадение"
- Если оба пусты → блок не показываем

---

## 5. System Prompt агента

```python
AGENT_SYSTEM_PROMPT = """
Ты — Второй Мозг системы Neural Inbox. Твоя задача — структурировать хаос.

Сегодняшняя дата: {current_date}

## Твои роли:
1. **Экстрактор** — выделяй из текста атомарные сущности
2. **Линкер** — находи связи с существующими записями
3. **Собеседник** — если пользователь просто общается, поддержи диалог

## Типы контента:
- task: требует действия ("купить", "позвонить", "сделать")
- idea: концепция, мысль ("а что если", "было бы круто")
- note: информация для запоминания (факты, цитаты, конспекты)
- resource: ссылки, книги, статьи
- contact: люди, телефоны, соцсети

## Правила атомизации:
- Одна мысль = один item
- "Купить молоко и позвонить маме" = 2 задачи
- Длинное голосовое с 3 темами = 3+ отдельных items
- НЕ дроби связанные вещи (список покупок = 1 задача)

## Правила проектов:
- Сверяйся со списком projects в контексте
- Если сущность явно относится к проекту — укажи его ID
- Не угадывай, если связь неочевидна (оставь null)

## Правила связей (suggested_links):
- Связывай ТОЛЬКО если действительно релевантно
- Используй similar_items из контекста как кандидатов
- Указывай reason на русском (кратко, 3-7 слов)
- **Думай глубже:** ищи не только совпадения слов, но и скрытый смысл.
  Примеры:
  - "API интеграция" ↔ "Документация Telegram" — связь через тему разработки
  - "Купить подарок маме" ↔ "День рождения мамы 15 марта" — связь через событие
  - "Идея приложения для фитнеса" ↔ "Статья про здоровый образ жизни" — тематическая связь

## Правила диалога:
- "Привет", "Как дела?" → chat_response, items = []
- "Спасибо" → chat_response: "Всегда рад помочь!"
- Вопрос о системе → объясни что умеешь

## Формат ответа (JSON):
{
  "items": [
    {
      "type": "task|idea|note|resource|contact",
      "title": "краткое название (до 100 символов)",
      "content": "полный текст",
      "tags": ["маркетинг", "личное"],
      "project_id": 123 | null,
      "due_at_raw": "завтра в 10" | null,
      "priority": "high|medium|low" | null
    }
  ],
  "chat_response": "текст ответа" | null,
  "suggested_links": [
    {
      "new_item_index": 0,
      "existing_item_id": 123,
      "reason": "Обе задачи про маркетинг"
    }
  ]
}
"""
```

### Динамический промпт:

```python
def build_prompt(user_text: str, context: AgentContext) -> str:
    return f"""
{AGENT_SYSTEM_PROMPT.format(current_date=date.today().isoformat())}

## Контекст пользователя:

### Проекты:
{json.dumps(context.projects, ensure_ascii=False)}

### Последние записи (20):
{json.dumps(context.recent_items, ensure_ascii=False)}

### Похожие записи (кандидаты на связь):
{json.dumps(context.similar_items, ensure_ascii=False)}

## Сообщение пользователя:
{user_text}
"""
```

---

## 6. Adaptive Model Selection

```python
class ModelSelector:
    """Выбор модели на основе сложности входа."""

    FAST_MODEL = "gpt-4o-mini"   # ~1 сек, дешёвый
    SMART_MODEL = "gpt-4o"       # ~2-3 сек, умный

    LONG_TEXT_THRESHOLD = 500
    MULTI_INTENT_MARKERS = [" и ", " а также ", " плюс ", " ещё ", "\n", "во-первых", "во-вторых", "1.", "2.", "1)", "2)"]
    COMPLEX_MARKERS = ["с одной стороны", "с другой стороны", "если", "то", "потому что", "следовательно"]

    @classmethod
    def select(cls, text: str, source: str) -> str:
        # Голосовые > 2 минут — умная модель
        if source == "voice" and len(text) > 1000:
            return cls.SMART_MODEL

        # Длинный текст
        if len(text) > cls.LONG_TEXT_THRESHOLD:
            return cls.SMART_MODEL

        # Маркеры множественных интентов
        text_lower = text.lower()
        multi_intent_count = sum(1 for marker in cls.MULTI_INTENT_MARKERS if marker in text_lower)
        if multi_intent_count >= 2:
            return cls.SMART_MODEL

        # Сложная структура
        if any(marker in text_lower for marker in cls.COMPLEX_MARKERS):
            return cls.SMART_MODEL

        return cls.FAST_MODEL
```

| Input | Model | Причина |
|-------|-------|---------|
| "Купить хлеб" | mini | Короткий, простой |
| "Привет, как дела?" | mini | Диалог |
| 3-минутное голосовое | 4o | Длинное голосовое |
| "Нужно сделать А, а также Б, плюс не забыть В" | 4o | Множественные интенты |

---

## 7. Error Handling

```python
async def _process_with_agent(user_id: int, text: str, source: str, msg: Message):
    agent = IntelligentAgent()

    try:
        result = await asyncio.wait_for(
            agent.process(user_id, text, source),
            timeout=10.0
        )

        if result.is_empty:
            await bot.delete_message(msg.chat.id, msg.message_id)
        elif result.chat_response:
            await bot.edit_message_text(result.chat_response, msg.chat.id, msg.message_id)
        else:
            summary = f"✅ Создано: {len(result.items_created)} записей"
            if result.links_created:
                summary += f", {len(result.links_created)} связей"
            await bot.edit_message_text(summary, msg.chat.id, msg.message_id)

    except (asyncio.TimeoutError, AgentError, Exception) as e:
        logger.error(f"Agent failed for user {user_id}: {e}")

        # Fallback: сохраняем оригинал как note в Inbox
        await repo.create_item(
            user_id=user_id,
            type="note",
            title=text[:100] + "..." if len(text) > 100 else text,
            content=text,
            source=source,
            status="inbox"
        )

        await bot.edit_message_text(
            "⚠️ Ошибка при обработке, но я сохранил оригинал в Inbox",
            msg.chat.id,
            msg.message_id
        )
```

---

## 8. Структура файлов

```
src/
├── ai/
│   ├── agent.py              # НОВЫЙ: IntelligentAgent (оркестратор)
│   ├── model_selector.py     # НОВЫЙ: Adaptive model selection
│   ├── prompts.py            # НОВЫЙ: System prompt + builder
│   ├── classifier.py         # УДАЛИТЬ
│   ├── embeddings.py         # Без изменений
│   └── linker.py             # Расширить: create_links_batch()
│
├── api/
│   └── routes/
│       └── items.py          # ИЗМЕНИТЬ: добавить GET /{id}/related
│
├── bot/
│   └── handlers/
│       └── message.py        # ИЗМЕНИТЬ: вызывать agent вместо classifier
│
└── db/
    ├── repository.py         # ИЗМЕНИТЬ: добавить методы для контекста
    └── search.py             # Без изменений
```

---

## 9. Cleanup после внедрения

```
📋 Checklist: Проверка и очистка

src/ai/
├── classifier.py        → УДАЛИТЬ (заменён на agent.py)
├── linker.py           → ПРОВЕРИТЬ: убрать дублирующие функции
└── embeddings.py       → ПРОВЕРИТЬ: убрать неиспользуемые методы

src/bot/handlers/
└── message.py          → ПРОВЕРИТЬ: убрать старые imports и функции
                          - _classify_and_update() — удалить
                          - любые прямые вызовы classifier — удалить

src/db/
├── repository.py       → ПРОВЕРИТЬ: убрать методы только для classifier
└── models.py           → ПРОВЕРИТЬ: ItemLink.reason добавлен?

Общее:
├── Неиспользуемые imports во всех файлах
├── Закомментированный код
└── TODO/FIXME которые уже решены
```

**Команды для поиска рудиментов:**
```bash
grep -r "classifier" src/ --include="*.py"
grep -r "ContentClassifier" src/ --include="*.py"
```

---

## 10. Метрики успеха

- [ ] Время обработки < 4 сек в 95% случаев
- [ ] Мульти-парсинг работает для голосовых > 2 мин
- [ ] Related Items показывает релевантные связи (score > 0.7)
- [ ] Диалог работает для приветствий без создания items
- [ ] Fallback сохраняет оригинал при ошибках
