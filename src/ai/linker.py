# neural-inbox1/src/ai/linker.py
"""Item linking utilities for the intelligent agent."""
import logging
from typing import List, Dict, Any

from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import Item, ItemLink
from src.db.repository import ItemLinkRepository

logger = logging.getLogger(__name__)


async def create_links_batch(
    session: AsyncSession,
    created_items: List[Item],
    suggested_links: List[Dict[str, Any]]
) -> List[ItemLink]:
    """
    Create links between newly created items and existing items.

    Args:
        session: Database session
        created_items: List of newly created Item objects (in order of creation)
        suggested_links: List of link suggestions from the agent, each containing:
            - new_item_index: int (index in created_items list)
            - existing_item_id: int (ID of existing item to link to)
            - reason: str (reason for the link)

    Returns:
        List of created ItemLink objects
    """
    if not suggested_links or not created_items:
        return []

    link_repo = ItemLinkRepository(session)
    links_to_create = []

    for suggestion in suggested_links:
        try:
            new_item_index = suggestion.get("new_item_index", 0)
            existing_item_id = suggestion.get("existing_item_id")
            reason = suggestion.get("reason", "")

            # Validate index
            if new_item_index < 0 or new_item_index >= len(created_items):
                logger.warning(f"Invalid new_item_index: {new_item_index}")
                continue

            if not existing_item_id:
                logger.warning("Missing existing_item_id in link suggestion")
                continue

            new_item = created_items[new_item_index]

            links_to_create.append({
                "item_id": new_item.id,
                "related_item_id": existing_item_id,
                "reason": reason[:200] if reason else None,  # Truncate to field limit
                "link_type": "related"
            })

        except (KeyError, IndexError, TypeError) as e:
            logger.warning(f"Invalid link suggestion: {suggestion}, error: {e}")
            continue

    if not links_to_create:
        return []

    try:
        created_links = await link_repo.create_batch(links_to_create)
        logger.info(f"Created {len(created_links)} links")
        return created_links
    except Exception as e:
        logger.error(f"Failed to create links batch: {e}")
        return []
