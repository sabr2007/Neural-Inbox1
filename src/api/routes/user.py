"""
User API routes.
User settings management.
"""
from fastapi import APIRouter, Depends, HTTPException

from src.api.auth import get_user_id
from src.api.schemas import (
    UserSettingsResponse, UserSettingsUpdate, UserSettings, NotificationSettings
)
from src.db.database import get_session
from src.db.repository import UserRepository

router = APIRouter(prefix="/api/user", tags=["user"])


@router.get("/settings", response_model=UserSettingsResponse)
async def get_settings(user_id: int = Depends(get_user_id)):
    """Get current user settings."""
    async with get_session() as session:
        user_repo = UserRepository(session)
        user = await user_repo.get_or_create(user_id)

        # Parse stored settings or use defaults
        raw_settings = user.settings or {}
        notifications_data = raw_settings.get("notifications", {})

        settings = UserSettings(
            notifications=NotificationSettings(**notifications_data) if notifications_data else NotificationSettings()
        )

        return UserSettingsResponse(
            timezone=user.timezone or "Asia/Almaty",
            language=user.language or "ru",
            settings=settings,
            onboarding_done=user.onboarding_done
        )


@router.patch("/settings", response_model=UserSettingsResponse)
async def update_settings(
    data: UserSettingsUpdate,
    user_id: int = Depends(get_user_id)
):
    """Update user settings (partial update)."""
    async with get_session() as session:
        user_repo = UserRepository(session)
        user = await user_repo.get_or_create(user_id)

        # Update timezone if provided
        if data.timezone is not None:
            # Validate timezone
            try:
                from zoneinfo import ZoneInfo
                ZoneInfo(data.timezone)  # Will raise if invalid
                user.timezone = data.timezone
            except Exception:
                raise HTTPException(status_code=400, detail=f"Invalid timezone: {data.timezone}")

        # Update language if provided
        if data.language is not None:
            user.language = data.language

        # Update notification settings if provided
        if data.notifications is not None:
            current_settings = user.settings or {}
            current_settings["notifications"] = data.notifications.model_dump()
            user.settings = current_settings

        await session.commit()
        await session.refresh(user)

        # Parse stored settings for response
        raw_settings = user.settings or {}
        notifications_data = raw_settings.get("notifications", {})

        settings = UserSettings(
            notifications=NotificationSettings(**notifications_data) if notifications_data else NotificationSettings()
        )

        return UserSettingsResponse(
            timezone=user.timezone or "Asia/Almaty",
            language=user.language or "ru",
            settings=settings,
            onboarding_done=user.onboarding_done
        )


@router.post("/onboarding/complete")
async def complete_onboarding(user_id: int = Depends(get_user_id)):
    """Mark onboarding as complete."""
    async with get_session() as session:
        user_repo = UserRepository(session)
        user = await user_repo.get_or_create(user_id)
        user.onboarding_done = True
        await session.commit()

        return {"success": True, "message": "Onboarding completed"}
