"""Mock Telegram objects for E2E tests."""

import random
from datetime import datetime
from typing import Optional


TEST_USER_ID = 999999999


class MockBot:
    """Mock Telegram Bot."""

    async def send_chat_action(self, chat_id: int, action: str, **kwargs):
        """Simulate typing indicator - does nothing in tests."""
        pass

    async def get_file(self, file_id: str):
        """Mock file download - not supported in E2E tests."""
        raise NotImplementedError("File download not supported in E2E tests")

    async def download_file(self, file_path: str, destination: str):
        """Mock file download - not supported in E2E tests."""
        raise NotImplementedError("File download not supported in E2E tests")


# Shared bot instance for all mock messages
_mock_bot = MockBot()


class MockUser:
    """Mock Telegram User."""

    def __init__(self, user_id: int = TEST_USER_ID):
        self.id = user_id
        self.first_name = "TestUser"
        self.username = "test_user"
        self.is_bot = False
        self.language_code = "ru"


class MockChat:
    """Mock Telegram Chat."""

    def __init__(self, chat_id: int = TEST_USER_ID):
        self.id = chat_id
        self.type = "private"


class MockForwardUser:
    """Mock forwarded message sender."""

    def __init__(self, name: str):
        self.first_name = name
        self.id = random.randint(100000, 999999)
        self.username = None
        self.is_bot = False


class MockMessage:
    """Mock Telegram Message for testing."""

    def __init__(
        self,
        text: str,
        user_id: int = TEST_USER_ID,
        forward_from: Optional[str] = None
    ):
        self.text = text
        self.from_user = MockUser(user_id)
        self.chat = MockChat(user_id)
        self.message_id = random.randint(1000, 9999)
        self.date = datetime.now()
        self._replies: list[str] = []
        self._reply_markups: list = []

        # Forward handling
        if forward_from:
            self.forward_from = MockForwardUser(forward_from)
            self.forward_date = datetime.now()
        else:
            self.forward_from = None
            self.forward_date = None

        # Bot instance for send_chat_action etc.
        self.bot = _mock_bot

        # Other attributes aiogram might check
        self.photo = None
        self.document = None
        self.voice = None
        self.video = None
        self.audio = None
        self.caption = None
        self.entities = None
        self.reply_to_message = None

    async def answer(self, text: str, **kwargs) -> "MockMessage":
        """Simulate bot answer."""
        self._replies.append(text)
        if "reply_markup" in kwargs:
            self._reply_markups.append(kwargs["reply_markup"])
        return self

    async def reply(self, text: str, **kwargs) -> "MockMessage":
        """Simulate bot reply."""
        self._replies.append(text)
        if "reply_markup" in kwargs:
            self._reply_markups.append(kwargs["reply_markup"])
        return self

    def get_replies(self) -> list[str]:
        """Get all bot replies."""
        return self._replies

    def get_last_reply(self) -> Optional[str]:
        """Get the last bot reply."""
        return self._replies[-1] if self._replies else None

    def has_confirmation_keyboard(self) -> bool:
        """Check if any reply had a confirmation keyboard."""
        return len(self._reply_markups) > 0


class MockCallbackQuery:
    """Mock Telegram CallbackQuery for confirmation tests."""

    def __init__(self, data: str, user_id: int = TEST_USER_ID):
        self.data = data
        self.from_user = MockUser(user_id)
        self.message = MockMessage("", user_id)
        self._answered = False
        self._answer_text: Optional[str] = None

    async def answer(self, text: Optional[str] = None, **kwargs):
        """Simulate callback answer."""
        self._answered = True
        self._answer_text = text
