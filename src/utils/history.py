# neural-inbox1/src/utils/history.py
"""Message history for conversation context."""
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Any

# Max messages per user
MAX_HISTORY = 6


@dataclass
class HistoryMessage:
    role: str  # "user" or "assistant"
    content: str
    timestamp: datetime
    metadata: Optional[Dict[str, Any]] = field(default=None)


class MessageHistory:
    """In-memory message history storage.

    For production, replace with Redis.
    """

    def __init__(self):
        self._storage: Dict[int, deque[HistoryMessage]] = {}

    def add(
        self,
        user_id: int,
        role: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """Add message to user's history.

        Args:
            user_id: Telegram user ID
            role: "user" or "assistant"
            content: Message text
            metadata: Optional metadata (e.g., search_results with item IDs)
        """
        if user_id not in self._storage:
            self._storage[user_id] = deque(maxlen=MAX_HISTORY)

        self._storage[user_id].append(
            HistoryMessage(
                role=role,
                content=content,
                timestamp=datetime.now(),
                metadata=metadata
            )
        )

    def get(self, user_id: int, limit: Optional[int] = None) -> List[HistoryMessage]:
        """Get user's message history."""
        if user_id not in self._storage:
            return []

        messages = list(self._storage[user_id])
        if limit:
            return messages[-limit:]
        return messages

    def get_context_string(self, user_id: int, limit: int = 5) -> Optional[str]:
        """Get formatted context string for LLM.

        Returns None if no history.
        """
        messages = self.get(user_id, limit)
        if not messages:
            return None

        lines = []
        for msg in messages:
            prefix = "User" if msg.role == "user" else "Bot"
            lines.append(f"{prefix}: {msg.content}")

        return "\n".join(lines)

    def clear(self, user_id: int) -> None:
        """Clear user's history."""
        if user_id in self._storage:
            del self._storage[user_id]

    def get_last_search_results(self, user_id: int) -> Optional[List[Dict[str, Any]]]:
        """Get last search results from history metadata.

        Returns list of {id, title, position} or None if no recent search.
        """
        messages = self.get(user_id)
        # Search backwards for last assistant message with search_results
        for msg in reversed(messages):
            if msg.role == "assistant" and msg.metadata:
                if "search_results" in msg.metadata:
                    return msg.metadata["search_results"]
        return None

    def get_context_with_search_info(self, user_id: int, limit: int = 5) -> Optional[str]:
        """Get formatted context with search results info for agent.

        Includes search result IDs so agent can reference them.
        """
        messages = self.get(user_id, limit)
        if not messages:
            return None

        lines = []
        for msg in messages:
            prefix = "User" if msg.role == "user" else "Bot"
            lines.append(f"{prefix}: {msg.content}")

            # Add search results context if present
            if msg.role == "assistant" and msg.metadata:
                search_results = msg.metadata.get("search_results")
                if search_results:
                    lines.append("  [Результаты поиска:")
                    for r in search_results:
                        lines.append(f"    {r['position']}. ID={r['id']} \"{r['title']}\"")
                    lines.append("  ]")

        return "\n".join(lines)


# Singleton instance
message_history = MessageHistory()
