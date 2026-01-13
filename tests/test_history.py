# tests/test_history.py
"""Tests for message history module."""
import pytest
from datetime import datetime

from src.utils.history import MessageHistory, HistoryMessage, message_history, MAX_HISTORY


class TestHistoryMessage:
    """Tests for HistoryMessage dataclass."""

    def test_history_message_creation(self):
        """Test creating HistoryMessage."""
        now = datetime.now()
        msg = HistoryMessage(role="user", content="Hello", timestamp=now)

        assert msg.role == "user"
        assert msg.content == "Hello"
        assert msg.timestamp == now


class TestMessageHistory:
    """Tests for MessageHistory class."""

    @pytest.fixture
    def history(self):
        """Create fresh MessageHistory instance."""
        return MessageHistory()

    def test_add_message(self, history):
        """Test adding a message."""
        history.add(123, "user", "Hello")

        messages = history.get(123)
        assert len(messages) == 1
        assert messages[0].role == "user"
        assert messages[0].content == "Hello"

    def test_add_multiple_messages(self, history):
        """Test adding multiple messages."""
        history.add(123, "user", "Hello")
        history.add(123, "assistant", "Hi there!")
        history.add(123, "user", "How are you?")

        messages = history.get(123)
        assert len(messages) == 3
        assert messages[0].content == "Hello"
        assert messages[1].content == "Hi there!"
        assert messages[2].content == "How are you?"

    def test_max_history_limit(self, history):
        """Test that history is limited to MAX_HISTORY messages."""
        for i in range(MAX_HISTORY + 5):
            history.add(123, "user", f"Message {i}")

        messages = history.get(123)
        assert len(messages) == MAX_HISTORY

        # Should have the most recent messages
        assert messages[-1].content == f"Message {MAX_HISTORY + 4}"

    def test_get_empty_history(self, history):
        """Test getting history for user with no messages."""
        messages = history.get(999)
        assert messages == []

    def test_get_with_limit(self, history):
        """Test getting limited number of messages."""
        for i in range(5):
            history.add(123, "user", f"Message {i}")

        messages = history.get(123, limit=3)
        assert len(messages) == 3
        # Should return last 3 messages
        assert messages[0].content == "Message 2"
        assert messages[2].content == "Message 4"

    def test_separate_user_histories(self, history):
        """Test that different users have separate histories."""
        history.add(123, "user", "User 123 message")
        history.add(456, "user", "User 456 message")

        messages_123 = history.get(123)
        messages_456 = history.get(456)

        assert len(messages_123) == 1
        assert len(messages_456) == 1
        assert messages_123[0].content == "User 123 message"
        assert messages_456[0].content == "User 456 message"

    def test_clear_history(self, history):
        """Test clearing user's history."""
        history.add(123, "user", "Message 1")
        history.add(123, "user", "Message 2")

        history.clear(123)

        messages = history.get(123)
        assert messages == []

    def test_clear_nonexistent_user(self, history):
        """Test clearing history for user that doesn't exist."""
        # Should not raise
        history.clear(999)

    def test_get_context_string(self, history):
        """Test getting formatted context string."""
        history.add(123, "user", "Hello")
        history.add(123, "assistant", "Hi there!")
        history.add(123, "user", "What can you do?")

        context = history.get_context_string(123)

        assert context is not None
        assert "User: Hello" in context
        assert "Bot: Hi there!" in context
        assert "User: What can you do?" in context

    def test_get_context_string_empty(self, history):
        """Test context string for empty history."""
        context = history.get_context_string(999)
        assert context is None

    def test_get_context_string_with_limit(self, history):
        """Test context string with limit."""
        for i in range(5):
            history.add(123, "user", f"Message {i}")

        context = history.get_context_string(123, limit=2)

        assert "Message 3" in context
        assert "Message 4" in context
        assert "Message 0" not in context

    def test_timestamp_is_set(self, history):
        """Test that timestamp is automatically set."""
        before = datetime.now()
        history.add(123, "user", "Test")
        after = datetime.now()

        messages = history.get(123)
        assert before <= messages[0].timestamp <= after


class TestGlobalMessageHistory:
    """Tests for global message_history singleton."""

    def test_singleton_exists(self):
        """Test that global singleton exists."""
        assert message_history is not None
        assert isinstance(message_history, MessageHistory)

    def test_singleton_is_functional(self):
        """Test that singleton can be used."""
        # Use unique user ID to avoid conflicts with other tests
        test_user = 999999

        # Clear any existing data
        message_history.clear(test_user)

        message_history.add(test_user, "user", "Test message")
        messages = message_history.get(test_user)

        assert len(messages) >= 1
        assert messages[-1].content == "Test message"

        # Cleanup
        message_history.clear(test_user)
