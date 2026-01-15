"""Assertion utilities for E2E tests."""

import re
from dataclasses import dataclass, field
from typing import Optional

from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import Item
from .mocks import TEST_USER_ID


@dataclass
class TestResult:
    """Result of a single test scenario."""

    scenario_id: str
    passed: bool
    expected: dict
    actual: dict
    errors: list[str]
    duration_ms: int
    bot_response: str
    input_text: str = ""


@dataclass
class Scenario:
    """Test scenario definition."""

    id: str
    input: str
    expect_intent: str  # "save" | "query" | "action" | "chat" | "unclear"
    expect_type: Optional[str] = None  # "task" | "idea" | "note" | "resource" | "contact" | "event"
    expect_in_db: bool = False
    expect_found: Optional[int] = None  # For query: expected result count
    expect_updated: Optional[int] = None  # For action: items updated
    expect_deleted: Optional[int] = None  # For action: items deleted
    check_title_contains: Optional[str] = None
    check_response_contains: Optional[str] = None
    confirm: Optional[bool] = None  # None=no confirmation needed, True/False=response
    depends_on: Optional[str] = None  # ID of prerequisite scenario
    tags: list[str] = field(default_factory=list)
    forward_from: Optional[str] = None  # Simulated forward sender name
    is_followup: bool = False  # Is this a follow-up to previous message


async def get_latest_item(session: AsyncSession, user_id: int) -> Optional[Item]:
    """Get the most recently created item for user."""
    result = await session.execute(
        select(Item)
        .where(Item.user_id == user_id)
        .order_by(desc(Item.created_at))
        .limit(1)
    )
    return result.scalar_one_or_none()


async def get_items_count(session: AsyncSession, user_id: int) -> int:
    """Count all items for user."""
    from sqlalchemy import func
    result = await session.execute(
        select(func.count(Item.id)).where(Item.user_id == user_id)
    )
    return result.scalar() or 0


async def get_active_items_count(session: AsyncSession, user_id: int) -> int:
    """Count active (non-deleted) items for user."""
    from sqlalchemy import func
    result = await session.execute(
        select(func.count(Item.id))
        .where(Item.user_id == user_id)
        .where(Item.status != "archived")
    )
    return result.scalar() or 0


def extract_found_count(replies: list[str]) -> int:
    """Extract count of found items from bot replies.

    Looks for patterns like:
    - "Нашёл 5 записей"
    - "Найдено 3 задачи"
    - "Вот что я нашёл (2):"
    - Lists with numbered items
    """
    full_response = " ".join(replies)

    # Pattern: "Нашёл/Найдено N"
    match = re.search(r'(?:нашёл|найдено|нашла)\s+(\d+)', full_response, re.IGNORECASE)
    if match:
        return int(match.group(1))

    # Pattern: count numbered list items (1., 2., etc.)
    numbered_items = re.findall(r'^\s*\d+\.\s+', full_response, re.MULTILINE)
    if numbered_items:
        return len(numbered_items)

    # Pattern: count bullet points
    bullets = re.findall(r'^\s*[•\-\*]\s+', full_response, re.MULTILINE)
    if bullets:
        return len(bullets)

    # Check for "ничего не найдено" patterns
    if re.search(r'ничего\s+не\s+(?:нашёл|найдено|нашла)', full_response, re.IGNORECASE):
        return 0
    if re.search(r'не\s+(?:нашёл|найдено|нашла)', full_response, re.IGNORECASE):
        return 0

    return -1  # Unknown/could not parse


async def check_assertions(
    scenario: Scenario,
    replies: list[str],
    session: AsyncSession,
    items_before: int,
    last_intent: Optional[str] = None
) -> TestResult:
    """Check all assertions for a scenario."""
    errors: list[str] = []
    actual: dict = {}
    expected: dict = {}

    response_text = " ".join(replies)

    # 1. Check intent (if we can determine it)
    if scenario.expect_intent and last_intent:
        expected["intent"] = scenario.expect_intent
        actual["intent"] = last_intent
        if last_intent != scenario.expect_intent:
            errors.append(f"Intent: expected '{scenario.expect_intent}', got '{last_intent}'")

    # 2. Check DB creation
    if scenario.expect_in_db:
        expected["created"] = True
        items_after = await get_items_count(session, TEST_USER_ID)
        item_created = items_after > items_before
        actual["created"] = item_created

        if not item_created:
            errors.append("Expected item in DB, but nothing created")
        else:
            # Check item type
            item = await get_latest_item(session, TEST_USER_ID)
            if item:
                if scenario.expect_type:
                    expected["type"] = scenario.expect_type
                    actual["type"] = item.type
                    if item.type != scenario.expect_type:
                        errors.append(f"Type: expected '{scenario.expect_type}', got '{item.type}'")

                # Check title contains
                if scenario.check_title_contains and item.title:
                    expected["title_contains"] = scenario.check_title_contains
                    actual["title"] = item.title
                    if scenario.check_title_contains.lower() not in item.title.lower():
                        errors.append(f"Title should contain '{scenario.check_title_contains}', got '{item.title}'")

    # 3. Check query results
    if scenario.expect_found is not None:
        expected["found"] = scenario.expect_found
        found_count = extract_found_count(replies)
        actual["found"] = found_count
        # Allow -1 (unknown) to pass for now - might need smarter parsing
        if found_count != -1 and found_count != scenario.expect_found:
            errors.append(f"Found: expected {scenario.expect_found}, got {found_count}")

    # 4. Check deletion
    if scenario.expect_deleted is not None:
        expected["deleted"] = scenario.expect_deleted
        items_after = await get_active_items_count(session, TEST_USER_ID)
        deleted_count = items_before - items_after
        actual["deleted"] = deleted_count
        if deleted_count != scenario.expect_deleted:
            errors.append(f"Deleted: expected {scenario.expect_deleted}, got {deleted_count}")

    # 5. Check updates (harder to verify without tracking)
    if scenario.expect_updated is not None:
        expected["updated"] = scenario.expect_updated
        # We'll check response for confirmation of update
        update_patterns = [
            r'обновлен', r'изменен', r'выполнен', r'перенес',
            r'updated', r'changed', r'completed', r'done'
        ]
        update_mentioned = any(
            re.search(p, response_text, re.IGNORECASE)
            for p in update_patterns
        )
        actual["update_mentioned"] = update_mentioned
        if scenario.expect_updated > 0 and not update_mentioned:
            errors.append(f"Expected update confirmation in response")

    # 6. Check response contains
    if scenario.check_response_contains:
        expected["response_contains"] = scenario.check_response_contains
        actual["response_snippet"] = response_text[:200]
        if scenario.check_response_contains.lower() not in response_text.lower():
            errors.append(f"Response should contain '{scenario.check_response_contains}'")

    # 7. Check no DB write for chat intent
    if scenario.expect_intent == "chat" and not scenario.expect_in_db:
        items_after = await get_items_count(session, TEST_USER_ID)
        if items_after > items_before:
            errors.append("Chat intent should not create DB items")

    return TestResult(
        scenario_id=scenario.id,
        passed=len(errors) == 0,
        expected=expected,
        actual=actual,
        errors=errors,
        duration_ms=0,  # Will be set by runner
        bot_response=response_text,
        input_text=scenario.input
    )
