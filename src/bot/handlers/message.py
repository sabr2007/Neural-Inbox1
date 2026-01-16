"""
Message handler - simplified "black hole" approach.
All messages get saved, search queries redirect to WebApp.
AI classification happens in background task.
"""
import asyncio
import logging
import re
import tempfile
from pathlib import Path

from aiogram import Router, F, Bot
from aiogram.types import Message
from aiogram.enums import ContentType, ChatAction

from src.config import MAX_VOICE_DURATION, MAX_FILE_SIZE, config
from src.services.extracted_content import ExtractedContent
from src.services.url_parser import URLParser, extract_urls
from src.services.whisper_transcriber import WhisperTranscriber
from src.services.image_analyzer import ImageAnalyzer
from src.services.pdf_extractor import PDFExtractor
from src.services.document_extractor import DocumentExtractor
from src.ai.classifier import ContentClassifier
from src.ai.embeddings import get_embedding
from src.db.database import get_session
from src.db.repository import UserRepository, ItemRepository
from src.db.models import ItemSource, ItemStatus
from src.bot.keyboards import delete_item_keyboard, webapp_button, reminder_actions_keyboard

logger = logging.getLogger(__name__)

message_router = Router()

# Search query patterns (triggers redirect to WebApp)
SEARCH_PATTERNS = [
    r'\bнайди\b', r'\bнайти\b', r'\bпокажи\b', r'\bпоиск\b',
    r'\bчто у меня\b', r'\bкакие\b', r'\bсписок\b', r'\bгде\b',
    r'\bпоказать\b', r'\bвсе мои\b', r'\bмои задачи\b', r'\bмои заметки\b'
]
SEARCH_REGEX = re.compile('|'.join(SEARCH_PATTERNS), re.IGNORECASE)


def is_search_query(text: str) -> bool:
    """Check if text is a search query that should redirect to WebApp."""
    return bool(SEARCH_REGEX.search(text))


async def download_temp_file(bot: Bot, file_id: str, suffix: str = "") -> Path:
    """Download a file from Telegram to a temporary location."""
    file = await bot.get_file(file_id)
    temp_dir = Path(tempfile.gettempdir()) / "neural_inbox"
    temp_dir.mkdir(exist_ok=True)

    temp_file = temp_dir / f"{file_id}{suffix}"
    await bot.download_file(file.file_path, temp_file)
    return temp_file


async def redirect_to_webapp(message: Message) -> None:
    """Redirect user to WebApp for search and management."""
    keyboard = webapp_button()
    if keyboard:
        await message.reply(
            "Я сохраняю всё, что ты отправляешь 📥\n"
            "Для поиска и управления открой приложение 👇",
            reply_markup=keyboard
        )
    else:
        await message.reply(
            "Я сохраняю всё, что ты отправляешь 📥\n"
            "Поиск и управление доступны в приложении."
        )


async def save_and_classify_background(
    message: Message,
    text: str,
    source: str,
    **kwargs
) -> None:
    """
    Save item instantly with PROCESSING status, then classify in background.

    Flow:
    1. Instantly reply "⏳ Сохраняю..."
    2. Save to DB with status=PROCESSING
    3. Start background task for AI classification
    4. Background task updates item and edits message
    """
    user_id = message.from_user.id

    # 1. Instant response
    status_message = await message.reply("⏳ Сохраняю...")

    async with get_session() as session:
        # Ensure user exists
        user_repo = UserRepository(session)
        await user_repo.get_or_create(user_id)

        # 2. Save with PROCESSING status
        item_repo = ItemRepository(session)
        item = await item_repo.create(
            user_id=user_id,
            type="note",  # Default type, will be updated by classifier
            status=ItemStatus.PROCESSING.value,
            title=text[:100] if text else "Обработка...",
            original_input=text,
            source=source,
            **kwargs
        )
        item_id = item.id

    # 3. Start background classification task
    asyncio.create_task(
        _classify_and_update(
            user_id=user_id,
            item_id=item_id,
            text=text,
            status_message=status_message,
            message=message
        )
    )


async def _classify_and_update(
    user_id: int,
    item_id: int,
    text: str,
    status_message: Message,
    message: Message
) -> None:
    """Background task: classify content with AI and update item."""
    try:
        # AI Classification
        classifier = ContentClassifier()
        classification = await classifier.classify(text)

        # Generate embedding
        embedding_text = f"{classification.title} {text}"
        embedding = await get_embedding(embedding_text)

        async with get_session() as session:
            item_repo = ItemRepository(session)

            # Update item with classification results
            await item_repo.update(
                item_id,
                user_id,
                type=classification.type,
                status=ItemStatus.INBOX.value,
                title=classification.title,
                content=text if len(text) > 100 else None,
                due_at=classification.due_at,
                due_at_raw=classification.due_at_raw,
                priority=classification.priority,
                tags=classification.tags,
                entities=classification.entities,
                embedding=embedding
            )

        # Format success response
        type_emoji = {
            "task": "✅",
            "idea": "💡",
            "note": "📝",
            "resource": "🔗",
            "contact": "👤"
        }
        emoji = type_emoji.get(classification.type, "📝")

        # Build response text
        type_labels = {
            "task": "Задача",
            "idea": "Идея",
            "note": "Заметка",
            "resource": "Ресурс",
            "contact": "Контакт"
        }
        type_label = type_labels.get(classification.type, "Запись")

        response = f"{emoji} {type_label}: {classification.title}"

        if classification.due_at_raw:
            due_display = classification.due_at_raw
            if classification.due_at:
                parsed_date = classification.due_at.strftime("%d.%m.%Y %H:%M")
                due_display += f" ({parsed_date})"
            response += f"\n📅 Срок: {due_display}"

        if classification.tags:
            response += f"\n🏷️ {' '.join(classification.tags)}"

        # Edit the status message with final result
        await status_message.edit_text(
            response,
            reply_markup=delete_item_keyboard(item_id)
        )

    except Exception as e:
        logger.error(f"Background classification failed: {e}")
        # Update message to show error but item is saved
        try:
            await status_message.edit_text(
                "📝 Сохранено (не удалось классифицировать)",
                reply_markup=delete_item_keyboard(item_id)
            )
        except Exception:
            pass


@message_router.message(F.content_type == ContentType.TEXT)
async def handle_text(message: Message) -> None:
    """Handle text messages - check for search, otherwise save."""
    text = message.text.strip()

    if not text:
        return

    # 1. Check for search queries first
    if is_search_query(text):
        await redirect_to_webapp(message)
        return

    # Show typing indicator
    await message.bot.send_chat_action(chat_id=message.chat.id, action=ChatAction.TYPING)

    # Detect and parse URLs (enrich content)
    urls = extract_urls(text)
    if urls:
        url_parser = URLParser()
        result = await url_parser.parse(urls[0])
        if not result.is_error and result.text:
            text = f"{text}\n\n--- Содержимое ссылки ---\n{result.text}"

    # 2. Save everything else
    await save_and_classify_background(message, text, ItemSource.TEXT.value)


@message_router.message(F.content_type == ContentType.VOICE)
async def handle_voice(message: Message) -> None:
    """Handle voice messages - transcribe with Whisper, then save."""
    await message.bot.send_chat_action(chat_id=message.chat.id, action=ChatAction.TYPING)

    voice = message.voice

    # Check duration limit
    if voice.duration > MAX_VOICE_DURATION:
        await message.reply(
            f"Голосовое сообщение слишком длинное ({voice.duration} сек). "
            f"Максимум: {MAX_VOICE_DURATION // 60} минут"
        )
        return

    # Download voice file
    file_path = await download_temp_file(message.bot, voice.file_id, suffix=".ogg")

    try:
        # Transcribe
        transcriber = WhisperTranscriber()
        result = await transcriber.transcribe(file_path, duration=voice.duration)

        if result.is_error:
            await message.reply(result.error)
            return

        text = result.text.strip()
        if not text:
            await message.reply("Не удалось распознать голосовое сообщение.")
            return

        # Show transcription briefly
        await message.reply(f"🎤 {text[:200]}{'...' if len(text) > 200 else ''}")

        # Save transcribed text
        await save_and_classify_background(message, text, ItemSource.VOICE.value)

    finally:
        if file_path.exists():
            file_path.unlink()


@message_router.message(F.content_type == ContentType.PHOTO)
async def handle_photo(message: Message) -> None:
    """Handle photos - analyze with GPT-4o Vision, then save."""
    await message.bot.send_chat_action(chat_id=message.chat.id, action=ChatAction.TYPING)

    photo = message.photo[-1]  # Highest resolution
    caption = message.caption

    file_path = await download_temp_file(message.bot, photo.file_id, suffix=".jpg")

    try:
        analyzer = ImageAnalyzer()
        result = await analyzer.analyze(file_path, caption=caption)

        if result.is_error:
            await message.reply(result.error)
            return

        # Save with extracted text
        await save_and_classify_background(
            message,
            result.text,
            ItemSource.PHOTO.value,
            attachment_file_id=photo.file_id,
            attachment_type="photo"
        )

    finally:
        if file_path.exists():
            file_path.unlink()


@message_router.message(F.content_type == ContentType.DOCUMENT)
async def handle_document(message: Message) -> None:
    """Handle documents - extract text from PDFs, Word docs, etc."""
    await message.bot.send_chat_action(chat_id=message.chat.id, action=ChatAction.TYPING)

    doc = message.document
    file_name = doc.file_name or "document"
    ext = Path(file_name).suffix.lower()

    # Check file size
    if doc.file_size > MAX_FILE_SIZE:
        await message.reply(
            f"Файл слишком большой ({doc.file_size // 1024 // 1024}MB). "
            f"Максимум: {MAX_FILE_SIZE // 1024 // 1024}MB"
        )
        return

    file_path = await download_temp_file(message.bot, doc.file_id, suffix=ext)

    try:
        # Extract text based on file type
        if ext == ".pdf":
            extractor = PDFExtractor()
            result = await extractor.extract(file_path)
            source = ItemSource.PDF.value
        elif ext in (".docx", ".doc"):
            extractor = DocumentExtractor()
            result = await extractor.extract(file_path)
            source = ItemSource.PDF.value
        else:
            await message.reply(f"Формат {ext} пока не поддерживается")
            return

        if result.is_error:
            await message.reply(result.error)
            return

        # Notify about extraction
        title_info = f"📄 {result.title}" if result.title else f"📄 {file_name}"
        pages_info = result.metadata.get("page_count", result.metadata.get("estimated_pages", "?"))
        await message.reply(f"{title_info}\nСтраниц: {pages_info}")

        # Save extracted text
        await save_and_classify_background(
            message,
            result.text,
            source,
            attachment_file_id=doc.file_id,
            attachment_type="document"
        )

    finally:
        if file_path.exists():
            file_path.unlink()


@message_router.message(F.forward_from | F.forward_from_chat)
async def handle_forward(message: Message) -> None:
    """Handle forwarded messages - save with origin context."""
    await message.bot.send_chat_action(chat_id=message.chat.id, action=ChatAction.TYPING)

    text = message.text or message.caption or ""
    origin = None

    if message.forward_from:
        origin = message.forward_from.full_name
    elif message.forward_from_chat:
        origin = message.forward_from_chat.title

    if text:
        await save_and_classify_background(
            message,
            text,
            ItemSource.FORWARD.value,
            origin_user_name=origin
        )
    else:
        await message.reply("Переслано, но не удалось извлечь текст.")
