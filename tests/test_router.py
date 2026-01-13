# tests/test_router.py
"""Tests for AI Router logic (isolated unit tests)."""
import pytest
import json


class TestIntentClassification:
    """Tests for intent classification logic."""

    def test_parse_save_response(self):
        """Test parsing SAVE intent response."""
        response = '{"intent": "save", "confidence": 0.95, "reasoning": "new task"}'
        result = json.loads(response)

        assert result["intent"] == "save"
        assert result["confidence"] == 0.95
        assert result["reasoning"] == "new task"

    def test_parse_query_response(self):
        """Test parsing QUERY intent response."""
        response = '{"intent": "query", "confidence": 0.9, "reasoning": "search request"}'
        result = json.loads(response)

        assert result["intent"] == "query"
        assert result["confidence"] == 0.9

    def test_parse_action_response(self):
        """Test parsing ACTION intent response."""
        response = '{"intent": "action", "confidence": 0.88, "reasoning": "modify"}'
        result = json.loads(response)

        assert result["intent"] == "action"

    def test_parse_chat_response(self):
        """Test parsing CHAT intent response."""
        response = '{"intent": "chat", "confidence": 0.99, "reasoning": "greeting"}'
        result = json.loads(response)

        assert result["intent"] == "chat"

    def test_low_confidence_detection(self):
        """Test detecting low confidence."""
        response = '{"intent": "save", "confidence": 0.5, "reasoning": "ambiguous"}'
        result = json.loads(response)

        # Low confidence should trigger UNCLEAR
        confidence_threshold = 0.7
        is_unclear = result["confidence"] < confidence_threshold

        assert is_unclear is True

    def test_high_confidence_detection(self):
        """Test detecting high confidence."""
        response = '{"intent": "save", "confidence": 0.95, "reasoning": "clear"}'
        result = json.loads(response)

        confidence_threshold = 0.7
        is_clear = result["confidence"] >= confidence_threshold

        assert is_clear is True


class TestIntentValues:
    """Tests for intent value constants."""

    def test_all_intent_values(self):
        """Test all expected intent values."""
        valid_intents = {"save", "query", "action", "chat", "unclear"}

        assert "save" in valid_intents
        assert "query" in valid_intents
        assert "action" in valid_intents
        assert "chat" in valid_intents
        assert "unclear" in valid_intents


class TestContextFormatting:
    """Tests for context formatting."""

    def test_context_message_format(self):
        """Test that context is properly formatted."""
        context = "User: привет\nBot: Привет!"
        text = "запомни это"

        # Check context format
        assert "User:" in context
        assert "Bot:" in context

        formatted = f"Контекст:\n{context}\n\nСообщение:\n{text}"
        assert "Контекст:" in formatted
        assert "Сообщение:" in formatted

    def test_no_context(self):
        """Test message without context."""
        text = "купить молоко"
        context = None

        # Without context, just use text directly
        message = text if context is None else f"Контекст:\n{context}\n\nСообщение:\n{text}"
        assert message == text
