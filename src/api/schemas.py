"""
Pydantic schemas (DTOs) for API request/response.
"""
from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel, Field


# ============== Item Schemas ==============

class RecurrenceRule(BaseModel):
    """Recurrence rule for recurring tasks."""
    type: str  # "daily", "weekly", "monthly"
    interval: int = 1  # Every N days/weeks/months
    days: Optional[List[int]] = None  # For weekly: [0-6] where 0=Monday
    end_date: Optional[str] = None  # ISO date string or null


class ItemResponse(BaseModel):
    """Item response DTO."""
    id: int
    type: str
    status: str
    title: str
    content: Optional[str] = None
    original_input: Optional[str] = None
    due_at: Optional[datetime] = None
    due_at_raw: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    project_id: Optional[int] = None
    priority: Optional[str] = None
    recurrence: Optional[dict] = None  # Recurrence rule
    attachment_file_id: Optional[str] = None
    attachment_type: Optional[str] = None
    attachment_filename: Optional[str] = None
    origin_user_name: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ItemUpdate(BaseModel):
    """Item update DTO (partial update)."""
    title: Optional[str] = None
    content: Optional[str] = None
    type: Optional[str] = None
    status: Optional[str] = None
    due_at: Optional[datetime] = None
    due_at_raw: Optional[str] = None
    tags: Optional[List[str]] = None
    project_id: Optional[int] = None
    priority: Optional[str] = None
    recurrence: Optional[dict] = None  # Recurrence rule or null to remove


class ItemMoveRequest(BaseModel):
    """Request to move item to a project."""
    project_id: Optional[int] = None  # None = remove from project


class ItemsListResponse(BaseModel):
    """Paginated items list response."""
    items: List[ItemResponse]
    total: int
    limit: int
    offset: int
    has_more: bool


# ============== Task Schemas ==============

class TaskGroup(BaseModel):
    """Group of tasks (e.g., "Today", "Tomorrow")."""
    label: str
    items: List[ItemResponse]


class TasksListResponse(BaseModel):
    """Tasks grouped by date."""
    groups: List[TaskGroup]
    total: int


class CalendarDay(BaseModel):
    """Calendar day with task count."""
    date: str  # ISO date string: "2026-01-17"
    count: int


class CalendarResponse(BaseModel):
    """Calendar data with tasks per day."""
    days: List[CalendarDay]
    tasks: List[ItemResponse]  # All tasks in the date range


# ============== Project Schemas ==============

class ProjectResponse(BaseModel):
    """Project response DTO."""
    id: int
    name: str
    color: Optional[str] = "#8B5CF6"
    emoji: Optional[str] = None
    item_count: int = 0
    created_at: datetime

    class Config:
        from_attributes = True


class ProjectCreate(BaseModel):
    """Project creation DTO."""
    name: str = Field(..., min_length=1, max_length=100)
    color: Optional[str] = "#8B5CF6"
    emoji: Optional[str] = None


class ProjectUpdate(BaseModel):
    """Project update DTO."""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    color: Optional[str] = None
    emoji: Optional[str] = None


class ProjectsListResponse(BaseModel):
    """Projects list response."""
    projects: List[ProjectResponse]
    total: int


# ============== Search Schemas ==============

class SearchResult(BaseModel):
    """Search result response."""
    items: List[ItemResponse]
    total: int
    has_more: bool
    query: str


# ============== Common Schemas ==============

class SuccessResponse(BaseModel):
    """Generic success response."""
    success: bool = True
    message: Optional[str] = None


class ErrorResponse(BaseModel):
    """Error response."""
    error: str
    detail: Optional[str] = None


# ============== User Settings Schemas ==============

class NotificationSettings(BaseModel):
    """Notification settings for user."""
    task_reminders: bool = True
    daily_digest: bool = True
    weekly_review: bool = False
    dnd_enabled: bool = False
    dnd_start: str = "22:00"  # HH:MM format
    dnd_end: str = "08:00"    # HH:MM format


class UserSettings(BaseModel):
    """Full user settings object stored in JSONB."""
    notifications: NotificationSettings = Field(default_factory=NotificationSettings)


class UserSettingsResponse(BaseModel):
    """User settings response with timezone."""
    timezone: str
    language: str
    settings: UserSettings
    onboarding_done: bool

    class Config:
        from_attributes = True


class UserSettingsUpdate(BaseModel):
    """User settings update DTO (partial update)."""
    timezone: Optional[str] = None
    language: Optional[str] = None
    notifications: Optional[NotificationSettings] = None
