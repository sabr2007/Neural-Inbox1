# neural-inbox1/src/bot/jobs/reminders.py
"""Reminder scheduler - sends notifications when items are due."""
import logging
from datetime import datetime, timedelta
from typing import Optional, List
from zoneinfo import ZoneInfo

from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy import select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import Item, User, ItemStatus
from src.db.database import get_session
from src.bot.keyboards import reminder_actions_keyboard

logger = logging.getLogger(__name__)


class ReminderScheduler:
    """Планировщик напоминаний."""

    def __init__(self, bot: Bot):
        self.bot = bot
        self.scheduler = AsyncIOScheduler()
        self._is_running = False

    def start(self) -> None:
        """Запустить планировщик."""
        if self._is_running:
            logger.warning("Scheduler already running")
            return

        self.scheduler.add_job(
            self._check_reminders,
            trigger=IntervalTrigger(minutes=1),
            id="check_reminders",
            replace_existing=True,
            max_instances=1
        )
        self.scheduler.start()
        self._is_running = True
        logger.info("Reminder scheduler started")

    def stop(self) -> None:
        """Остановить планировщик."""
        if self._is_running:
            self.scheduler.shutdown(wait=False)
            self._is_running = False
            logger.info("Reminder scheduler stopped")

    async def _check_reminders(self) -> None:
        """Проверить и отправить напоминания."""
        logger.debug("Checking for due reminders...")

        try:
            async with get_session() as session:
                items = await self._get_due_items(session)

                if not items:
                    logger.debug("No due reminders found")
                    return

                logger.info(f"Found {len(items)} due reminders")

                for item, user in items:
                    await self._send_reminder(item, user)
                    await self._mark_reminded(session, item)

        except Exception as e:
            logger.error(f"Error checking reminders: {e}", exc_info=True)

    async def _get_due_items(
        self,
        session: AsyncSession
    ) -> List[tuple[Item, User]]:
        """Получить items, у которых пришло время напоминания."""
        now = datetime.now(ZoneInfo("UTC"))
        window_start = now - timedelta(minutes=5)
        window_end = now + timedelta(minutes=1)

        query = (
            select(Item, User)
            .join(User, Item.user_id == User.user_id)
            .where(
                and_(
                    Item.status.in_([ItemStatus.INBOX.value, ItemStatus.ACTIVE.value]),
                    or_(
                        and_(
                            Item.remind_at.isnot(None),
                            Item.remind_at >= window_start,
                            Item.remind_at <= window_end
                        ),
                        and_(
                            Item.remind_at.is_(None),
                            Item.due_at.isnot(None),
                            Item.due_at >= window_start,
                            Item.due_at <= window_end
                        )
                    )
                )
            )
        )

        result = await session.execute(query)
        return list(result.all())

    async def _send_reminder(self, item: Item, user: User) -> None:
        """Отправить напоминание пользователю."""
        try:
            tz = ZoneInfo(user.timezone or "Asia/Almaty")
            now_local = datetime.now(tz)

            time_str = ""
            if item.due_at:
                due_local = item.due_at.astimezone(tz)
                time_str = due_local.strftime("%H:%M")

            type_icon = {
                "task": "✔︎",
                "event": "•",
                "idea": "•",
                "note": "•",
                "resource": "•",
                "contact": "•"
            }.get(item.type, "•")

            message = f"{type_icon} <b>Напоминание</b>\n\n"
            message += f"{item.title or item.content[:100] if item.content else 'Без названия'}"

            if time_str:
                message += f"\n\n{time_str}"

            if item.due_at_raw:
                message += f" ({item.due_at_raw})"

            # Add interactive buttons for tasks
            keyboard = None
            if item.type == "task":
                keyboard = reminder_actions_keyboard(item.id)

            await self.bot.send_message(
                chat_id=item.user_id,
                text=message,
                reply_markup=keyboard
            )
            logger.info(f"Reminder sent: item_id={item.id}, user_id={item.user_id}")

        except Exception as e:
            logger.error(f"Failed to send reminder for item {item.id}: {e}")

    async def _mark_reminded(self, session: AsyncSession, item: Item) -> None:
        """Отметить, что напоминание отправлено (сдвинуть remind_at в прошлое)."""
        item.remind_at = datetime.now(ZoneInfo("UTC")) - timedelta(days=1)
        await session.flush()


_scheduler: Optional[ReminderScheduler] = None


def get_scheduler() -> Optional[ReminderScheduler]:
    """Получить текущий экземпляр планировщика."""
    return _scheduler


def init_scheduler(bot: Bot) -> ReminderScheduler:
    """Инициализировать планировщик."""
    global _scheduler
    _scheduler = ReminderScheduler(bot)
    return _scheduler
