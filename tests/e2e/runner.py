"""E2E Test Runner for Neural Inbox.

Usage:
    python -m tests.e2e.runner
    python -m tests.e2e.runner --no-cleanup --verbose
    python -m tests.e2e.runner --tag dates
    python -m tests.e2e.runner --scenario save_task_01
"""

import argparse
import asyncio
import json
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

from sqlalchemy import delete

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.db.database import get_session
from src.db.models import Item, User
from src.bot.handlers.message import handle_text
from src.ai.agent import continue_agent_loop, clear_pending_state, has_pending_state

from .mocks import MockMessage, TEST_USER_ID
from .assertions import Scenario, TestResult, check_assertions, get_items_count
from .scenarios import SCENARIOS

try:
    from colorama import init, Fore, Style
    init()
    HAS_COLOR = True
except ImportError:
    HAS_COLOR = False
    class Fore:
        GREEN = RED = YELLOW = CYAN = RESET = ""
    class Style:
        BRIGHT = RESET_ALL = ""


def print_scenario_start(index: int, total: int, scenario: Scenario, verbose: bool):
    """Print scenario start info."""
    if verbose:
        print(f"\n{Fore.CYAN}[{index}/{total}]{Style.RESET_ALL} Running: {scenario.id}")
        print(f"  Input: \"{scenario.input[:60]}{'...' if len(scenario.input) > 60 else ''}\"")
    else:
        print(f"[{index}/{total}] {scenario.id}...", end=" ", flush=True)


def print_result(result: TestResult, verbose: bool):
    """Print test result."""
    if result.passed:
        mark = f"{Fore.GREEN}✓{Style.RESET_ALL}"
        if verbose:
            print(f"  {mark} PASSED")
        else:
            print(mark)
    else:
        mark = f"{Fore.RED}✗{Style.RESET_ALL}"
        if verbose:
            print(f"  {mark} FAILED")
            for error in result.errors:
                print(f"    → {Fore.RED}{error}{Style.RESET_ALL}")
            if result.bot_response:
                snippet = result.bot_response[:150].replace('\n', ' ')
                print(f"    Response: \"{snippet}...\"")
        else:
            print(f"{mark} - {result.errors[0] if result.errors else 'Unknown error'}")


def print_summary(results: list[TestResult]):
    """Print test summary."""
    total = len(results)
    passed = sum(1 for r in results if r.passed)
    failed = total - passed

    print("\n" + "=" * 60)
    print(f"TOTAL: {total} scenarios")
    print(f"{Fore.GREEN}PASSED: {passed}{Style.RESET_ALL}")
    if failed > 0:
        print(f"{Fore.RED}FAILED: {failed}{Style.RESET_ALL}")
    print("=" * 60)

    if failed > 0:
        print(f"\n{Fore.RED}Failed scenarios:{Style.RESET_ALL}")
        for r in results:
            if not r.passed:
                print(f"  - {r.scenario_id}: {r.errors[0] if r.errors else 'Unknown'}")


def save_json_report(results: list[TestResult]) -> str:
    """Save JSON report and return filename."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    reports_dir = Path(__file__).parent / "reports"
    reports_dir.mkdir(exist_ok=True)
    filename = reports_dir / f"report_{timestamp}.json"

    report = {
        "timestamp": timestamp,
        "total": len(results),
        "passed": sum(1 for r in results if r.passed),
        "failed": sum(1 for r in results if not r.passed),
        "results": [
            {
                "scenario_id": r.scenario_id,
                "passed": r.passed,
                "duration_ms": r.duration_ms,
                "input": r.input_text,
                "expected": r.expected,
                "actual": r.actual,
                "errors": r.errors,
                "bot_response": r.bot_response[:500] if r.bot_response else ""
            }
            for r in results
        ]
    }

    with open(filename, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    return str(filename)


async def cleanup_test_data(user_id: int = TEST_USER_ID):
    """Remove all test data for the test user."""
    async with get_session() as session:
        # Delete all items for test user
        await session.execute(
            delete(Item).where(Item.user_id == user_id)
        )
        # Optionally delete user record too
        await session.execute(
            delete(User).where(User.user_id == user_id)
        )
        await session.commit()


async def ensure_test_user(user_id: int = TEST_USER_ID):
    """Ensure test user exists in database."""
    from src.db.repository import UserRepository
    async with get_session() as session:
        user_repo = UserRepository(session)
        await user_repo.get_or_create(user_id)
        await session.commit()


async def run_scenario(
    scenario: Scenario,
    verbose: bool = False
) -> TestResult:
    """Run a single test scenario."""
    start_time = time.time()

    async with get_session() as session:
        # Get items count before
        items_before = await get_items_count(session, TEST_USER_ID)

        # Create mock message
        message = MockMessage(
            text=scenario.input,
            user_id=TEST_USER_ID,
            forward_from=scenario.forward_from
        )

        # Run the handler
        try:
            await handle_text(message)
        except Exception as e:
            return TestResult(
                scenario_id=scenario.id,
                passed=False,
                expected={},
                actual={},
                errors=[f"Handler exception: {str(e)}"],
                duration_ms=int((time.time() - start_time) * 1000),
                bot_response="",
                input_text=scenario.input
            )

        # Handle confirmation if needed
        if scenario.confirm is not None and has_pending_state(TEST_USER_ID):
            try:
                await continue_agent_loop(TEST_USER_ID, confirmed=scenario.confirm)
            except Exception as e:
                if verbose:
                    print(f"    Warning: continue_agent_loop error: {e}")

        # Clear any pending state
        clear_pending_state(TEST_USER_ID)

        # Get replies
        replies = message.get_replies()

        # Determine intent from response (heuristic)
        last_intent = detect_intent_from_response(replies, scenario)

        # Check assertions
        result = await check_assertions(
            scenario=scenario,
            replies=replies,
            session=session,
            items_before=items_before,
            last_intent=last_intent
        )

        result.duration_ms = int((time.time() - start_time) * 1000)
        result.input_text = scenario.input

        return result


def detect_intent_from_response(replies: list[str], scenario: Scenario) -> Optional[str]:
    """Try to detect intent from bot response patterns."""
    response = " ".join(replies).lower()

    # Save patterns
    save_patterns = ["сохранил", "записал", "создал", "добавил", "запомнил"]
    if any(p in response for p in save_patterns):
        return "save"

    # Query patterns
    query_patterns = ["нашёл", "найдено", "вот что", "результат", "ничего не найдено"]
    if any(p in response for p in query_patterns):
        return "query"

    # Action patterns
    action_patterns = ["удалил", "обновил", "изменил", "выполнено", "отменено", "подтверд"]
    if any(p in response for p in action_patterns):
        return "action"

    # Chat patterns (greetings, help, etc.)
    chat_patterns = ["привет", "помогу", "умею", "могу", "бот"]
    if any(p in response for p in chat_patterns):
        return "chat"

    # Unclear
    if "уточни" in response or "не понял" in response:
        return "unclear"

    return None


def filter_scenarios(
    scenarios: list[Scenario],
    tag: Optional[str] = None,
    scenario_id: Optional[str] = None
) -> list[Scenario]:
    """Filter scenarios by tag or ID."""
    if scenario_id:
        return [s for s in scenarios if s.id == scenario_id]
    if tag:
        return [s for s in scenarios if tag in s.tags]
    return scenarios


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="E2E Test Runner for Neural Inbox")
    parser.add_argument("--no-cleanup", action="store_true", help="Don't clean up test data after run")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument("--tag", type=str, help="Run only scenarios with this tag")
    parser.add_argument("--scenario", type=str, help="Run only this specific scenario")
    parser.add_argument("--skip-cleanup-before", action="store_true", help="Don't clean up before run")
    args = parser.parse_args()

    print(f"\n{Style.BRIGHT}Neural Inbox E2E Test Runner{Style.RESET_ALL}")
    print("=" * 60)

    # Filter scenarios
    scenarios = filter_scenarios(SCENARIOS, tag=args.tag, scenario_id=args.scenario)
    if not scenarios:
        print(f"{Fore.RED}No scenarios matched filters{Style.RESET_ALL}")
        return 1

    print(f"Running {len(scenarios)} scenarios...")

    # Setup
    if not args.skip_cleanup_before:
        print("Cleaning up test data...")
        await cleanup_test_data()

    print("Ensuring test user exists...")
    await ensure_test_user()

    # Run scenarios
    results: list[TestResult] = []
    for i, scenario in enumerate(scenarios, 1):
        print_scenario_start(i, len(scenarios), scenario, args.verbose)
        result = await run_scenario(scenario, verbose=args.verbose)
        results.append(result)
        print_result(result, args.verbose)

        # Small delay between scenarios
        await asyncio.sleep(0.1)

    # Summary
    print_summary(results)

    # Save report
    report_file = save_json_report(results)
    print(f"\n📄 JSON report saved: {report_file}")

    # Cleanup
    if not args.no_cleanup:
        print("Cleaning up test data...")
        await cleanup_test_data()

    # Return exit code
    failed = sum(1 for r in results if not r.passed)
    return 1 if failed > 0 else 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
