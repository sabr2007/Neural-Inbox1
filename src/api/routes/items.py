"""
Items API routes.
CRUD operations for items.
"""
from typing import Optional, List

from aiogram import Bot
from fastapi import APIRouter, Depends, HTTPException, Query

from src.api.auth import get_user_id
from src.api.schemas import (
    ItemResponse, ItemUpdate, ItemMoveRequest,
    ItemsListResponse, SuccessResponse
)
from src.config import config
from src.db.database import get_session
from src.db.repository import ItemRepository, ItemLinkRepository
from src.db.search import find_similar

router = APIRouter(prefix="/api/items", tags=["items"])


@router.get("", response_model=ItemsListResponse)
async def list_items(
    user_id: int = Depends(get_user_id),
    type: Optional[str] = Query(None, description="Filter by type (comma-separated)"),
    status: Optional[str] = Query(None, description="Filter by status (comma-separated)"),
    project_id: Optional[int] = Query(None, description="Filter by project"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0)
):
    """List items with filters and pagination."""
    # Parse comma-separated filters
    types = type.split(",") if type else None
    statuses = status.split(",") if status else None

    async with get_session() as session:
        item_repo = ItemRepository(session)

        items = await item_repo.list_items(
            user_id=user_id,
            types=types,
            statuses=statuses,
            project_id=project_id,
            limit=limit,
            offset=offset
        )

        total = await item_repo.count_items(
            user_id=user_id,
            types=types,
            statuses=statuses,
            project_id=project_id
        )

        return ItemsListResponse(
            items=[ItemResponse.model_validate(item) for item in items],
            total=total,
            limit=limit,
            offset=offset,
            has_more=offset + len(items) < total
        )


@router.get("/{item_id}", response_model=ItemResponse)
async def get_item(
    item_id: int,
    user_id: int = Depends(get_user_id)
):
    """Get item by ID."""
    async with get_session() as session:
        item_repo = ItemRepository(session)
        item = await item_repo.get(item_id, user_id)

        if not item:
            raise HTTPException(status_code=404, detail="Item not found")

        return ItemResponse.model_validate(item)


@router.get("/{item_id}/related")
async def get_related_items(
    item_id: int,
    user_id: int = Depends(get_user_id)
):
    """
    Get related items for an item.

    Returns:
        - auto: Semantically similar items (score > 0.7)
        - linked: Explicitly linked items from agent with reason
    """
    async with get_session() as session:
        item_repo = ItemRepository(session)
        link_repo = ItemLinkRepository(session)

        # Verify item exists and belongs to user
        item = await item_repo.get(item_id, user_id)
        if not item:
            raise HTTPException(status_code=404, detail="Item not found")

        # Get semantically similar items (auto-related)
        similar_results = await find_similar(
            session=session,
            item_id=item_id,
            user_id=user_id,
            limit=10,
            min_similarity=0.7
        )
        auto_related = [
            {
                "id": r.id,
                "title": r.title,
                "type": r.type,
                "score": round(r.score, 2)
            }
            for r in similar_results
        ]

        # Get explicit links from agent
        linked = await link_repo.get_item_links(item_id)

        return {
            "auto": auto_related,
            "linked": linked
        }


@router.patch("/{item_id}", response_model=ItemResponse)
async def update_item(
    item_id: int,
    data: ItemUpdate,
    user_id: int = Depends(get_user_id)
):
    """Update item (partial update)."""
    async with get_session() as session:
        item_repo = ItemRepository(session)

        # Get only non-None values
        update_data = data.model_dump(exclude_unset=True)
        if not update_data:
            raise HTTPException(status_code=400, detail="No fields to update")

        item = await item_repo.update(item_id, user_id, **update_data)

        if not item:
            raise HTTPException(status_code=404, detail="Item not found")

        return ItemResponse.model_validate(item)


@router.delete("/{item_id}", response_model=SuccessResponse)
async def delete_item(
    item_id: int,
    user_id: int = Depends(get_user_id)
):
    """Delete item."""
    async with get_session() as session:
        item_repo = ItemRepository(session)
        deleted = await item_repo.delete(item_id, user_id)

        if not deleted:
            raise HTTPException(status_code=404, detail="Item not found")

        return SuccessResponse(message="Item deleted")


@router.patch("/{item_id}/complete", response_model=ItemResponse)
async def complete_item(
    item_id: int,
    user_id: int = Depends(get_user_id)
):
    """Mark item as completed."""
    async with get_session() as session:
        item_repo = ItemRepository(session)
        item = await item_repo.complete(item_id, user_id)

        if not item:
            raise HTTPException(status_code=404, detail="Item not found")

        return ItemResponse.model_validate(item)


@router.patch("/{item_id}/move", response_model=ItemResponse)
async def move_item(
    item_id: int,
    data: ItemMoveRequest,
    user_id: int = Depends(get_user_id)
):
    """Move item to a project (or remove from project if project_id is null)."""
    async with get_session() as session:
        item_repo = ItemRepository(session)
        item = await item_repo.update(item_id, user_id, project_id=data.project_id)

        if not item:
            raise HTTPException(status_code=404, detail="Item not found")

        return ItemResponse.model_validate(item)


@router.post("/{item_id}/send-to-chat", response_model=SuccessResponse)
async def send_to_chat(
    item_id: int,
    user_id: int = Depends(get_user_id)
):
    """Send item attachment back to user's Telegram chat."""
    async with get_session() as session:
        item_repo = ItemRepository(session)
        item = await item_repo.get(item_id, user_id)

        if not item:
            raise HTTPException(status_code=404, detail="Item not found")

        if not item.attachment_file_id:
            raise HTTPException(status_code=400, detail="Item has no attachment")

        # Send file via Telegram Bot API
        bot = Bot(token=config.telegram.bot_token)
        try:
            if item.attachment_type == "photo":
                await bot.send_photo(chat_id=user_id, photo=item.attachment_file_id)
            else:
                await bot.send_document(chat_id=user_id, document=item.attachment_file_id)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to send file: {str(e)}")
        finally:
            await bot.session.close()

        return SuccessResponse(message="File sent to chat")
