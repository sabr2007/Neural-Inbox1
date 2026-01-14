#neural-inbox1/src/ai/agent.py
"""
AI Agent run loop for processing ACTION intents.
Multi-turn agent that calls OpenAI with tools and handles confirmations.
"""
import json
import logging
from dataclasses import dataclass
from datetime import datetime, date
from typing import Optional

from openai import AsyncOpenAI

from src.config import config
from src.ai.tools import TOOL_DEFINITIONS, execute_tool

logger = logging.getLogger(__name__)

# OpenAI client
client = AsyncOpenAI(api_key=config.openai.api_key)

# Agent system prompt
AGENT_SYSTEM_PROMPT = """Ты — AI-агент для управления задачами, заметками, идеями и проектами пользователя.

## Твои возможности (tools):

1. **search_items** — поиск записей по тексту, типу, статусу, дате, проекту, тегам
2. **get_item_details** — получить полную информацию о записи по ID
3. **batch_update_items** — массовое обновление записей (статус, приоритет, дата, проект, теги)
4. **batch_delete_items** — массовое удаление записей
5. **manage_projects** — создание, список, переименование, удаление проектов, перемещение записей

## Как работать:

1. **Сначала найди** — перед изменением/удалением используй search_items, чтобы понять что затронешь
2. **Уточняй при неясности** — если запрос размытый, лучше спросить пользователя
3. **Опасные операции требуют подтверждения** — batch_update, batch_delete, delete project вернут needs_confirmation=true. Ты получишь результат после подтверждения пользователем.

## Формат ответов:

- Отвечай кратко и по делу
- При успешной операции: "Готово: [что сделано]"
- При ошибке: "Ошибка: [что пошло не так]"

## Примеры:

Пользователь: "Удали все выполненные задачи"
→ Вызови search_items(status="done", type="task") чтобы увидеть что удалится
→ Вызови batch_delete_items(filter={{status: "done", type: "task"}})
→ Получишь needs_confirmation с превью
→ [Ждёшь подтверждения пользователя]
→ После подтверждения: "Готово: Удалено 5 задач"

Пользователь: "Перенеси задачи из Работа в Личное"
→ Сначала manage_projects(action="list") — найти ID проектов
→ Затем manage_projects(action="move_items", project_id=1, target_project_id=2)

Пользователь: "Что у меня на завтра?"
→ Это QUERY, не ACTION. Просто ответь: "Это похоже на поиск, а не действие. Переформулируй как действие или спроси напрямую."

## Текущая дата: {current_date}
"""


@dataclass
class AgentResult:
    """Result of agent execution."""
    success: bool
    response: str
    needs_confirmation: bool
    confirmation_token: Optional[str] = None


@dataclass
class PendingAgentState:
    """State of an interrupted agent (waiting for confirmation)."""
    user_id: int
    messages: list  # Full history: system + user + assistant + tool calls
    confirmation_token: str  # Token for confirming the operation
    pending_tool_call: dict  # Which tool to call with confirmed=true
    iteration: int  # Which iteration we stopped at
    created_at: datetime


# In-memory state storage (replace with Redis in production)
_pending_states: dict[int, PendingAgentState] = {}


def save_pending_state(user_id: int, state: PendingAgentState) -> None:
    """Save pending agent state for a user."""
    _pending_states[user_id] = state


def get_pending_state(user_id: int) -> Optional[PendingAgentState]:
    """Get pending agent state for a user."""
    return _pending_states.get(user_id)


def clear_pending_state(user_id: int) -> None:
    """Clear pending agent state for a user."""
    _pending_states.pop(user_id, None)


def has_pending_state(user_id: int) -> bool:
    """Check if user has pending agent state."""
    return user_id in _pending_states


def format_tools(definitions: list[dict]) -> list[dict]:
    """Convert tool definitions to OpenAI format."""
    return [
        {
            "type": "function",
            "function": {
                "name": tool["name"],
                "description": tool["description"],
                "parameters": tool["parameters"]
            }
        }
        for tool in definitions
    ]


def format_confirmation_request(result: dict) -> str:
    """Format confirmation request message."""
    action = result.get("action", "operation")
    count = result.get("matched_count", 0)
    preview = result.get("items_preview", [])

    lines = []

    if action == "delete":
        lines.append(f"Удалить {count} записей?")
    elif action == "update":
        lines.append(f"Обновить {count} записей?")
    elif action == "delete_project":
        project = result.get("project", {})
        items = result.get("items_count", 0)
        lines.append(f"Удалить проект «{project.get('name')}»?")
        if items > 0:
            lines.append(f"   (содержит {items} записей)")
    elif action == "move_items":
        source = result.get("source_project", {})
        target = result.get("target_project", {})
        count = result.get("items_count", 0)
        target_name = target.get("name", "без проекта") if target else "без проекта"
        lines.append(f"Переместить {count} записей из «{source.get('name')}» → «{target_name}»?")

    if preview:
        lines.append("\nПревью:")
        for item in preview[:5]:
            lines.append(f"  - {item.get('title', item.get('id'))}")
        if count > 5:
            lines.append(f"  ... и ещё {count - 5}")

    return "\n".join(lines)


def get_system_prompt() -> str:
    """Get system prompt with current date."""
    return AGENT_SYSTEM_PROMPT.format(
        current_date=date.today().isoformat()
    )


def _message_to_dict(message) -> dict:
    """Convert OpenAI message to dictionary for storage."""
    result = {
        "role": message.role,
        "content": message.content
    }
    if message.tool_calls:
        result["tool_calls"] = [
            {
                "id": tc.id,
                "type": tc.type,
                "function": {
                    "name": tc.function.name,
                    "arguments": tc.function.arguments
                }
            }
            for tc in message.tool_calls
        ]
    return result


async def run_agent_loop(user_id: int, user_message: str, context: str = None) -> AgentResult:
    """Run agent loop to process ACTION intent."""

    messages = [
        {"role": "system", "content": get_system_prompt()},
        {"role": "user", "content": user_message}
    ]

    if context:
        messages[1]["content"] = f"Контекст:\n{context}\n\nЗапрос:\n{user_message}"

    iteration = 0
    MAX_ITERATIONS = 5

    while iteration < MAX_ITERATIONS:
        iteration += 1

        try:
            # 1. Call OpenAI with tools
            response = await client.chat.completions.create(
                model=config.openai.model,
                messages=messages,
                tools=format_tools(TOOL_DEFINITIONS),
                tool_choice="auto"
            )

            assistant_message = response.choices[0].message
            messages.append(_message_to_dict(assistant_message))

            # 2. If no tool_calls - agent is done
            if not assistant_message.tool_calls:
                return AgentResult(
                    success=True,
                    response=assistant_message.content or "Готово.",
                    needs_confirmation=False
                )

            # 3. Execute each tool_call
            for tool_call in assistant_message.tool_calls:
                tool_name = tool_call.function.name
                tool_args = json.loads(tool_call.function.arguments)

                logger.info(f"Agent calling tool: {tool_name} with args: {tool_args}")

                result = await execute_tool(tool_name, user_id, tool_args)

                # 4. Check for needs_confirmation - INTERRUPT
                if result.get("needs_confirmation"):
                    save_pending_state(user_id, PendingAgentState(
                        user_id=user_id,
                        messages=messages,
                        confirmation_token=result["confirmation_token"],
                        pending_tool_call={
                            "id": tool_call.id,
                            "name": tool_name,
                            "arguments": {
                                **tool_args,
                                "confirmed": True,
                                "confirmation_token": result["confirmation_token"]
                            }
                        },
                        iteration=iteration,
                        created_at=datetime.utcnow()
                    ))

                    return AgentResult(
                        success=True,
                        response=format_confirmation_request(result),
                        needs_confirmation=True,
                        confirmation_token=result["confirmation_token"]
                    )

                # 5. Add result to messages
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": json.dumps(result, ensure_ascii=False)
                })

        except Exception as e:
            logger.error(f"Agent loop error: {e}")
            return AgentResult(
                success=False,
                response=f"Ошибка при выполнении: {str(e)}",
                needs_confirmation=False
            )

    # Iteration limit reached
    return AgentResult(
        success=False,
        response="Не удалось выполнить запрос за 5 шагов. Попробуй переформулировать.",
        needs_confirmation=False
    )


async def continue_agent_loop(user_id: int, confirmed: bool) -> AgentResult:
    """Continue agent loop after user confirmation."""

    # 1. Load state
    state = get_pending_state(user_id)
    if not state:
        return AgentResult(
            success=False,
            response="Нет активной операции для подтверждения.",
            needs_confirmation=False
        )

    # 2. Clear state (use once)
    clear_pending_state(user_id)

    # 3. If user declined
    if not confirmed:
        return AgentResult(
            success=True,
            response="Операция отменена.",
            needs_confirmation=False
        )

    # 4. Execute pending tool_call with confirmed=True
    pending = state.pending_tool_call
    result = await execute_tool(
        pending["name"],
        user_id,
        pending["arguments"]
    )

    # 5. Add result to history (complete Assistant → Tool pair)
    messages = state.messages
    messages.append({
        "role": "tool",
        "tool_call_id": pending["id"],
        "content": json.dumps(result, ensure_ascii=False)
    })

    # 6. Continue loop from where we stopped
    iteration = state.iteration
    MAX_ITERATIONS = 5

    while iteration < MAX_ITERATIONS:
        iteration += 1

        try:
            response = await client.chat.completions.create(
                model=config.openai.model,
                messages=messages,
                tools=format_tools(TOOL_DEFINITIONS),
                tool_choice="auto"
            )

            assistant_message = response.choices[0].message
            messages.append(_message_to_dict(assistant_message))

            if not assistant_message.tool_calls:
                return AgentResult(
                    success=True,
                    response=assistant_message.content or "Готово.",
                    needs_confirmation=False
                )

            for tool_call in assistant_message.tool_calls:
                tool_name = tool_call.function.name
                tool_args = json.loads(tool_call.function.arguments)

                logger.info(f"Agent continuing, calling tool: {tool_name}")

                result = await execute_tool(tool_name, user_id, tool_args)

                if result.get("needs_confirmation"):
                    save_pending_state(user_id, PendingAgentState(
                        user_id=user_id,
                        messages=messages,
                        confirmation_token=result["confirmation_token"],
                        pending_tool_call={
                            "id": tool_call.id,
                            "name": tool_name,
                            "arguments": {
                                **tool_args,
                                "confirmed": True,
                                "confirmation_token": result["confirmation_token"]
                            }
                        },
                        iteration=iteration,
                        created_at=datetime.utcnow()
                    ))

                    return AgentResult(
                        success=True,
                        response=format_confirmation_request(result),
                        needs_confirmation=True,
                        confirmation_token=result["confirmation_token"]
                    )

                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": json.dumps(result, ensure_ascii=False)
                })

        except Exception as e:
            logger.error(f"Agent continue error: {e}")
            return AgentResult(
                success=False,
                response=f"Ошибка при выполнении: {str(e)}",
                needs_confirmation=False
            )

    return AgentResult(
        success=False,
        response="Не удалось завершить за отведённое число шагов.",
        needs_confirmation=False
    )
