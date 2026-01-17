# neural-inbox1/src/ai/agent.py
"""Intelligent Agent - orchestrator for message processing."""
from src.db.models import Item
import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Dict, Any

from openai import AsyncOpenAI

from src.config import config
from src.db.database import get_session
from src.db.repository import ItemRepository, ProjectRepository, ItemLinkRepository
from src.db.search import vector_search
from src.db.models import ItemStatus
from src.ai.prompts import AgentContext, build_prompt
from src.ai.model_selector import ModelSelector
from src.ai.embeddings import get_embedding, get_embeddings_batch
from src.ai.linker import create_links_batch

logger = logging.getLogger(__name__)


class AgentError(Exception):
    """Custom exception for agent errors."""
    pass


@dataclass
class CreatedItem:
    """Simple representation of a created item (detached from DB session)."""
    id: int
    type: str
    title: str
    due_at: Optional[datetime] = None
    due_at_raw: Optional[str] = None
    tags: List[str] = field(default_factory=list)


@dataclass
class CreatedLink:
    """Simple representation of a created link (detached from DB session)."""
    id: int
    item_id: int
    related_item_id: int
    reason: Optional[str] = None


@dataclass
class AgentResult:
    """Result of agent processing."""
    items_created: List[CreatedItem] = field(default_factory=list)
    links_created: List[CreatedLink] = field(default_factory=list)
    chat_response: Optional[str] = None
    processing_time: float = 0.0

    @property
    def is_empty(self) -> bool:
        """True if no items created and no chat response."""
        return not self.items_created and not self.chat_response


class IntelligentAgent:
    """
    Intelligent agent that processes user messages.

    Flow:
    1. GATHER CONTEXT (parallel) - projects, recent items, similar items
    2. ANALYZE & EXTRACT (LLM call) - parse text into items
    3. PERSIST & LINK (parallel) - save items, generate embeddings, create links
    """

    def __init__(self):
        self.client = AsyncOpenAI(api_key=config.openai.api_key)

    async def process(
        self,
        user_id: int,
        text: str,
        source: str
    ) -> AgentResult:
        """
        Process a user message and return structured result.

        Args:
            user_id: Telegram user ID
            text: Message text (transcribed if voice)
            source: Source type (text, voice, photo, etc.)

        Returns:
            AgentResult with created items, links, and optional chat response
        """
        start_time = time.time()

        async with get_session() as session:
            # 1. GATHER CONTEXT (parallel)
            context = await self._gather_context(session, user_id, text)

            # 2. ANALYZE & EXTRACT (LLM call)
            model = ModelSelector.select(text, source)
            llm_result = await self._analyze_with_llm(text, context, model)

            # Validate and extract items
            items_data = llm_result.get("items", [])
            if not isinstance(items_data, list):
                logger.error(f"Invalid items format from LLM: {type(items_data)}")
                raise AgentError(f"Invalid items format: expected list, got {type(items_data).__name__}")

            # Handle chat-only response (no items)
            if not items_data and llm_result.get("chat_response"):
                return AgentResult(
                    chat_response=llm_result["chat_response"],
                    processing_time=time.time() - start_time
                )

            # 3. PERSIST & LINK (parallel where possible)
            db_items = await self._persist_items(
                session, user_id, text, source, items_data
            )

            # Generate embeddings for new items
            if db_items:
                await self._generate_embeddings(session, db_items)

            # Create links from suggestions
            db_links = []
            suggested_links = llm_result.get("suggested_links", [])
            if db_items and isinstance(suggested_links, list) and suggested_links:
                db_links = await create_links_batch(
                    session, db_items, suggested_links
                )

            # Convert ORM objects to simple dataclasses before session closes
            items_created = [
                CreatedItem(
                    id=item.id,
                    type=item.type,
                    title=item.title or "",
                    due_at=item.due_at,
                    due_at_raw=item.due_at_raw,
                    tags=item.tags or []
                )
                for item in db_items
            ]

            links_created = [
                CreatedLink(
                    id=link.id,
                    item_id=link.item_id,
                    related_item_id=link.related_item_id,
                    reason=link.reason
                )
                for link in db_links
            ]

        return AgentResult(
            items_created=items_created,
            links_created=links_created,
            chat_response=llm_result.get("chat_response"),
            processing_time=time.time() - start_time
        )

    async def _gather_context(
        self,
        session,
        user_id: int,
        text: str
    ) -> AgentContext:
        """Gather user context sequentially (AsyncSession doesn't support parallel queries)."""
        item_repo = ItemRepository(session)
        project_repo = ProjectRepository(session)

        # Run context queries sequentially - AsyncSession doesn't support parallel operations
        projects = await project_repo.get_for_context(user_id)
        recent_items = await item_repo.get_recent_items(user_id, limit=20)
        similar_items = await self._get_similar_items(session, user_id, text)

        return AgentContext(
            projects=projects,
            recent_items=recent_items,
            similar_items=similar_items
        )

    async def _get_similar_items(
        self,
        session,
        user_id: int,
        text: str,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """Get semantically similar items for linking context."""
        try:
            results = await vector_search(session, user_id, text, limit=limit)
            return [
                {
                    "id": r.id,
                    "title": r.title,
                    "type": r.type,
                    "score": round(r.score, 2)
                }
                for r in results
                if r.score > 0.5  # Only include reasonably similar items
            ]
        except Exception as e:
            logger.warning(f"Similar items search failed: {e}")
            return []

    async def _analyze_with_llm(
        self,
        text: str,
        context: AgentContext,
        model: str
    ) -> Dict[str, Any]:
        """Call LLM to analyze text and extract items."""
        prompt = build_prompt(text, context)

        try:
            response = await self.client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": text}
                ],
                temperature=0.3,
                max_tokens=2000,
                response_format={"type": "json_object"}
            )

            raw_content = response.choices[0].message.content
            logger.debug(f"LLM raw response: {raw_content[:500]}")

            result = json.loads(raw_content)

            # Validate structure
            if not isinstance(result, dict):
                raise AgentError("Invalid LLM response format")

            # Log keys for debugging
            logger.debug(f"LLM result keys: {list(result.keys())}")

            return result

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response: {e}")
            raise AgentError(f"Invalid JSON from LLM: {e}")

        except Exception as e:
            logger.error(f"LLM call failed: {e}")
            raise AgentError(f"LLM error: {e}")

    async def _persist_items(
        self,
        session,
        user_id: int,
        original_text: str,
        source: str,
        items_data: List[Dict[str, Any]]
    ) -> List[Item]:
        """Create items in database."""
        if not items_data:
            return []

        item_repo = ItemRepository(session)
        created_items = []

        for item_data in items_data:
            try:
                # Validate item_data is a dict
                if not isinstance(item_data, dict):
                    logger.warning(f"Invalid item_data type: {type(item_data)}, value: {str(item_data)[:100]}")
                    continue

                # Parse due_at if provided
                due_at = None
                due_at_raw = item_data.get("due_at_raw")
                if item_data.get("due_at_iso"):
                    try:
                        due_at = datetime.fromisoformat(
                            item_data["due_at_iso"].replace("Z", "+00:00")
                        )
                    except (ValueError, TypeError):
                        pass

                item = await item_repo.create(
                    user_id=user_id,
                    type=item_data.get("type", "note"),
                    status=ItemStatus.INBOX.value,
                    title=item_data.get("title", original_text[:100]),
                    content=item_data.get("content") or original_text,
                    original_input=original_text,
                    source=source,
                    due_at=due_at,
                    due_at_raw=due_at_raw,
                    priority=item_data.get("priority"),
                    tags=item_data.get("tags", []),
                    project_id=item_data.get("project_id")
                )
                created_items.append(item)

            except Exception as e:
                logger.error(f"Failed to create item: {e}, data: {item_data}")
                continue

        return created_items

    async def _generate_embeddings(
        self,
        session,
        items: List[Item]
    ) -> None:
        """Generate and save embeddings for items."""
        if not items:
            return

        # Prepare texts for embedding
        texts = [
            f"{item.title or ''} {item.content or item.original_input or ''}"
            for item in items
        ]

        try:
            embeddings = await get_embeddings_batch(texts)

            item_repo = ItemRepository(session)
            for item, embedding in zip(items, embeddings):
                if embedding:
                    await item_repo.update(
                        item.id,
                        item.user_id,
                        embedding=embedding
                    )

        except Exception as e:
            logger.error(f"Failed to generate embeddings: {e}")
            # Non-fatal error, items are still saved
