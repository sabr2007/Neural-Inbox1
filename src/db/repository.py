# neural-inbox1/src/db/repository.py
# CRUD
"""Database repository - CRUD operations."""
from datetime import datetime
from typing import Optional, List

from sqlalchemy import select, update, delete
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


class ProjectRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, user_id: int, name: str, color: Optional[str] = None, emoji: Optional[str] = None) -> Project:
        project = Project(user_id=user_id, name=name, color=color, emoji=emoji)
        self.session.add(project)
        await self.session.flush()
        return project

    async def get_all(self, user_id: int) -> List[Project]:
        result = await self.session.execute(
            select(Project).where(Project.user_id == user_id).order_by(Project.name)
        )
        return list(result.scalars().all())


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
