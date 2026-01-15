# E2E Test Runner Design

## Overview

End-to-end тестовый скрипт для проверки полного пайплайна Neural Inbox: от входящего сообщения пользователя до результата в БД и ответа бота.

**Цель:** Автоматизировать тестирование всех функций (кроме PDF, документов, фото) чтобы быстро находить где логика хромает или LLM ошибается.

## Решения

| Вопрос | Решение |
|--------|---------|
| База данных | Текущая БД (DATABASE_URL из .env) с тестовым user_id |
| Уровень тестирования | Полный пайплайн через Handler (handle_text) |
| Формат сценариев | Явные ожидания для каждого сценария |
| Отчёты | Консоль + JSON файл |
| Очистка данных | В конце прогона |
| Подтверждения | Тестируем оба пути (confirm/cancel) |

---

## Структура файлов

```
tests/
├── e2e/
│   ├── __init__.py
│   ├── runner.py           # Основной раннер тестов
│   ├── scenarios.py        # 75 сценариев с ожиданиями
│   ├── mocks.py            # Мок Telegram Message
│   ├── assertions.py       # Проверки (DB, response)
│   └── reports/            # Папка для JSON отчётов
│       └── .gitkeep
```

**Запуск:**
```bash
python -m tests.e2e.runner
python -m tests.e2e.runner --no-cleanup --verbose
```

**Тестовый user_id:** `999999999`

---

## Структура сценариев

```python
@dataclass
class Scenario:
    id: str                              # "save_task_01"
    input: str                           # "Запомни купить молоко завтра"
    expect_intent: str                   # "save" | "query" | "action" | "chat" | "unclear"
    expect_type: str | None = None       # "task" | "idea" | "note" | ...
    expect_in_db: bool = False           # True = должен создать Item
    expect_found: int | None = None      # Для query: сколько результатов
    expect_updated: int | None = None    # Для action: сколько изменено
    expect_deleted: int | None = None    # Для action: сколько удалено
    check_title_contains: str | None = None
    check_response_contains: str | None = None
    confirm: bool | None = None          # None=не требует, True/False=ответ
    depends_on: str | None = None        # ID предыдущего сценария
    tags: list[str] = field(default_factory=list)
    forward_from: str | None = None      # Имитация пересланного сообщения
    is_followup: bool = False            # Продолжение предыдущего
```

---

## Мок Telegram Message

```python
# tests/e2e/mocks.py

TEST_USER_ID = 999999999

class MockUser:
    id = TEST_USER_ID
    first_name = "TestUser"
    username = "test_user"

class MockChat:
    id = TEST_USER_ID
    type = "private"

class MockForwardUser:
    def __init__(self, name: str):
        self.first_name = name
        self.id = random.randint(100000, 999999)

class MockMessage:
    def __init__(self, text: str, forward_from: str | None = None):
        self.text = text
        self.from_user = MockUser()
        self.chat = MockChat()
        self.message_id = random.randint(1000, 9999)
        self.date = datetime.now()
        self._replies = []

        if forward_from:
            self.forward_from = MockForwardUser(forward_from)
            self.forward_date = datetime.now()
        else:
            self.forward_from = None
            self.forward_date = None

    async def answer(self, text: str, **kwargs):
        self._replies.append(text)
        return self

    async def reply(self, text: str, **kwargs):
        self._replies.append(text)
        return self
```

---

## Runner (основной цикл)

```python
# tests/e2e/runner.py

async def run_scenario(scenario: Scenario, db_session) -> TestResult:
    # 1. Создаём мок сообщения
    message = MockMessage(scenario.input, forward_from=scenario.forward_from)

    # 2. Вызываем handler (полный пайплайн)
    await handle_text(message)

    # 3. Если требуется подтверждение — обрабатываем
    if scenario.confirm is not None:
        await continue_agent_loop(TEST_USER_ID, confirmed=scenario.confirm)

    # 4. Проверяем результаты
    result = await check_assertions(scenario, message._replies, db_session)

    return result

async def main():
    results = []

    # Setup
    db_session = await get_db_session()
    await cleanup_test_data(db_session, TEST_USER_ID)

    # Run scenarios
    for i, scenario in enumerate(SCENARIOS, 1):
        print(f"Running [{i}/{len(SCENARIOS)}] {scenario.id}...")
        result = await run_scenario(scenario, db_session)
        results.append(result)
        print_result(i, len(SCENARIOS), result)

    # Reports
    print_summary(results)
    save_json_report(results)

    # Cleanup
    await cleanup_test_data(db_session, TEST_USER_ID)
```

---

## Assertions (проверки)

```python
# tests/e2e/assertions.py

@dataclass
class TestResult:
    scenario_id: str
    passed: bool
    expected: dict
    actual: dict
    errors: list[str]
    duration_ms: int
    bot_response: str

async def check_assertions(
    scenario: Scenario,
    replies: list[str],
    db_session
) -> TestResult:
    errors = []
    actual = {}

    # 1. Проверка intent
    if scenario.expect_intent:
        actual_intent = get_last_intent(TEST_USER_ID)
        actual["intent"] = actual_intent
        if actual_intent != scenario.expect_intent:
            errors.append(f"Intent: expected '{scenario.expect_intent}', got '{actual_intent}'")

    # 2. Проверка создания в БД
    if scenario.expect_in_db:
        item = await get_latest_item(db_session, TEST_USER_ID)
        actual["created"] = item is not None
        if not item:
            errors.append("Expected item in DB, but nothing created")
        else:
            if scenario.expect_type and item.type != scenario.expect_type:
                actual["type"] = item.type
                errors.append(f"Type: expected '{scenario.expect_type}', got '{item.type}'")

            if scenario.check_title_contains:
                actual["title"] = item.title
                if scenario.check_title_contains.lower() not in item.title.lower():
                    errors.append(f"Title should contain '{scenario.check_title_contains}'")

    # 3. Проверка поиска
    if scenario.expect_found is not None:
        found_count = extract_found_count(replies)
        actual["found"] = found_count
        if found_count != scenario.expect_found:
            errors.append(f"Found: expected {scenario.expect_found}, got {found_count}")

    # 4. Проверка обновления/удаления
    if scenario.expect_deleted is not None:
        deleted = get_deleted_count(TEST_USER_ID)
        actual["deleted"] = deleted
        if deleted != scenario.expect_deleted:
            errors.append(f"Deleted: expected {scenario.expect_deleted}, got {deleted}")

    if scenario.expect_updated is not None:
        updated = get_updated_count(TEST_USER_ID)
        actual["updated"] = updated
        if updated != scenario.expect_updated:
            errors.append(f"Updated: expected {scenario.expect_updated}, got {updated}")

    # 5. Проверка ответа бота
    if scenario.check_response_contains:
        response_text = " ".join(replies)
        actual["response_snippet"] = response_text[:100]
        if scenario.check_response_contains.lower() not in response_text.lower():
            errors.append(f"Response should contain '{scenario.check_response_contains}'")

    return TestResult(
        scenario_id=scenario.id,
        passed=len(errors) == 0,
        expected={...},
        actual=actual,
        errors=errors,
        duration_ms=...,
        bot_response=" ".join(replies)
    )
```

---

## Отчёты

### Консольный вывод

```
[1/75] ✅ save_task_01
    Input: "Задача 'купить молоко' создана на завтра..."

[2/75] ❌ query_dates_01
    Input: "Вот что я нашёл..."
    → Found: expected 1, got 0

==================================================
TOTAL: 75 scenarios
PASSED: 70
FAILED: 5
==================================================

Failed scenarios:
  - query_dates_01: Found: expected 1, got 0
  - action_delete_01: Intent: expected 'action', got 'chat'

📄 JSON report saved: tests/e2e/reports/report_20250115_143022.json
```

### JSON отчёт

```python
def save_json_report(results: list[TestResult]):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"tests/e2e/reports/report_{timestamp}.json"

    report = {
        "timestamp": timestamp,
        "total": len(results),
        "passed": sum(1 for r in results if r.passed),
        "failed": sum(1 for r in results if not r.passed),
        "results": [
            {
                "scenario_id": r.scenario_id,
                "passed": r.passed,
                "duration_ms": r.duration_ms,
                "expected": r.expected,
                "actual": r.actual,
                "errors": r.errors,
                "bot_response": r.bot_response
            }
            for r in results
        ]
    }

    with open(filename, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
```

---

## Сценарии (75 штук)

### SAVE: Задачи (10)

| ID | Input | Type | Теги |
|----|-------|------|------|
| save_task_01 | "Запомни купить молоко завтра" | task | dates |
| save_task_02 | "Задача: позвонить маме в субботу в 15:00" | task | dates, time |
| save_task_03 | "Надо сделать презентацию до пятницы" | task | dates |
| save_task_04 | "Срочно! Отправить отчёт Ивану" | task | priority, people |
| save_task_05 | "Записать ребёнка к врачу на следующей неделе" | task | dates |
| save_task_06 | "Не забыть оплатить интернет до 25 числа" | task | dates |
| save_task_07 | "TODO: разобрать почту" | task | - |
| save_task_08 | "Через час созвон с командой" | task | dates, relative |
| save_task_09 | "В понедельник сдать документы в налоговую" | task | dates |
| save_task_10 | "Высокий приоритет: исправить баг в продакшене" | task | priority |

### SAVE: Идеи (7)

| ID | Input | Теги |
|----|-------|------|
| save_idea_01 | "Идея: сделать мобильное приложение для трекинга привычек" | - |
| save_idea_02 | "А что если добавить геймификацию в обучение?" | - |
| save_idea_03 | "Придумал: можно использовать AI для автоматической категоризации" | - |
| save_idea_04 | "Интересная мысль — интегрировать с календарём Google" | - |
| save_idea_05 | "Концепция: бот который сам напоминает о забытых задачах" | - |
| save_idea_06 | "Было бы круто добавить голосовые заметки с транскрипцией" | - |
| save_idea_07 | "Подумать над интеграцией с Notion" | - |

### SAVE: Заметки (7)

| ID | Input | Теги |
|----|-------|------|
| save_note_01 | "Заметка: пароль от wifi в офисе — Guest2024" | - |
| save_note_02 | "Запиши: встреча прошла хорошо, договорились о следующих шагах" | - |
| save_note_03 | "Размер обуви ребёнка — 32" | - |
| save_note_04 | "Артём сказал что сроки сдвигаются на 2 недели" | people |
| save_note_05 | "Конференция будет в зале B, 3 этаж" | - |
| save_note_06 | "Рецепт борща от бабушки: свёкла, капуста, картошка..." | - |
| save_note_07 | "Номер заказа: 7823-ABC-445" | - |

### SAVE: Ресурсы (5)

| ID | Input | Теги |
|----|-------|------|
| save_resource_01 | "Полезная статья: https://example.com/article-about-ai" | url |
| save_resource_02 | "Книга на почитать: Atomic Habits by James Clear" | - |
| save_resource_03 | "Курс по машинному обучению: coursera.org/ml-course" | url |
| save_resource_04 | "Сохрани эту ссылку https://github.com/cool-project" | url |
| save_resource_05 | "Документация по API: docs.example.com/api/v2" | url |

### SAVE: Контакты (3)

| ID | Input | Теги |
|----|-------|------|
| save_contact_01 | "Контакт: Иван Петров, +7-999-123-45-67, менеджер" | people |
| save_contact_02 | "Электрик Сергей: 8-800-555-35-35" | people |
| save_contact_03 | "Email дизайнера: anna@design.studio" | - |

### QUERY: Поиск (10)

| ID | Input | depends_on | Теги |
|----|-------|------------|------|
| query_01 | "Что у меня на сегодня?" | save_task_08 | dates |
| query_02 | "Покажи все задачи" | - | list |
| query_03 | "Найди заметки про wifi" | save_note_01 | search |
| query_04 | "Какие у меня идеи?" | - | filter |
| query_05 | "Поиск: презентация" | save_task_03 | search |
| query_06 | "Есть что-нибудь срочное?" | - | priority |
| query_07 | "Что я записывал про Ивана?" | save_contact_01 | people |
| query_08 | "Покажи ресурсы" | - | filter |
| query_09 | "Задачи на эту неделю" | - | dates |
| query_10 | "Найди всё связанное с работой" | - | semantic |

### ACTION: Обновление (4)

| ID | Input | confirm | expect_updated | Теги |
|----|-------|---------|----------------|------|
| action_update_01 | "Отметь задачу про молоко как выполненную" | True | 1 | confirm |
| action_update_02 | "Перенеси презентацию на понедельник" | True | 1 | dates, confirm |
| action_update_03 | "Сделай задачу с багом высоким приоритетом" | True | 1 | priority, confirm |
| action_update_04_cancel | "Отметь все задачи как выполненные" | False | 0 | batch, cancel |

### ACTION: Удаление (3)

| ID | Input | confirm | expect_deleted | Теги |
|----|-------|---------|----------------|------|
| action_delete_01 | "Удали заметку про номер заказа" | True | 1 | confirm |
| action_delete_02_cancel | "Удали все мои идеи" | False | 0 | batch, cancel |
| action_delete_03 | "Убери контакт электрика" | True | 1 | confirm |

### CHAT: Диалог (5)

| ID | Input | expect_in_db |
|----|-------|--------------|
| chat_01 | "Привет!" | False |
| chat_02 | "Спасибо за помощь" | False |
| chat_03 | "Что ты умеешь?" | False |
| chat_04 | "Как дела?" | False |
| chat_05 | "Ты бот или человек?" | False |

### EDGE CASES: Сложные случаи (6)

| ID | Input | expect_intent | Теги |
|----|-------|---------------|------|
| edge_01_ambiguous | "молоко" | unclear | ambiguous |
| edge_02_mixed | "Запомни идею и сразу найди похожие" | save | mixed |
| edge_03_typos | "Задача: купитт хлеп завтар" | save | typos |
| edge_04_emoji | "🔥 Срочно сделать отчёт! 📊" | save | emoji |
| edge_05_long | "Это очень длинная заметка бла бла... (100+ слов)" | save | long |
| edge_06_special_chars | "Заметка: формула E=mc², код \<script\>" | save | special |

### IMPLICIT: Неявные сценарии (15)

#### Голые ссылки (3)

| ID | Input | expect_type | Теги |
|----|-------|-------------|------|
| implicit_url_01 | "https://habr.com/ru/articles/123456/" | resource | bare |
| implicit_url_02 | "youtube.com/watch?v=dQw4w9WgXcQ" | resource | bare |
| implicit_url_03 | "вот это глянь https://twitter.com/elonmusk/status/123" | resource | context |

#### Буфер обмена (4)

| ID | Input | expect_type | Теги |
|----|-------|-------------|------|
| implicit_clipboard_01 | "ул. Ленина 42, кв 15" | note | address |
| implicit_clipboard_02 | "4276 1234 5678 9012" | note | number |
| implicit_clipboard_03 | "ABC-123-XYZ" | note | code |
| implicit_clipboard_04 | "192.168.1.100:8080" | note | technical |

#### Пересланные сообщения (3)

| ID | Input | forward_from | expect_type | Теги |
|----|-------|--------------|-------------|------|
| implicit_forward_01 | "Встречаемся в 18:00 у метро" | Жена | note | forward |
| implicit_forward_02 | "Дедлайн по проекту — пятница, без вариантов" | Начальник | task | forward |
| implicit_forward_03 | "Вот контакт хорошего стоматолога: +7-999-111-22-33" | Мама | contact | forward |

#### Follow-up исправления (5)

| ID | Input | depends_on | is_followup | expect_intent |
|----|-------|------------|-------------|---------------|
| implicit_followup_01_base | "Купить подарок Маше" | - | False | save |
| implicit_followup_01_correction | "*Кате, не Маше" | implicit_followup_01_base | True | action |
| implicit_followup_02_base | "Встреча с клиентом" | - | False | save |
| implicit_followup_02_addition | "в четверг в 14:00" | implicit_followup_02_base | True | action |
| implicit_followup_03_clarify | "это срочно" | implicit_followup_02_base | True | action |

---

## Зависимости

```
colorama          # Цветной вывод в консоль
```

Все остальные зависимости уже есть в проекте (asyncpg, sqlalchemy, etc).

---

## Следующие шаги

1. Создать файлы по структуре выше
2. Реализовать mocks.py
3. Реализовать assertions.py
4. Реализовать runner.py
5. Заполнить scenarios.py
6. Запустить и отладить
