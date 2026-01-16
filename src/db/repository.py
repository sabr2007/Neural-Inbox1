# neural-inbox1/src/db/repository.py
# CRUD
"""Database repository - CRUD operations."""
from datetime import datetime
from typing import Optional, List, Dict, Any

from sqlalchemy import select, update, delete, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import User, Item, Project, ItemLink, ItemStatus, ItemType


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
        return item

    async def complete(self, item_id: int, user_id: int) -> Optional[Item]:
        return await self.update(
            item_id, user_id,
            status=ItemStatus.DONE.value,
            completed_at=datetime.utcnow()
        )

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


class ProjectRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, user_id: int, name: str, color: Optional[str] = None, emoji: Optional[str] = None) -> Project:
        project = Project(user_id=user_id, name=name, color=color, emoji=emoji)
        self.session.add(project)
        await self.session.flush()
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

    async def update(self, project_id: int, user_id: int, **kwargs) -> Optional[Project]:
        """Update a project."""
        project = await self.get(project_id, user_id)
        if project:
            for key, value in kwargs.items():
                if hasattr(project, key):
                    setattr(project, key, value)
            await self.session.flush()
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

    async def create(self, item_id: int, related_item_id: int, link_type: str = "related",
                     confidence: Optional[float] = None, confirmed: bool = False) -> ItemLink:
        link = ItemLink(
            item_id=item_id, related_item_id=related_item_id,
            link_type=link_type, confidence=confidence, confirmed=confirmed
        )
        self.session.add(link)
        await self.session.flush()
        return link
