# neural-inbox1/src/db/repository.py
# CRUD
"""Database repository - CRUD operations."""
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Tuple
from zoneinfo import ZoneInfo

from sqlalchemy import select, update, delete, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import User, Item, Project, ItemLink, ItemStatus, ItemType


def calculate_next_due_date(current_due: datetime, recurrence: dict) -> Optional[datetime]:
    """
    Calculate the next due date based on recurrence rule.

    Args:
        current_due: Current due date
        recurrence: Recurrence rule dict with keys: type, interval, days, end_date

    Returns:
        Next due date or None if recurrence has ended
    """
    if not recurrence or not current_due:
        return None

    rec_type = recurrence.get("type", "daily")
    interval = recurrence.get("interval", 1)
    end_date_str = recurrence.get("end_date")

    # Check end date
    if end_date_str:
        try:
            end_date = datetime.fromisoformat(end_date_str.replace("Z", "+00:00"))
            if current_due >= end_date:
                return None
        except (ValueError, TypeError):
            pass

    next_due = current_due

    if rec_type == "daily":
        next_due = current_due + timedelta(days=interval)

    elif rec_type == "weekly":
        days = recurrence.get("days", [])
        if days:
            # Find next day from allowed days
            current_weekday = current_due.weekday()
            sorted_days = sorted(days)

            # Find next day in this week
            next_day = None
            for day in sorted_days:
                if day > current_weekday:
                    next_day = day
                    break

            if next_day is not None:
                # Next day in current week
                delta = next_day - current_weekday
            else:
                # First day of next week cycle
                delta = (7 * interval) - current_weekday + sorted_days[0]

            next_due = current_due + timedelta(days=delta)
        else:
            # No specific days, just add weeks
            next_due = current_due + timedelta(weeks=interval)

    elif rec_type == "monthly":
        # Add months (approximate with 30 days)
        month = current_due.month + interval
        year = current_due.year + (month - 1) // 12
        month = ((month - 1) % 12) + 1

        # Handle day overflow (e.g., Jan 31 -> Feb 28)
        day = min(current_due.day, 28)  # Safe day for all months

        next_due = current_due.replace(year=year, month=month, day=day)

    # Final check against end date
    if end_date_str:
        try:
            end_date = datetime.fromisoformat(end_date_str.replace("Z", "+00:00"))
            if next_due > end_date:
                return None
        except (ValueError, TypeError):
            pass

    return next_due


class UserRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_or_create(self, user_id: int) -> User:
        result = await self.session.execute(select(User).where(User.user_id == user_id))
        user = result.scalar_one_or_none()
        if not user:
            user = User(user_id=user_id)
            self.session.add(user)
            await self.session.flush()
            await self.session.refresh(user)
        return user

    async def get(self, user_id: int) -> Optional[User]:
        result = await self.session.execute(select(User).where(User.user_id == user_id))
        return result.scalar_one_or_none()


class ItemRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self, user_id: int, type: str,
        title: Optional[str] = None, content: Optional[str] = None,
        original_input: Optional[str] = None, source: Optional[str] = None,
        due_at: Optional[datetime] = None, due_at_raw: Optional[str] = None,
        priority: Optional[str] = None, tags: Optional[List[str]] = None,
        entities: Optional[dict] = None, project_id: Optional[int] = None,
        **kwargs
    ) -> Item:
        item = Item(
            user_id=user_id, type=type, title=title, content=content,
            original_input=original_input, source=source,
            due_at=due_at, due_at_raw=due_at_raw, priority=priority,
            tags=tags or [], entities=entities or {},
            project_id=project_id, **kwargs
        )
        self.session.add(item)
        await self.session.flush()
        # Refresh to get server-side default values (e.g., created_at, updated_at)
        await self.session.refresh(item)
        return item

    async def get(self, item_id: int, user_id: int) -> Optional[Item]:
        result = await self.session.execute(
            select(Item).where(Item.id == item_id, Item.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def get_by_status(self, user_id: int, status: str, limit: int = 50) -> List[Item]:
        result = await self.session.execute(
            select(Item).where(Item.user_id == user_id, Item.status == status)
            .order_by(Item.created_at.desc()).limit(limit)
        )
        return list(result.scalars().all())

    async def get_inbox(self, user_id: int, limit: int = 50) -> List[Item]:
        return await self.get_by_status(user_id, ItemStatus.INBOX.value, limit)

    async def update(self, item_id: int, user_id: int, **kwargs) -> Optional[Item]:
        item = await self.get(item_id, user_id)
        if item:
            for key, value in kwargs.items():
                if hasattr(item, key):
                    setattr(item, key, value)
            await self.session.flush()
            # Refresh to get server-side updated values (e.g., updated_at)
            await self.session.refresh(item)
        return item

    async def complete(self, item_id: int, user_id: int) -> Tuple[Optional[Item], Optional[Item]]:
        """
        Complete an item. If it has recurrence, create the next instance.

        Returns:
            Tuple of (completed_item, next_recurring_item or None)
        """
        item = await self.get(item_id, user_id)
        if not item:
            return None, None

        # Mark as completed
        item.status = ItemStatus.DONE.value
        item.completed_at = datetime.now(ZoneInfo("UTC"))
        await self.session.flush()
        await self.session.refresh(item)

        # Create next recurring instance if applicable
        next_item = None
        if item.recurrence and item.due_at:
            next_due = calculate_next_due_date(item.due_at, item.recurrence)
            if next_due:
                next_item = Item(
                    user_id=user_id,
                    type=item.type,
                    status=ItemStatus.INBOX.value,
                    title=item.title,
                    content=item.content,
                    due_at=next_due,
                    due_at_raw=item.due_at_raw,
                    remind_at=next_due,  # Remind at due time
                    priority=item.priority,
                    project_id=item.project_id,
                    tags=item.tags or [],
                    recurrence=item.recurrence,  # Inherit recurrence rule
                )
                self.session.add(next_item)
                await self.session.flush()
                await self.session.refresh(next_item)

        return item, next_item

    async def delete(self, item_id: int, user_id: int) -> bool:
        result = await self.session.execute(
            delete(Item).where(Item.id == item_id, Item.user_id == user_id)
        )
        return result.rowcount > 0

    async def search_advanced(
        self,
        user_id: int,
        query: Optional[str] = None,
        type_filter: Optional[str] = None,
        status_filter: Optional[str] = None,
        date_field: Optional[str] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        project_id: Optional[int] = None,
        priority: Optional[str] = None,
        tags: Optional[List[str]] = None,
        limit: int = 10
    ) -> List[Item]:
        """Advanced search with multiple filters."""
        conditions = [Item.user_id == user_id]

        if type_filter:
            conditions.append(Item.type == type_filter)
        if status_filter:
            conditions.append(Item.status == status_filter)
        if project_id:
            conditions.append(Item.project_id == project_id)
        if priority:
            conditions.append(Item.priority == priority)

        # Date range filtering
        if date_field and (date_from or date_to):
            date_column = Item.due_at if date_field == "due_at" else Item.created_at
            if date_from:
                conditions.append(date_column >= date_from)
            if date_to:
                conditions.append(date_column <= date_to)

        # Tags filtering (items containing ALL specified tags)
        if tags:
            for tag in tags:
                conditions.append(Item.tags.contains([tag]))

        # Text search in title and content
        if query:
            search_pattern = f"%{query}%"
            conditions.append(
                or_(
                    Item.title.ilike(search_pattern),
                    Item.content.ilike(search_pattern),
                    Item.original_input.ilike(search_pattern)
                )
            )

        stmt = select(Item).where(and_(*conditions)).order_by(Item.created_at.desc()).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_ids(self, item_ids: List[int], user_id: int) -> List[Item]:
        """Get multiple items by IDs."""
        result = await self.session.execute(
            select(Item).where(Item.id.in_(item_ids), Item.user_id == user_id)
        )
        return list(result.scalars().all())

    async def batch_update(self, item_ids: List[int], user_id: int, **kwargs) -> int:
        """Batch update items by IDs. Returns count of updated items."""
        if not item_ids:
            return 0

        stmt = (
            update(Item)
            .where(Item.id.in_(item_ids), Item.user_id == user_id)
            .values(**kwargs)
        )
        result = await self.session.execute(stmt)
        await self.session.flush()
        return result.rowcount

    async def batch_delete(self, item_ids: List[int], user_id: int) -> int:
        """Batch delete items by IDs. Returns count of deleted items."""
        if not item_ids:
            return 0

        stmt = delete(Item).where(Item.id.in_(item_ids), Item.user_id == user_id)
        result = await self.session.execute(stmt)
        await self.session.flush()
        return result.rowcount

    async def list_items(
        self,
        user_id: int,
        types: Optional[List[str]] = None,
        statuses: Optional[List[str]] = None,
        project_id: Optional[int] = None,
        limit: int = 20,
        offset: int = 0
    ) -> List[Item]:
        """List items with filters and pagination."""
        conditions = [Item.user_id == user_id]

        if types:
            conditions.append(Item.type.in_(types))
        if statuses:
            conditions.append(Item.status.in_(statuses))
        if project_id is not None:
            conditions.append(Item.project_id == project_id)

        stmt = (
            select(Item)
            .where(and_(*conditions))
            .order_by(Item.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def count_items(
        self,
        user_id: int,
        types: Optional[List[str]] = None,
        statuses: Optional[List[str]] = None,
        project_id: Optional[int] = None
    ) -> int:
        """Count items with filters."""
        from sqlalchemy import func

        conditions = [Item.user_id == user_id]

        if types:
            conditions.append(Item.type.in_(types))
        if statuses:
            conditions.append(Item.status.in_(statuses))
        if project_id is not None:
            conditions.append(Item.project_id == project_id)

        stmt = select(func.count(Item.id)).where(and_(*conditions))
        result = await self.session.execute(stmt)
        return result.scalar() or 0

    async def get_tasks_with_due_dates(
        self,
        user_id: int,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None
    ) -> List[Item]:
        """Get tasks with due dates in range."""
        conditions = [
            Item.user_id == user_id,
            Item.type == "task"
        ]

        if date_from:
            conditions.append(Item.due_at >= date_from)
        if date_to:
            conditions.append(Item.due_at <= date_to)

        stmt = (
            select(Item)
            .where(and_(*conditions))
            .order_by(Item.due_at.asc().nullslast())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_all_tasks(self, user_id: int) -> List[Item]:
        """Get all tasks for user (for Tasks tab)."""
        stmt = (
            select(Item)
            .where(Item.user_id == user_id, Item.type == "task")
            .order_by(Item.due_at.asc().nullslast(), Item.created_at.desc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_recent_items(self, user_id: int, limit: int = 20) -> List[Dict[str, Any]]:
        """Get recent items for agent context."""
        stmt = (
            select(Item)
            .where(Item.user_id == user_id)
            .order_by(Item.created_at.desc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        items = result.scalars().all()

        return [
            {
                "id": item.id,
                "title": item.title,
                "type": item.type,
                "tags": item.tags or [],
                "created_at": item.created_at.isoformat() if item.created_at else None
            }
            for item in items
        ]


class ProjectRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, user_id: int, name: str, color: Optional[str] = None, emoji: Optional[str] = None) -> Project:
        project = Project(user_id=user_id, name=name, color=color, emoji=emoji)
        self.session.add(project)
        await self.session.flush()
        await self.session.refresh(project)
        return project

    async def get(self, project_id: int, user_id: int) -> Optional[Project]:
        """Get a project by ID."""
        result = await self.session.execute(
            select(Project).where(Project.id == project_id, Project.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def get_by_name(self, name: str, user_id: int) -> Optional[Project]:
        """Get a project by name."""
        result = await self.session.execute(
            select(Project).where(Project.name == name, Project.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def get_all(self, user_id: int) -> List[Project]:
        result = await self.session.execute(
            select(Project).where(Project.user_id == user_id).order_by(Project.name)
        )
        return list(result.scalars().all())

    async def get_for_context(self, user_id: int) -> List[Dict[str, Any]]:
        """Get projects in simplified format for agent context."""
        projects = await self.get_all(user_id)
        return [
            {
                "id": p.id,
                "name": p.name,
                "emoji": p.emoji
            }
            for p in projects
        ]

    async def update(self, project_id: int, user_id: int, **kwargs) -> Optional[Project]:
        """Update a project."""
        project = await self.get(project_id, user_id)
        if project:
            for key, value in kwargs.items():
                if hasattr(project, key):
                    setattr(project, key, value)
            await self.session.flush()
            await self.session.refresh(project)
        return project

    async def delete(self, project_id: int, user_id: int) -> bool:
        """Delete a project. Returns True if deleted."""
        result = await self.session.execute(
            delete(Project).where(Project.id == project_id, Project.user_id == user_id)
        )
        await self.session.flush()
        return result.rowcount > 0

    async def get_items_count(self, project_id: int, user_id: int) -> int:
        """Get count of items in a project."""
        result = await self.session.execute(
            select(Item).where(Item.project_id == project_id, Item.user_id == user_id)
        )
        return len(list(result.scalars().all()))

    async def move_items(self, source_project_id: int, target_project_id: Optional[int], user_id: int) -> int:
        """Move all items from one project to another. Returns count of moved items."""
        stmt = (
            update(Item)
            .where(Item.project_id == source_project_id, Item.user_id == user_id)
            .values(project_id=target_project_id)
        )
        result = await self.session.execute(stmt)
        await self.session.flush()
        return result.rowcount


class ItemLinkRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        item_id: int,
        related_item_id: int,
        link_type: str = "related",
        reason: Optional[str] = None,
        confidence: Optional[float] = None,
        confirmed: bool = False
    ) -> ItemLink:
        """Create a link between two items."""
        link = ItemLink(
            item_id=item_id,
            related_item_id=related_item_id,
            link_type=link_type,
            reason=reason,
            confidence=confidence,
            confirmed=confirmed
        )
        self.session.add(link)
        await self.session.flush()
        await self.session.refresh(link)
        return link

    async def create_batch(
        self,
        links: List[Dict[str, Any]]
    ) -> List[ItemLink]:
        """
        Create multiple links at once.

        Args:
            links: List of dicts with keys: item_id, related_item_id, reason, link_type

        Returns:
            List of created ItemLink objects
        """
        created = []
        for link_data in links:
            link = ItemLink(
                item_id=link_data["item_id"],
                related_item_id=link_data["related_item_id"],
                link_type=link_data.get("link_type", "related"),
                reason=link_data.get("reason"),
                confidence=link_data.get("confidence"),
                confirmed=False
            )
            self.session.add(link)
            created.append(link)

        await self.session.flush()
        for link in created:
            await self.session.refresh(link)

        return created

    async def get_item_links(self, item_id: int) -> List[Dict[str, Any]]:
        """
        Get all explicit links for an item (for related items endpoint).

        Returns linked items with their details and link reason.
        """
        # Get links where this item is the source
        stmt = (
            select(ItemLink, Item)
            .join(Item, ItemLink.related_item_id == Item.id)
            .where(ItemLink.item_id == item_id)
        )
        result = await self.session.execute(stmt)
        rows = result.all()

        return [
            {
                "id": item.id,
                "title": item.title,
                "type": item.type,
                "reason": link.reason
            }
            for link, item in rows
        ]
