# neural-inbox1/src/ai/batch_confirmations.py
"""Storage for pending batch operations requiring confirmation."""
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
import secrets


@dataclass
class PendingOperation:
    """A pending batch operation awaiting user confirmation."""
    token: str
    action: str  # "update" | "delete" | "move_items" | "delete_project"
    user_id: int
    filter: Dict[str, Any]
    updates: Optional[Dict[str, Any]]  # for update operations
    matched_ids: List[int]
    created_at: datetime

    def is_expired(self) -> bool:
        """Check if operation has expired (5 minute TTL)."""
        return datetime.utcnow() > self.created_at + timedelta(minutes=5)


# In-memory storage
_pending: Dict[str, PendingOperation] = {}


def generate_token(prefix: str = "op") -> str:
    """Generate a unique token for an operation."""
    return f"{prefix}_{secrets.token_urlsafe(8)}"


def store_pending(operation: PendingOperation) -> None:
    """Store a pending operation."""
    _cleanup_expired()
    _pending[operation.token] = operation


def get_pending(token: str) -> Optional[PendingOperation]:
    """Get a pending operation by token if not expired."""
    op = _pending.get(token)
    if op and not op.is_expired():
        return op
    return None


def clear_pending(token: str) -> None:
    """Clear a pending operation by token."""
    _pending.pop(token, None)


def _cleanup_expired() -> None:
    """Remove expired operations from storage."""
    expired = [k for k, v in _pending.items() if v.is_expired()]
    for k in expired:
        del _pending[k]
