"""
Message handler - routes ALL inputs through AI Router.
No commands, only natural language understanding.
"""
import logging
from typing import Optional

from aiogram import Router, F
from aiogram.types import Message
from aiogram.enums import ContentType

from src.ai.router import router as intent_router, Intent
from src.ai.classifier import ContentClassifier
from src.db.database import get_session
from src.db.repository import UserRepository, ItemRepository
from src.db.models import ItemSource
from src.bot.keyboards import clarification_keyboard, item_actions_keyboard

logger = logging.getLogger(__name__)

message_router = Router()

# Store pending clarifications (in production use Redis)
pending_clarifications: dict[int, str] = {}


@message_router.message(F.content_type == ContentType.TEXT)
async def handle_text(message: Message) -> None:
    """Handle text messages - route through AI."""
    user_id = message.from_user.id
    text = message.text.strip()

    if not text:
        return

    # Check if this is a response to a clarification
    if user_id in pending_clarifications:
        # Clear pending and process as save
        original_text = pending_clarifications.pop(user_id)
        await process_save(message, original_text, ItemSource.TEXT.value)
        return

    # Route through AI
    result, clarification = await intent_router.classify_with_clarification(text)

    logger.info(f"Intent: {result.intent.value}, confidence: {result.confidence}")

    if result.intent == Intent.UNCLEAR:
        # Store original text and ask for clarification
        pending_clarifications[user_id] = text
        await message.reply(
            clarification or "Сохранить это или найти в записях?",
            reply_markup=clarification_keyboard(text)
        )
        return

    if result.intent == Intent.SAVE:
        await process_save(message, text, ItemSource.TEXT.value)

    elif result.intent == Intent.QUERY:
        await process_query(message, text)

    elif result.intent == Intent.ACTION:
        await process_action(message, text)

    elif result.intent == Intent.CHAT:
        await process_chat(message, text)


@message_router.message(F.content_type == ContentType.VOICE)
async def handle_voice(message: Message) -> None:
    """Handle voice messages - transcribe with Whisper, then route."""
    # TODO: Implement Whisper transcription
    await message.reply(
        "Голосовые сообщения скоро будут поддерживаться! "
        "Пока отправьте текстом."
    )


@message_router.message(F.content_type == ContentType.PHOTO)
async def handle_photo(message: Message) -> None:
    """Handle photos - use GPT-4o Vision for understanding."""
    # TODO: Implement GPT-4o Vision processing
    caption = message.caption or ""

    if caption:
        # Process caption as text, note that there's a photo
        await message.reply(
            "Сохраняю фото с описанием. "
            "Скоро добавлю распознавание содержимого изображений!"
        )
        await process_save(
            message,
            f"[Фото] {caption}",
            ItemSource.PHOTO.value,
            attachment_file_id=message.photo[-1].file_id,
            attachment_type="photo"
        )
    else:
        await message.reply(
            "Получил фото! Добавьте описание, чтобы я мог его сохранить."
        )


@message_router.message(F.content_type == ContentType.DOCUMENT)
async def handle_document(message: Message) -> None:
    """Handle documents - extract text from PDFs, etc."""
    doc = message.document
    caption = message.caption or doc.file_name or "Документ"

    # TODO: Implement PDF extraction
    await message.reply(
        f"Сохраняю документ: {doc.file_name}\n"
        "Скоро добавлю извлечение текста из PDF!"
    )
    await process_save(
        message,
        f"[Документ] {caption}",
        ItemSource.PDF.value,
        attachment_file_id=doc.file_id,
        attachment_type="document"
    )


@message_router.message(F.forward_from | F.forward_from_chat)
async def handle_forward(message: Message) -> None:
    """Handle forwarded messages - save with origin context."""
    text = message.text or message.caption or ""
    origin = None

    if message.forward_from:
        origin = message.forward_from.full_name
    elif message.forward_from_chat:
        origin = message.forward_from_chat.title

    if text:
        await process_save(
            message,
            text,
            ItemSource.FORWARD.value,
            origin_user_name=origin
        )
    else:
        await message.reply("Переслано, но не удалось извлечь текст.")


async def process_save(
    message: Message,
    text: str,
    source: str,
    **kwargs
) -> None:
    """Process SAVE intent - classify and save item."""
    user_id = message.from_user.id

    # Classify content type
    classifier = ContentClassifier()
    classification = await classifier.classify(text)

    async with get_session() as session:
        # Ensure user exists
        user_repo = UserRepository(session)
        await user_repo.get_or_create(user_id)

        # Save item
        item_repo = ItemRepository(session)
        item = await item_repo.create(
            user_id=user_id,
            type=classification.type,
            title=classification.title,
            content=text if len(text) > 100 else None,
            original_input=text,
            source=source,
            due_at=classification.due_at,
            due_at_raw=classification.due_at_raw,
            priority=classification.priority,
            tags=classification.tags,
            entities=classification.entities,
            **kwargs
        )

        # Format response
        type_emoji = {
            "task": "",
            "idea": "",
            "note": "",
            "resource": "",
            "contact": "",
            "event": ""
        }
        emoji = type_emoji.get(classification.type, "")

        response = f"{emoji} Сохранено: {classification.title}"

        if classification.due_at_raw:
            response += f"\nСрок: {classification.due_at_raw}"

        if classification.tags:
            response += f"\nТеги: {' '.join(classification.tags)}"

        await message.reply(
            response,
            reply_markup=item_actions_keyboard(item.id, classification.type)
        )


async def process_query(message: Message, text: str) -> None:
    """Process QUERY intent - search and return results."""
    # TODO: Implement hybrid search
    await message.reply(
        "Ищу в твоих записях...\n"
        "(Поиск будет добавлен в следующей версии)"
    )


async def process_action(message: Message, text: str) -> None:
    """Process ACTION intent - modify existing items."""
    # TODO: Implement action processing with AI agent
    await message.reply(
        "Понял, нужно изменить что-то существующее.\n"
        "(Действия будут добавлены в следующей версии)"
    )


async def process_chat(message: Message, text: str) -> None:
    """Process CHAT intent - respond to small talk."""
    greetings = ["привет", "здравствуй", "хай", "hello", "hi"]
    thanks = ["спасибо", "благодарю", "thanks"]

    text_lower = text.lower()

    if any(g in text_lower for g in greetings):
        await message.reply(
            "Привет! Я твой второй мозг в Telegram.\n"
            "Просто отправляй мне что угодно - я сохраню и помогу найти."
        )
    elif any(t in text_lower for t in thanks):
        await message.reply("Всегда пожалуйста!")
    else:
        await message.reply(
            "Я готов сохранять и искать твои заметки, задачи и идеи. "
            "Просто отправь мне что-нибудь!"
        )
