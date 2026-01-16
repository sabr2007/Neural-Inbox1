"""
Items API routes.
CRUD operations for items.
"""
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query

from src.api.auth import get_user_id
from src.api.schemas import (
    ItemResponse, ItemUpdate, ItemMoveRequest,
    ItemsListResponse, SuccessResponse
)
from src.db.database import get_session
from src.db.repository import ItemRepository

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
