"""
Search API route.
Semantic search using hybrid FTS + vector similarity.
"""
from typing import Optional

from fastapi import APIRouter, Depends, Query

from src.api.auth import get_user_id
from src.api.schemas import SearchResult, ItemResponse
from src.db.database import get_session
from src.db.search import hybrid_search
from src.db.repository import ItemRepository

router = APIRouter(prefix="/api/search", tags=["search"])


@router.get("", response_model=SearchResult)
async def search_items(
    q: str = Query(..., min_length=1, description="Search query"),
    user_id: int = Depends(get_user_id),
    type: Optional[str] = Query(None, description="Filter by type"),
    status: Optional[str] = Query(None, description="Filter by status"),
    limit: int = Query(20, ge=1, le=50)
):
    """
    Semantic search across all items.
    Uses hybrid search: Full-text search + Vector similarity.
    """
    async with get_session() as session:
        results = await hybrid_search(
            session=session,
            user_id=user_id,
            query=q,
            limit=limit,
            type_filter=type,
            status_filter=status
        )

        # Get full item details for results
        if results:
            item_repo = ItemRepository(session)
            item_ids = [r.id for r in results]
            items = await item_repo.get_by_ids(item_ids, user_id)

            # Maintain search order
            items_dict = {item.id: item for item in items}
            ordered_items = [items_dict[r.id] for r in results if r.id in items_dict]

            return SearchResult(
                items=[ItemResponse.model_validate(item) for item in ordered_items],
                total=len(ordered_items),
                has_more=len(ordered_items) == limit,
                query=q
            )

        return SearchResult(
            items=[],
            total=0,
            has_more=False,
            query=q
        )
