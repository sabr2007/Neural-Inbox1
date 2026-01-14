"""
Callback handlers for inline buttons.
"""
import logging
from datetime import datetime, timedelta

from aiogram import Router, F
from aiogram.types import CallbackQuery

from src.db.database import get_session
from src.db.repository import ItemRepository
from src.bot.keyboards import snooze_keyboard, confirm_delete_keyboard
from src.bot.handlers.message import pending_clarifications, process_save
from src.db.models import ItemSource

logger = logging.getLogger(__name__)

callback_router = Router()


@callback_router.callback_query(F.data == "cancel")
async def handle_cancel(callback: CallbackQuery) -> None:
    """Handle cancel button."""
    await callback.message.edit_text("Отменено.")
    await callback.answer()


@callback_router.callback_query(F.data.startswith("clarify:"))
async def handle_clarification(callback: CallbackQuery) -> None:
    """Handle clarification response (save vs query)."""
    user_id = callback.from_user.id
    action = callback.data.split(":")[1]

    original_text = pending_clarifications.pop(user_id, None)

    if not original_text:
        await callback.answer("Время ответа истекло. Отправьте сообщение заново.")
        return

    if action == "save":
        # Process as save
        await callback.message.edit_text("Сохраняю...")
        # Create a fake message to reuse process_save
        # In production, refactor to not need message object
        async with get_session() as session:
            from src.ai.classifier import ContentClassifier
            from src.db.repository import UserRepository

            classifier = ContentClassifier()
            classification = await classifier.classify(original_text)

            user_repo = UserRepository(session)
            await user_repo.get_or_create(user_id)

            item_repo = ItemRepository(session)
            item = await item_repo.create(
                user_id=user_id,
                type=classification.type,
                title=classification.title,
                original_input=original_text,
                source=ItemSource.TEXT.value,
                due_at=classification.due_at,
                due_at_raw=classification.due_at_raw,
                priority=classification.priority,
                tags=classification.tags,
                entities=classification.entities
            )

            from src.bot.keyboards import item_actions_keyboard
            type_emoji = {
                "task": "",
                "idea": "",
                "note": "",
                "resource": "",
                "contact": "",
                "event": ""
            }
            emoji = type_emoji.get(classification.type, "")
            response = f"{emoji} Сохранено: {classification.title}"

            await callback.message.edit_text(
                response,
                reply_markup=item_actions_keyboard(item.id, classification.type)
            )

    elif action == "query":
        # Process as search query
        await callback.message.edit_text(
            f"Ищу: {original_text}\n"
            "(Поиск будет добавлен в следующей версии)"
        )

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
                f"Выполнено: {item.title}"
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
            await callback.message.edit_text("Удалено.")
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

    if duration == "1h":
        remind_at = now + timedelta(hours=1)
    elif duration == "3h":
        remind_at = now + timedelta(hours=3)
    elif duration == "tomorrow":
        remind_at = now.replace(hour=9, minute=0, second=0) + timedelta(days=1)
    elif duration == "week":
        remind_at = now.replace(hour=9, minute=0, second=0) + timedelta(weeks=1)

    async with get_session() as session:
        item_repo = ItemRepository(session)
        item = await item_repo.update(item_id, user_id, remind_at=remind_at)

        if item:
            duration_text = {
                "1h": "через 1 час",
                "3h": "через 3 часа",
                "tomorrow": "завтра в 9:00",
                "week": "через неделю"
            }
            await callback.message.edit_text(
                f"Напомню {duration_text.get(duration, 'позже')}: {item.title}"
            )
        else:
            await callback.answer("Элемент не найден", show_alert=True)
            return

    await callback.answer("Отложено!")


@callback_router.callback_query(F.data.startswith("view:"))
async def handle_view_item(callback: CallbackQuery) -> None:
    """View item details."""
    item_id = int(callback.data.split(":")[1])
    user_id = callback.from_user.id

    async with get_session() as session:
        item_repo = ItemRepository(session)
        item = await item_repo.get(item_id, user_id)

        if not item:
            await callback.answer("Элемент не найден", show_alert=True)
            return

        # Format item details
        type_emoji = {
            "task": "",
            "idea": "",
            "note": "",
            "resource": "",
            "contact": "",
            "event": ""
        }
        emoji = type_emoji.get(item.type, "")

        details = f"{emoji} **{item.title}**\n"

        if item.content:
            details += f"\n{item.content[:500]}"
            if len(item.content) > 500:
                details += "..."

        if item.due_at_raw:
            details += f"\n\nСрок: {item.due_at_raw}"

        if item.tags:
            details += f"\nТеги: {' '.join(item.tags)}"

        details += f"\n\nСоздано: {item.created_at.strftime('%d.%m.%Y %H:%M')}"

        from src.bot.keyboards import item_actions_keyboard
        await callback.message.edit_text(
            details,
            reply_markup=item_actions_keyboard(item.id, item.type),
            parse_mode="Markdown"
        )

    await callback.answer()


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

        await callback.message.edit_text("Элементы связаны!")
        await callback.answer("Связь создана!")

    elif action == "reject":
        await callback.message.edit_text("Понял, не связываю.")
        await callback.answer()


@callback_router.callback_query(F.data.startswith("batch_confirm:"))
async def handle_batch_confirm(callback: CallbackQuery) -> None:
    """Handle batch operation confirmation."""
    token = callback.data.split(":")[1]
    user_id = callback.from_user.id

    from src.ai.batch_confirmations import get_pending, clear_pending
    from src.db.repository import ProjectRepository

    pending = get_pending(token)
    if not pending:
        await callback.answer("Время подтверждения истекло. Попробуйте заново.", show_alert=True)
        return

    if pending.user_id != user_id:
        await callback.answer("Операция недоступна.", show_alert=True)
        return

    async with get_session() as session:
        item_repo = ItemRepository(session)
        project_repo = ProjectRepository(session)

        if pending.action == "update":
            # Parse update values from stored updates
            update_values = {}
            updates = pending.updates or {}
            if "status" in updates:
                update_values["status"] = updates["status"]
            if "priority" in updates:
                update_values["priority"] = updates["priority"]
            if "project_id" in updates:
                update_values["project_id"] = updates["project_id"]
            if "tags" in updates:
                update_values["tags"] = updates["tags"]
            if "due_at" in updates:
                from datetime import datetime
                try:
                    update_values["due_at"] = datetime.fromisoformat(
                        updates["due_at"].replace("Z", "+00:00")
                    )
                except ValueError:
                    pass
            if "due_at_raw" in updates:
                update_values["due_at_raw"] = updates["due_at_raw"]

            count = await item_repo.batch_update(pending.matched_ids, user_id, **update_values)
            clear_pending(token)
            await callback.message.edit_text(f"Обновлено {count} элементов.")
            await callback.answer("Готово!")

        elif pending.action == "delete":
            count = await item_repo.batch_delete(pending.matched_ids, user_id)
            clear_pending(token)
            await callback.message.edit_text(f"Удалено {count} элементов.")
            await callback.answer("Удалено!")

        elif pending.action == "delete_project":
            project_id = pending.filter.get("project_id")
            deleted = await project_repo.delete(project_id, user_id)
            clear_pending(token)
            if deleted:
                await callback.message.edit_text("Проект удалён.")
                await callback.answer("Проект удалён!")
            else:
                await callback.message.edit_text("Не удалось удалить проект.")
                await callback.answer("Ошибка", show_alert=True)

        elif pending.action == "move_items":
            source_id = pending.filter.get("project_id")
            target_id = pending.filter.get("target_project_id")
            count = await project_repo.move_items(source_id, target_id, user_id)
            clear_pending(token)
            await callback.message.edit_text(f"Перенесено {count} элементов.")
            await callback.answer("Перенесено!")

        else:
            await callback.answer("Неизвестная операция.", show_alert=True)


@callback_router.callback_query(F.data.startswith("batch_cancel:"))
async def handle_batch_cancel(callback: CallbackQuery) -> None:
    """Handle batch operation cancellation."""
    token = callback.data.split(":")[1]

    from src.ai.batch_confirmations import clear_pending

    clear_pending(token)
    await callback.message.edit_text("Операция отменена.")
    await callback.answer("Отменено")


@callback_router.callback_query(F.data == "agent_confirm_yes")
async def handle_agent_confirm_yes(callback: CallbackQuery) -> None:
    """Handle agent operation confirmation (Yes)."""
    from src.ai.agent import continue_agent_loop
    from src.bot.keyboards import agent_confirmation_keyboard

    user_id = callback.from_user.id
    result = await continue_agent_loop(user_id, confirmed=True)

    # Update original message with result
    await callback.message.edit_text(
        callback.message.text + "\n\n" + result.response,
        reply_markup=None
    )

    # If there's another confirmation needed, send new message
    if result.needs_confirmation:
        await callback.message.answer(
            result.response,
            reply_markup=agent_confirmation_keyboard()
        )

    await callback.answer()


@callback_router.callback_query(F.data == "agent_confirm_no")
async def handle_agent_confirm_no(callback: CallbackQuery) -> None:
    """Handle agent operation cancellation (No)."""
    from src.ai.agent import continue_agent_loop

    user_id = callback.from_user.id
    result = await continue_agent_loop(user_id, confirmed=False)

    await callback.message.edit_text(
        callback.message.text + "\n\nОтменено",
        reply_markup=None
    )
    await callback.answer("Отменено")
