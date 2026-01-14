"""
Telegram inline keyboards for Neural Inbox bot.
"""
from typing import Optional
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo

from src.config import config


def clarification_keyboard(original_text: str) -> InlineKeyboardMarkup:
    """Keyboard for clarifying ambiguous intent (save vs query)."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="Сохранить",
                callback_data=f"clarify:save"
            ),
            InlineKeyboardButton(
                text="Найти",
                callback_data=f"clarify:query"
            )
        ]
    ])


def item_actions_keyboard(item_id: int, item_type: str) -> InlineKeyboardMarkup:
    """Keyboard with actions for a saved item."""
    buttons = [
        [
            InlineKeyboardButton(
                text="Выполнено",
                callback_data=f"complete:{item_id}"
            ),
            InlineKeyboardButton(
                text="Удалить",
                callback_data=f"delete:{item_id}"
            )
        ]
    ]

    if item_type == "task":
        buttons.append([
            InlineKeyboardButton(
                text="Отложить",
                callback_data=f"snooze:{item_id}"
            ),
            InlineKeyboardButton(
                text="Изменить",
                callback_data=f"edit:{item_id}"
            )
        ])

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def snooze_keyboard(item_id: int) -> InlineKeyboardMarkup:
    """Keyboard for snooze options."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="1 час",
                callback_data=f"snooze:{item_id}:1h"
            ),
            InlineKeyboardButton(
                text="3 часа",
                callback_data=f"snooze:{item_id}:3h"
            ),
            InlineKeyboardButton(
                text="Завтра",
                callback_data=f"snooze:{item_id}:tomorrow"
            )
        ],
        [
            InlineKeyboardButton(
                text="Через неделю",
                callback_data=f"snooze:{item_id}:week"
            ),
            InlineKeyboardButton(
                text="Отмена",
                callback_data=f"cancel"
            )
        ]
    ])


def link_suggestion_keyboard(item_id: int, related_id: int) -> InlineKeyboardMarkup:
    """Keyboard for confirming auto-link suggestion."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="Да, связать",
                callback_data=f"link:confirm:{item_id}:{related_id}"
            ),
            InlineKeyboardButton(
                text="Нет",
                callback_data=f"link:reject:{item_id}:{related_id}"
            )
        ]
    ])


def webapp_button() -> InlineKeyboardMarkup:
    """Button to open WebApp."""
    if not config.telegram.webapp_url:
        return None

    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="Открыть приложение",
                web_app=WebAppInfo(url=config.telegram.webapp_url)
            )
        ]
    ])


def confirm_delete_keyboard(item_id: int) -> InlineKeyboardMarkup:
    """Keyboard for confirming deletion."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="Да, удалить",
                callback_data=f"confirm_delete:{item_id}"
            ),
            InlineKeyboardButton(
                text="Отмена",
                callback_data="cancel"
            )
        ]
    ])


def search_results_keyboard(items: list, page: int = 0, has_more: bool = False) -> InlineKeyboardMarkup:
    """Keyboard for paginating search results."""
    buttons = []

    for item in items:
        buttons.append([
            InlineKeyboardButton(
                text=f"{item.title[:40]}..." if len(item.title) > 40 else item.title,
                callback_data=f"view:{item.id}"
            )
        ])

    nav_buttons = []
    if page > 0:
        nav_buttons.append(
            InlineKeyboardButton(text="<< Назад", callback_data=f"search_page:{page-1}")
        )
    if has_more:
        nav_buttons.append(
            InlineKeyboardButton(text="Вперёд >>", callback_data=f"search_page:{page+1}")
        )

    if nav_buttons:
        buttons.append(nav_buttons)

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def confirmation_keyboard(token: str, action_text: str) -> InlineKeyboardMarkup:
    """Keyboard for confirming batch operations."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text=f"{action_text}",
                callback_data=f"batch_confirm:{token}"
            ),
            InlineKeyboardButton(
                text="Отмена",
                callback_data=f"batch_cancel:{token}"
            )
        ]
    ])
