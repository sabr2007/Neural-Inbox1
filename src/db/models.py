# neural-inbox1/src/db/models.py
# SQLAlchemy / raw SQL
"""Database models for Neural Inbox."""
from datetime import datetime
from enum import Enum as PyEnum
from typing import Optional, List

from sqlalchemy import (
    BigInteger, String, Text, Boolean, Float, Integer,
    ForeignKey, CheckConstraint, UniqueConstraint, Index,
    DateTime, func
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from pgvector.sqlalchemy import Vector


class Base(DeclarativeBase):
    pass


class ItemType(str, PyEnum):
    TASK = "task"
    IDEA = "idea"
    NOTE = "note"
    RESOURCE = "resource"
    CONTACT = "contact"
    EVENT = "event"


class ItemStatus(str, PyEnum):
    INBOX = "inbox"
    ACTIVE = "active"
    DONE = "done"
    ARCHIVED = "archived"


class ItemSource(str, PyEnum):
    TEXT = "text"
    VOICE = "voice"
    PHOTO = "photo"
    PDF = "pdf"
    FORWARD = "forward"
    LINK = "link"


class Priority(str, PyEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class User(Base):
    __tablename__ = "users"

    user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    timezone: Mapped[str] = mapped_column(String(50), default="Asia/Almaty")
    language: Mapped[str] = mapped_column(String(5), default="ru")
    settings: Mapped[dict] = mapped_column(JSONB, default=dict)
    onboarding_done: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    items: Mapped[List["Item"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    projects: Mapped[List["Project"]] = relationship(back_populates="user", cascade="all, delete-orphan")


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    color: Mapped[Optional[str]] = mapped_column(String(7))
    emoji: Mapped[Optional[str]] = mapped_column(String(10))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped["User"] = relationship(back_populates="projects")
    items: Mapped[List["Item"]] = relationship(back_populates="project")


class Item(Base):
    __tablename__ = "items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False)

    type: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="inbox")

    title: Mapped[Optional[str]] = mapped_column(String(500))
    content: Mapped[Optional[str]] = mapped_column(Text)
    original_input: Mapped[Optional[str]] = mapped_column(Text)
    source: Mapped[Optional[str]] = mapped_column(String(20))

    due_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    due_at_raw: Mapped[Optional[str]] = mapped_column(String(100))
    remind_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    priority: Mapped[Optional[str]] = mapped_column(String(10))
    project_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("projects.id", ondelete="SET NULL"))
    tags: Mapped[list] = mapped_column(JSONB, default=list)
    entities: Mapped[dict] = mapped_column(JSONB, default=dict)

    embedding: Mapped[Optional[list]] = mapped_column(Vector(1536))

    origin_user_name: Mapped[Optional[str]] = mapped_column(String(255))
    attachment_file_id: Mapped[Optional[str]] = mapped_column(String(255))
    attachment_type: Mapped[Optional[str]] = mapped_column(String(20))

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    user: Mapped["User"] = relationship(back_populates="items")
    project: Mapped[Optional["Project"]] = relationship(back_populates="items")

    __table_args__ = (
        CheckConstraint("type IN ('task', 'idea', 'note', 'resource', 'contact', 'event')", name="valid_type"),
        CheckConstraint("status IN ('inbox', 'active', 'done', 'archived')", name="valid_status"),
        Index("idx_items_user_status", "user_id", "status"),
        Index("idx_items_user_type", "user_id", "type"),
    )


class ItemLink(Base):
    __tablename__ = "item_links"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    item_id: Mapped[int] = mapped_column(Integer, ForeignKey("items.id", ondelete="CASCADE"), nullable=False)
    related_item_id: Mapped[int] = mapped_column(Integer, ForeignKey("items.id", ondelete="CASCADE"), nullable=False)
    link_type: Mapped[Optional[str]] = mapped_column(String(20))
    confidence: Mapped[Optional[float]] = mapped_column(Float)
    confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("item_id", "related_item_id", name="unique_item_link"),
    )
