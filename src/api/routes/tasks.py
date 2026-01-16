"""
Tasks API routes.
Specialized endpoints for Tasks and Calendar tabs.
"""
from datetime import datetime, timedelta
from typing import Optional
from collections import defaultdict

from fastapi import APIRouter, Depends, Query

from src.api.auth import get_user_id
from src.api.schemas import (
    ItemResponse, TaskGroup, TasksListResponse,
    CalendarDay, CalendarResponse
)
from src.db.database import get_session
from src.db.repository import ItemRepository

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


def get_task_group_label(due_at: Optional[datetime], now: datetime) -> str:
    """Determine which group a task belongs to based on due date."""
    if due_at is None:
        return "without_date"

    today = now.date()
    due_date = due_at.date()

    if due_date < today:
        return "overdue"
    elif due_date == today:
        return "today"
    elif due_date == today + timedelta(days=1):
        return "tomorrow"
    elif due_date <= today + timedelta(days=7):
        return "this_week"
    else:
        return "later"


GROUP_ORDER = ["overdue", "today", "tomorrow", "this_week", "later", "without_date", "completed"]
GROUP_LABELS = {
    "overdue": "Просрочено",
    "today": "Сегодня",
    "tomorrow": "Завтра",
    "this_week": "На этой неделе",
    "later": "Позже",
    "without_date": "Без срока",
    "completed": "Выполненные"
}


@router.get("", response_model=TasksListResponse)
async def list_tasks(
    user_id: int = Depends(get_user_id),
    include_completed: bool = Query(False, description="Include completed tasks")
):
    """
    Get all tasks grouped by date.
    Groups: Просрочено, Сегодня, Завтра, На этой неделе, Позже, Без срока, Выполненные
    """
    async with get_session() as session:
        item_repo = ItemRepository(session)
        tasks = await item_repo.get_all_tasks(user_id)

        now = datetime.now()
        grouped: dict[str, list] = defaultdict(list)

        for task in tasks:
            if task.status == "done":
                if include_completed:
                    grouped["completed"].append(task)
            else:
                group_key = get_task_group_label(task.due_at, now)
                grouped[group_key].append(task)

        # Build response with ordered groups
        groups = []
        total = 0

        for key in GROUP_ORDER:
            if key in grouped and grouped[key]:
                items = [ItemResponse.model_validate(t) for t in grouped[key]]
                groups.append(TaskGroup(
                    label=GROUP_LABELS[key],
                    items=items
                ))
                total += len(items)

        return TasksListResponse(groups=groups, total=total)


@router.get("/calendar", response_model=CalendarResponse)
async def get_calendar_tasks(
    user_id: int = Depends(get_user_id),
    year: int = Query(..., description="Year"),
    month: int = Query(..., ge=1, le=12, description="Month (1-12)")
):
    """
    Get tasks for calendar view.
    Returns days with task counts and all tasks in the month.
    """
    # Calculate date range for the month
    first_day = datetime(year, month, 1)
    if month == 12:
        last_day = datetime(year + 1, 1, 1) - timedelta(seconds=1)
    else:
        last_day = datetime(year, month + 1, 1) - timedelta(seconds=1)

    async with get_session() as session:
        item_repo = ItemRepository(session)
        tasks = await item_repo.get_tasks_with_due_dates(
            user_id=user_id,
            date_from=first_day,
            date_to=last_day
        )

        # Count tasks per day
        day_counts: dict[str, int] = defaultdict(int)
        for task in tasks:
            if task.due_at and task.status != "done":
                date_str = task.due_at.strftime("%Y-%m-%d")
                day_counts[date_str] += 1

        days = [
            CalendarDay(date=date_str, count=count)
            for date_str, count in sorted(day_counts.items())
        ]

        return CalendarResponse(
            days=days,
            tasks=[ItemResponse.model_validate(t) for t in tasks]
        )
