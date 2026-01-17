"""
Callback handlers for inline buttons.
Simplified for new "black hole" architecture - no clarification needed.
"""
import logging
from datetime import datetime, timedelta

from aiogram import Router, F
from aiogram.types import CallbackQuery

from src.db.database import get_session
from src.db.repository import ItemRepository
from src.bot.keyboards import (
    snooze_keyboard, confirm_delete_keyboard
)

logger = logging.getLogger(__name__)

callback_router = Router()


@callback_router.callback_query(F.data == "cancel")
async def handle_cancel(callback: CallbackQuery) -> None:
    """Handle cancel button."""
    await callback.message.edit_text("Отменено.")
    await callback.answer()


@callback_router.callback_query(F.data.startswith("complete:"))
async def handle_complete(callback: CallbackQuery) -> None:
    """Mark item as completed."""
    item_id = int(callback.data.split(":")[1])
    user_id = callback.from_user.id

    async with get_session() as session:
        item_repo = ItemRepository(session)
        item = await item_repo.complete(item_id, user_id)

        if item:
            await callback.message.edit_text(
                f"✔️ Выполнено: {item.title}"
            )
        else:
            await callback.answer("Элемент не найден", show_alert=True)
            return

    await callback.answer("Отмечено как выполненное!")


@callback_router.callback_query(F.data.startswith("delete:"))
async def handle_delete_request(callback: CallbackQuery) -> None:
    """Request confirmation for deletion."""
    item_id = int(callback.data.split(":")[1])

    await callback.message.edit_reply_markup(
        reply_markup=confirm_delete_keyboard(item_id)
    )
    await callback.answer()


@callback_router.callback_query(F.data.startswith("confirm_delete:"))
async def handle_confirm_delete(callback: CallbackQuery) -> None:
    """Confirm and delete item."""
    item_id = int(callback.data.split(":")[1])
    user_id = callback.from_user.id

    async with get_session() as session:
        item_repo = ItemRepository(session)
        deleted = await item_repo.delete(item_id, user_id)

        if deleted:
            await callback.message.edit_text("🗑️ Удалено.")
        else:
            await callback.answer("Элемент не найден", show_alert=True)
            return

    await callback.answer("Удалено!")


@callback_router.callback_query(F.data.startswith("snooze:"))
async def handle_snooze(callback: CallbackQuery) -> None:
    """Handle snooze - show options or apply snooze."""
    parts = callback.data.split(":")
    item_id = int(parts[1])

    if len(parts) == 2:
        # Show snooze options
        await callback.message.edit_reply_markup(
            reply_markup=snooze_keyboard(item_id)
        )
        await callback.answer()
        return

    # Apply snooze
    duration = parts[2]
    user_id = callback.from_user.id

    now = datetime.utcnow()
    remind_at = None
    duration_text = ""

    if duration == "15m":
        remind_at = now + timedelta(minutes=15)
        duration_text = "через 15 минут"
    elif duration == "1h":
        remind_at = now + timedelta(hours=1)
        duration_text = "через 1 час"
    elif duration == "1d":
        remind_at = now.replace(hour=9, minute=0, second=0) + timedelta(days=1)
        duration_text = "завтра в 9:00"
    elif duration == "3h":
        remind_at = now + timedelta(hours=3)
        duration_text = "через 3 часа"
    elif duration == "tomorrow":
        remind_at = now.replace(hour=9, minute=0, second=0) + timedelta(days=1)
        duration_text = "завтра в 9:00"
    elif duration == "week":
        remind_at = now.replace(hour=9, minute=0, second=0) + timedelta(weeks=1)
        duration_text = "через неделю"

    async with get_session() as session:
        item_repo = ItemRepository(session)
        item = await item_repo.update(item_id, user_id, remind_at=remind_at)

        if item:
            await callback.message.edit_text(
                f" Напомню {duration_text}: {item.title}"
            )
        else:
            await callback.answer("Элемент не найден", show_alert=True)
            return

    await callback.answer("Отложено!")


@callback_router.callback_query(F.data.startswith("link:"))
async def handle_link_action(callback: CallbackQuery) -> None:
    """Handle link confirmation/rejection."""
    parts = callback.data.split(":")
    action = parts[1]
    item_id = int(parts[2])
    related_id = int(parts[3])

    if action == "confirm":
        async with get_session() as session:
            from src.db.repository import ItemLinkRepository
            link_repo = ItemLinkRepository(session)
            await link_repo.create(item_id, related_id, "related", confirmed=True)

        await callback.message.edit_text("✅ Элементы связаны!")
        await callback.answer("Связь создана!")

    elif action == "reject":
        await callback.message.edit_text("Понял, не связываю.")
        await callback.answer()





