"""
Telegram inline keyboards for Neural Inbox bot.
"""
from typing import Optional
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo

from src.config import config

def delete_item_keyboard(item_id: int) -> InlineKeyboardMarkup:
    """Simple keyboard with just delete button (for after save)."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="Удалить",
                callback_data=f"delete:{item_id}"
            )
        ]
    ])


def reminder_actions_keyboard(item_id: int) -> InlineKeyboardMarkup:
    """Keyboard for task reminders with quick actions."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="✅ Выполнено",
                callback_data=f"complete:{item_id}"
            )
        ],
        [
            InlineKeyboardButton(
                text="+15м",
                callback_data=f"snooze:{item_id}:15m"
            ),
            InlineKeyboardButton(
                text="+1ч",
                callback_data=f"snooze:{item_id}:1h"
            ),
            InlineKeyboardButton(
                text="+1д",
                callback_data=f"snooze:{item_id}:1d"
            )
        ]
    ])


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






