# tests/conftest.py
"""Shared fixtures for all tests."""
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock
from dataclasses import dataclass


# Configure pytest-asyncio
pytest_plugins = ('pytest_asyncio',)


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


# Mock OpenAI responses
@dataclass
class MockEmbeddingData:
    embedding: list


@dataclass
class MockEmbeddingResponse:
    data: list


@dataclass
class MockChoice:
    message: MagicMock


@dataclass
class MockChatResponse:
    choices: list


@pytest.fixture
def mock_embedding():
    """Mock embedding vector (1536 dimensions)."""
    return [0.1] * 1536


def create_chat_response(content: str):
    """Helper to create mock chat response."""
    message = MagicMock()
    message.content = content
    choice = MockChoice(message=message)
    return MockChatResponse(choices=[choice])


@pytest.fixture
def mock_router_response():
    """Mock router classification response."""
    return create_chat_response('{"intent": "save", "confidence": 0.95, "reasoning": "test"}')


@pytest.fixture
def mock_classifier_response():
    """Mock classifier response."""
    return create_chat_response('''{
        "type": "task",
        "title": "Test task",
        "due_at_raw": null,
        "due_at_iso": null,
        "priority": "medium",
        "tags": ["#test"],
        "entities": {"people": [], "urls": [], "phones": [], "places": []}
    }''')


# Database fixtures
@pytest.fixture
def mock_session():
    """Mock async database session."""
    session = AsyncMock()
    session.execute = AsyncMock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    session.add = MagicMock()
    return session


# Telegram fixtures
@pytest.fixture
def mock_message():
    """Mock Telegram message."""
    message = AsyncMock()
    message.from_user = MagicMock()
    message.from_user.id = 12345
    message.text = "Test message"
    message.reply = AsyncMock()
    return message
