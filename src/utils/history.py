# neural-inbox1/src/utils/history.py
"""Message history for conversation context."""
from collections import deque
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional

# Max messages per user
MAX_HISTORY = 6


@dataclass
class HistoryMessage:
    role: str  # "user" or "assistant"
    content: str
    timestamp: datetime


class MessageHistory:
    """In-memory message history storage.

    For production, replace with Redis.
    """

    def __init__(self):
        self._storage: Dict[int, deque[HistoryMessage]] = {}

    def add(self, user_id: int, role: str, content: str) -> None:
        """Add message to user's history."""
        if user_id not in self._storage:
            self._storage[user_id] = deque(maxlen=MAX_HISTORY)

        self._storage[user_id].append(
            HistoryMessage(role=role, content=content, timestamp=datetime.now())
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


# Singleton instance
message_history = MessageHistory()
