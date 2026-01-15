"""E2E Test Scenarios for Neural Inbox.

75 scenarios covering:
- SAVE: Tasks, Ideas, Notes, Resources, Contacts
- QUERY: Search and filtering
- ACTION: Update and delete operations
- CHAT: Conversational responses
- EDGE CASES: Ambiguous, typos, emoji, long text
- IMPLICIT: URLs, clipboard, forwards, follow-ups
"""

from .assertions import Scenario


# =============================================================================
# SAVE: Tasks (10 scenarios)
# =============================================================================

SAVE_TASKS = [
    Scenario(
        id="save_task_01",
        input="Запомни купить молоко завтра",
        expect_intent="save",
        expect_type="task",
        expect_in_db=True,
        check_title_contains="молоко",
        tags=["dates"],
    ),
    Scenario(
        id="save_task_02",
        input="Задача: позвонить маме в субботу в 15:00",
        expect_intent="save",
        expect_type="task",
        expect_in_db=True,
        check_title_contains="маме",
        tags=["dates", "time"],
    ),
    Scenario(
        id="save_task_03",
        input="Надо сделать презентацию до пятницы",
        expect_intent="save",
        expect_type="task",
        expect_in_db=True,
        check_title_contains="презентацию",
        tags=["dates"],
    ),
    Scenario(
        id="save_task_04",
        input="Срочно! Отправить отчёт Ивану",
        expect_intent="save",
        expect_type="task",
        expect_in_db=True,
        check_title_contains="отчёт",
        tags=["priority", "people"],
    ),
    Scenario(
        id="save_task_05",
        input="Записать ребёнка к врачу на следующей неделе",
        expect_intent="save",
        expect_type="task",
        expect_in_db=True,
        check_title_contains="врач",
        tags=["dates"],
    ),
    Scenario(
        id="save_task_06",
        input="Не забыть оплатить интернет до 25 числа",
        expect_intent="save",
        expect_type="task",
        expect_in_db=True,
        check_title_contains="интернет",
        tags=["dates"],
    ),
    Scenario(
        id="save_task_07",
        input="TODO: разобрать почту",
        expect_intent="save",
        expect_type="task",
        expect_in_db=True,
        check_title_contains="почту",
        tags=[],
    ),
    Scenario(
        id="save_task_08",
        input="Через час созвон с командой",
        expect_intent="save",
        expect_type="task",
        expect_in_db=True,
        check_title_contains="созвон",
        tags=["dates", "relative"],
    ),
    Scenario(
        id="save_task_09",
        input="В понедельник сдать документы в налоговую",
        expect_intent="save",
        expect_type="task",
        expect_in_db=True,
        check_title_contains="документы",
        tags=["dates"],
    ),
    Scenario(
        id="save_task_10",
        input="Высокий приоритет: исправить баг в продакшене",
        expect_intent="save",
        expect_type="task",
        expect_in_db=True,
        check_title_contains="баг",
        tags=["priority"],
    ),
]


# =============================================================================
# SAVE: Ideas (7 scenarios)
# =============================================================================

SAVE_IDEAS = [
    Scenario(
        id="save_idea_01",
        input="Идея: сделать мобильное приложение для трекинга привычек",
        expect_intent="save",
        expect_type="idea",
        expect_in_db=True,
        check_title_contains="приложение",
        tags=[],
    ),
    Scenario(
        id="save_idea_02",
        input="А что если добавить геймификацию в обучение?",
        expect_intent="save",
        expect_type="idea",
        expect_in_db=True,
        check_title_contains="геймификац",
        tags=[],
    ),
    Scenario(
        id="save_idea_03",
        input="Придумал: можно использовать AI для автоматической категоризации",
        expect_intent="save",
        expect_type="idea",
        expect_in_db=True,
        check_title_contains="категориз",
        tags=[],
    ),
    Scenario(
        id="save_idea_04",
        input="Интересная мысль — интегрировать с календарём Google",
        expect_intent="save",
        expect_type="idea",
        expect_in_db=True,
        check_title_contains="календар",
        tags=[],
    ),
    Scenario(
        id="save_idea_05",
        input="Концепция: бот который сам напоминает о забытых задачах",
        expect_intent="save",
        expect_type="idea",
        expect_in_db=True,
        check_title_contains="напомина",
        tags=[],
    ),
    Scenario(
        id="save_idea_06",
        input="Было бы круто добавить голосовые заметки с транскрипцией",
        expect_intent="save",
        expect_type="idea",
        expect_in_db=True,
        check_title_contains="голосов",
        tags=[],
    ),
    Scenario(
        id="save_idea_07",
        input="Подумать над интеграцией с Notion",
        expect_intent="save",
        expect_type="idea",
        expect_in_db=True,
        check_title_contains="Notion",
        tags=[],
    ),
]


# =============================================================================
# SAVE: Notes (7 scenarios)
# =============================================================================

SAVE_NOTES = [
    Scenario(
        id="save_note_01",
        input="Заметка: пароль от wifi в офисе — Guest2024",
        expect_intent="save",
        expect_type="note",
        expect_in_db=True,
        check_title_contains="wifi",
        tags=[],
    ),
    Scenario(
        id="save_note_02",
        input="Запиши: встреча прошла хорошо, договорились о следующих шагах",
        expect_intent="save",
        expect_type="note",
        expect_in_db=True,
        check_title_contains="встреча",
        tags=[],
    ),
    Scenario(
        id="save_note_03",
        input="Размер обуви ребёнка — 32",
        expect_intent="save",
        expect_type="note",
        expect_in_db=True,
        check_title_contains="обув",
        tags=[],
    ),
    Scenario(
        id="save_note_04",
        input="Артём сказал что сроки сдвигаются на 2 недели",
        expect_intent="save",
        expect_type="note",
        expect_in_db=True,
        check_title_contains="срок",
        tags=["people"],
    ),
    Scenario(
        id="save_note_05",
        input="Конференция будет в зале B, 3 этаж",
        expect_intent="save",
        expect_type="note",
        expect_in_db=True,
        check_title_contains="конференц",
        tags=[],
    ),
    Scenario(
        id="save_note_06",
        input="Рецепт борща от бабушки: свёкла, капуста, картошка...",
        expect_intent="save",
        expect_type="note",
        expect_in_db=True,
        check_title_contains="борщ",
        tags=[],
    ),
    Scenario(
        id="save_note_07",
        input="Номер заказа: 7823-ABC-445",
        expect_intent="save",
        expect_type="note",
        expect_in_db=True,
        check_title_contains="заказ",
        tags=[],
    ),
]


# =============================================================================
# SAVE: Resources (5 scenarios)
# =============================================================================

SAVE_RESOURCES = [
    Scenario(
        id="save_resource_01",
        input="Полезная статья: https://example.com/article-about-ai",
        expect_intent="save",
        expect_type="resource",
        expect_in_db=True,
        tags=["url"],
    ),
    Scenario(
        id="save_resource_02",
        input="Книга на почитать: Atomic Habits by James Clear",
        expect_intent="save",
        expect_type="resource",
        expect_in_db=True,
        check_title_contains="Atomic",
        tags=[],
    ),
    Scenario(
        id="save_resource_03",
        input="Курс по машинному обучению: coursera.org/ml-course",
        expect_intent="save",
        expect_type="resource",
        expect_in_db=True,
        tags=["url"],
    ),
    Scenario(
        id="save_resource_04",
        input="Сохрани эту ссылку https://github.com/cool-project",
        expect_intent="save",
        expect_type="resource",
        expect_in_db=True,
        tags=["url"],
    ),
    Scenario(
        id="save_resource_05",
        input="Документация по API: docs.example.com/api/v2",
        expect_intent="save",
        expect_type="resource",
        expect_in_db=True,
        tags=["url"],
    ),
]


# =============================================================================
# SAVE: Contacts (3 scenarios)
# =============================================================================

SAVE_CONTACTS = [
    Scenario(
        id="save_contact_01",
        input="Контакт: Иван Петров, +7-999-123-45-67, менеджер",
        expect_intent="save",
        expect_type="contact",
        expect_in_db=True,
        check_title_contains="Иван",
        tags=["people"],
    ),
    Scenario(
        id="save_contact_02",
        input="Электрик Сергей: 8-800-555-35-35",
        expect_intent="save",
        expect_type="contact",
        expect_in_db=True,
        check_title_contains="Сергей",
        tags=["people"],
    ),
    Scenario(
        id="save_contact_03",
        input="Email дизайнера: anna@design.studio",
        expect_intent="save",
        expect_type="contact",
        expect_in_db=True,
        check_title_contains="дизайнер",
        tags=[],
    ),
]


# =============================================================================
# QUERY: Search (10 scenarios)
# =============================================================================

QUERY_SCENARIOS = [
    Scenario(
        id="query_01",
        input="Что у меня на сегодня?",
        expect_intent="query",
        depends_on="save_task_08",
        tags=["dates"],
    ),
    Scenario(
        id="query_02",
        input="Покажи все задачи",
        expect_intent="query",
        tags=["list"],
    ),
    Scenario(
        id="query_03",
        input="Найди заметки про wifi",
        expect_intent="query",
        depends_on="save_note_01",
        tags=["search"],
    ),
    Scenario(
        id="query_04",
        input="Какие у меня идеи?",
        expect_intent="query",
        tags=["filter"],
    ),
    Scenario(
        id="query_05",
        input="Поиск: презентация",
        expect_intent="query",
        depends_on="save_task_03",
        tags=["search"],
    ),
    Scenario(
        id="query_06",
        input="Есть что-нибудь срочное?",
        expect_intent="query",
        tags=["priority"],
    ),
    Scenario(
        id="query_07",
        input="Что я записывал про Ивана?",
        expect_intent="query",
        depends_on="save_contact_01",
        tags=["people"],
    ),
    Scenario(
        id="query_08",
        input="Покажи ресурсы",
        expect_intent="query",
        tags=["filter"],
    ),
    Scenario(
        id="query_09",
        input="Задачи на эту неделю",
        expect_intent="query",
        tags=["dates"],
    ),
    Scenario(
        id="query_10",
        input="Найди всё связанное с работой",
        expect_intent="query",
        tags=["semantic"],
    ),
]


# =============================================================================
# ACTION: Update (4 scenarios)
# =============================================================================

ACTION_UPDATE = [
    Scenario(
        id="action_update_01",
        input="Отметь задачу про молоко как выполненную",
        expect_intent="action",
        confirm=True,
        expect_updated=1,
        depends_on="save_task_01",
        tags=["confirm"],
    ),
    Scenario(
        id="action_update_02",
        input="Перенеси презентацию на понедельник",
        expect_intent="action",
        confirm=True,
        expect_updated=1,
        depends_on="save_task_03",
        tags=["dates", "confirm"],
    ),
    Scenario(
        id="action_update_03",
        input="Сделай задачу с багом высоким приоритетом",
        expect_intent="action",
        confirm=True,
        expect_updated=1,
        depends_on="save_task_10",
        tags=["priority", "confirm"],
    ),
    Scenario(
        id="action_update_04_cancel",
        input="Отметь все задачи как выполненные",
        expect_intent="action",
        confirm=False,
        expect_updated=0,
        tags=["batch", "cancel"],
    ),
]


# =============================================================================
# ACTION: Delete (3 scenarios)
# =============================================================================

ACTION_DELETE = [
    Scenario(
        id="action_delete_01",
        input="Удали заметку про номер заказа",
        expect_intent="action",
        confirm=True,
        expect_deleted=1,
        depends_on="save_note_07",
        tags=["confirm"],
    ),
    Scenario(
        id="action_delete_02_cancel",
        input="Удали все мои идеи",
        expect_intent="action",
        confirm=False,
        expect_deleted=0,
        tags=["batch", "cancel"],
    ),
    Scenario(
        id="action_delete_03",
        input="Убери контакт электрика",
        expect_intent="action",
        confirm=True,
        expect_deleted=1,
        depends_on="save_contact_02",
        tags=["confirm"],
    ),
]


# =============================================================================
# CHAT: Dialog (5 scenarios)
# =============================================================================

CHAT_SCENARIOS = [
    Scenario(
        id="chat_01",
        input="Привет!",
        expect_intent="chat",
        expect_in_db=False,
    ),
    Scenario(
        id="chat_02",
        input="Спасибо за помощь",
        expect_intent="chat",
        expect_in_db=False,
    ),
    Scenario(
        id="chat_03",
        input="Что ты умеешь?",
        expect_intent="chat",
        expect_in_db=False,
    ),
    Scenario(
        id="chat_04",
        input="Как дела?",
        expect_intent="chat",
        expect_in_db=False,
    ),
    Scenario(
        id="chat_05",
        input="Ты бот или человек?",
        expect_intent="chat",
        expect_in_db=False,
    ),
]


# =============================================================================
# EDGE CASES (6 scenarios)
# =============================================================================

EDGE_CASES = [
    Scenario(
        id="edge_01_ambiguous",
        input="молоко",
        expect_intent="unclear",
        tags=["ambiguous"],
    ),
    Scenario(
        id="edge_02_mixed",
        input="Запомни идею и сразу найди похожие",
        expect_intent="save",
        expect_in_db=True,
        tags=["mixed"],
    ),
    Scenario(
        id="edge_03_typos",
        input="Задача: купитт хлеп завтар",
        expect_intent="save",
        expect_type="task",
        expect_in_db=True,
        tags=["typos"],
    ),
    Scenario(
        id="edge_04_emoji",
        input="🔥 Срочно сделать отчёт! 📊",
        expect_intent="save",
        expect_type="task",
        expect_in_db=True,
        check_title_contains="отчёт",
        tags=["emoji"],
    ),
    Scenario(
        id="edge_05_long",
        input="Это очень длинная заметка которая содержит много текста и различных деталей о встрече которая прошла вчера где мы обсуждали планы на следующий квартал и решили что нужно увеличить продажи на двадцать процентов и нанять ещё трёх разработчиков для нового проекта который запустится в марте",
        expect_intent="save",
        expect_in_db=True,
        tags=["long"],
    ),
    Scenario(
        id="edge_06_special_chars",
        input="Заметка: формула E=mc², код <script>",
        expect_intent="save",
        expect_type="note",
        expect_in_db=True,
        tags=["special"],
    ),
]


# =============================================================================
# IMPLICIT: URLs (3 scenarios)
# =============================================================================

IMPLICIT_URLS = [
    Scenario(
        id="implicit_url_01",
        input="https://habr.com/ru/articles/123456/",
        expect_intent="save",
        expect_type="resource",
        expect_in_db=True,
        tags=["bare"],
    ),
    Scenario(
        id="implicit_url_02",
        input="youtube.com/watch?v=dQw4w9WgXcQ",
        expect_intent="save",
        expect_type="resource",
        expect_in_db=True,
        tags=["bare"],
    ),
    Scenario(
        id="implicit_url_03",
        input="вот это глянь https://twitter.com/elonmusk/status/123",
        expect_intent="save",
        expect_type="resource",
        expect_in_db=True,
        tags=["context"],
    ),
]


# =============================================================================
# IMPLICIT: Clipboard (4 scenarios)
# =============================================================================

IMPLICIT_CLIPBOARD = [
    Scenario(
        id="implicit_clipboard_01",
        input="ул. Ленина 42, кв 15",
        expect_intent="save",
        expect_type="note",
        expect_in_db=True,
        tags=["address"],
    ),
    Scenario(
        id="implicit_clipboard_02",
        input="4276 1234 5678 9012",
        expect_intent="save",
        expect_type="note",
        expect_in_db=True,
        tags=["number"],
    ),
    Scenario(
        id="implicit_clipboard_03",
        input="ABC-123-XYZ",
        expect_intent="save",
        expect_type="note",
        expect_in_db=True,
        tags=["code"],
    ),
    Scenario(
        id="implicit_clipboard_04",
        input="192.168.1.100:8080",
        expect_intent="save",
        expect_type="note",
        expect_in_db=True,
        tags=["technical"],
    ),
]


# =============================================================================
# IMPLICIT: Forwarded messages (3 scenarios)
# =============================================================================

IMPLICIT_FORWARDS = [
    Scenario(
        id="implicit_forward_01",
        input="Встречаемся в 18:00 у метро",
        forward_from="Жена",
        expect_intent="save",
        expect_type="note",
        expect_in_db=True,
        tags=["forward"],
    ),
    Scenario(
        id="implicit_forward_02",
        input="Дедлайн по проекту — пятница, без вариантов",
        forward_from="Начальник",
        expect_intent="save",
        expect_type="task",
        expect_in_db=True,
        tags=["forward"],
    ),
    Scenario(
        id="implicit_forward_03",
        input="Вот контакт хорошего стоматолога: +7-999-111-22-33",
        forward_from="Мама",
        expect_intent="save",
        expect_type="contact",
        expect_in_db=True,
        tags=["forward"],
    ),
]


# =============================================================================
# IMPLICIT: Follow-up corrections (5 scenarios)
# =============================================================================

IMPLICIT_FOLLOWUPS = [
    Scenario(
        id="implicit_followup_01_base",
        input="Купить подарок Маше",
        expect_intent="save",
        expect_in_db=True,
        is_followup=False,
    ),
    Scenario(
        id="implicit_followup_01_correction",
        input="*Кате, не Маше",
        expect_intent="action",
        depends_on="implicit_followup_01_base",
        is_followup=True,
    ),
    Scenario(
        id="implicit_followup_02_base",
        input="Встреча с клиентом",
        expect_intent="save",
        expect_in_db=True,
        is_followup=False,
    ),
    Scenario(
        id="implicit_followup_02_addition",
        input="в четверг в 14:00",
        expect_intent="action",
        depends_on="implicit_followup_02_base",
        is_followup=True,
    ),
    Scenario(
        id="implicit_followup_03_clarify",
        input="это срочно",
        expect_intent="action",
        depends_on="implicit_followup_02_base",
        is_followup=True,
    ),
]


# =============================================================================
# ALL SCENARIOS COMBINED
# =============================================================================

SCENARIOS: list[Scenario] = (
    SAVE_TASKS +
    SAVE_IDEAS +
    SAVE_NOTES +
    SAVE_RESOURCES +
    SAVE_CONTACTS +
    QUERY_SCENARIOS +
    ACTION_UPDATE +
    ACTION_DELETE +
    CHAT_SCENARIOS +
    EDGE_CASES +
    IMPLICIT_URLS +
    IMPLICIT_CLIPBOARD +
    IMPLICIT_FORWARDS +
    IMPLICIT_FOLLOWUPS
)

# Verify count
assert len(SCENARIOS) == 75, f"Expected 75 scenarios, got {len(SCENARIOS)}"
