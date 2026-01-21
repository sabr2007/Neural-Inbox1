"""
Message handler - intelligent agent approach.
All messages are processed by IntelligentAgent for multi-parsing and smart responses.
"""
import asyncio
import logging
import re
import tempfile
from pathlib import Path
from typing import Optional, Dict, Any
from zoneinfo import ZoneInfo

from aiogram import Router, F, Bot
from aiogram.types import Message
from aiogram.enums import ContentType, ChatAction

# Default timezone for displaying dates to users
DEFAULT_TIMEZONE = "Asia/Almaty"

from src.config import MAX_VOICE_DURATION, MAX_FILE_SIZE
from src.services.url_parser import URLParser, extract_urls
from src.services.whisper_transcriber import WhisperTranscriber
from src.services.image_analyzer import ImageAnalyzer
from src.services.pdf_extractor import PDFExtractor
from src.services.document_extractor import DocumentExtractor
from src.ai.agent import IntelligentAgent, AgentError
from src.db.database import get_session
from src.db.repository import UserRepository, ItemRepository
from src.db.models import ItemSource, ItemStatus
from src.bot.keyboards import delete_item_keyboard, webapp_button

logger = logging.getLogger(__name__)

message_router = Router()

# Patterns that trigger redirect to WebApp (search and management commands)
# Bot only accepts data input (notes via text, voice, photo, files)
# Any management/search actions redirect to WebApp
WEBAPP_REDIRECT_PATTERNS = [
    # Search patterns
    r'\bнайди\b', r'\bнайти\b', r'\bпокажи\b', r'\bпоиск\b',
    r'\bчто у меня\b', r'\bкакие\b', r'\bсписок\b', r'\bгде\b',
    r'\bпоказать\b', r'\bвсе мои\b', r'\bмои задачи\b', r'\bмои заметки\b',

    # Project management
    r'\bсоздай проект\b', r'\bновый проект\b', r'\bудали проект\b',
    r'\bпереименуй проект\b', r'\bизмени проект\b',

    # Item management (edit, delete, move)
    r'\bудали\b', r'\bудалить\b', r'\bизмени\b', r'\bизменить\b',
    r'\bредактируй\b', r'\bредактировать\b', r'\bотредактируй\b',
    r'\bперенеси\b', r'\bперенести\b', r'\bпереместить\b', r'\bпереместi\b',
    r'\bотметь\b', r'\bотметить\b', r'\bзавершить\b', r'\bзаверши\b',

    # Send/export requests
    r'\bотправь\b', r'\bотправить\b', r'\bпришли\b', r'\bприслать\b',
    r'\bэкспорт\b', r'\bэкспортируй\b', r'\bскачать\b', r'\bскачай\b',

    # View/open requests
    r'\bоткрой\b', r'\bоткрыть\b', r'\bпросмотр\b', r'\bпросмотреть\b',

    # Status/settings
    r'\bстатус\b', r'\bнастройки\b', r'\bнастроить\b', r'\bстатистика\b',
]
WEBAPP_REDIRECT_REGEX = re.compile('|'.join(WEBAPP_REDIRECT_PATTERNS), re.IGNORECASE)


def should_redirect_to_webapp(text: str) -> bool:
    """Check if text is a management/search command that should redirect to WebApp."""
    return bool(WEBAPP_REDIRECT_REGEX.search(text))


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
            "Я сохраняю всё, что ты отправляешь\n"
            "Для поиска и управления открой приложение",
            reply_markup=keyboard
        )
    else:
        await message.reply(
            "Я сохраняю всё, что ты отправляешь\n"
            "Поиск и управление доступны в приложении."
        )


async def process_with_agent(
    message: Message,
    text: str,
    source: str,
    metadata: Optional[Dict[str, Any]] = None
) -> None:
    """
    Process message with IntelligentAgent.

    Flow:
    1. Reply "⏳ Обрабатываю..."
    2. Ensure user exists
    3. Start background task with agent
    4. Handle result (edit message accordingly)
    
    Args:
        message: Telegram message
        text: Text to process
        source: Source type (text, voice, photo, pdf, etc.)
        metadata: Optional file attachment metadata (file_id, type, filename)
    """
    user_id = message.from_user.id

    # 1. Instant response
    status_message = await message.reply("⏳ Обрабатываю...")

    # 2. Ensure user exists
    async with get_session() as session:
        user_repo = UserRepository(session)
        await user_repo.get_or_create(user_id)

    # 3. Start background agent task
    asyncio.create_task(
        _process_with_agent(
            user_id=user_id,
            text=text,
            source=source,
            status_message=status_message,
            metadata=metadata
        )
    )


async def _process_with_agent(
    user_id: int,
    text: str,
    source: str,
    status_message: Message,
    metadata: Optional[Dict[str, Any]] = None
) -> None:
    """Background task: process with IntelligentAgent."""
    agent = IntelligentAgent()

    try:
        result = await asyncio.wait_for(
            agent.process(user_id, text, source, metadata=metadata),
            timeout=30.0
        )

        # Handle empty result (nothing created, no chat response)
        if result.is_empty:
            await status_message.delete()
            return

        # Handle chat-only response
        if result.chat_response and not result.items_created:
            await status_message.edit_text(result.chat_response)
            return

        # Handle items created
        if result.items_created:
            response = _format_items_response(result.items_created, result.links_created)

            # If single item, show delete button
            if len(result.items_created) == 1:
                await status_message.edit_text(
                    response,
                    reply_markup=delete_item_keyboard(result.items_created[0].id)
                )
            else:
                await status_message.edit_text(response)

            # If there's also a chat response, send it separately
            if result.chat_response:
                await status_message.answer(result.chat_response)

    except asyncio.TimeoutError:
        logger.error(f"Agent timeout for user {user_id}")
        await _fallback_save(user_id, text, source, status_message, metadata)

    except AgentError as e:
        logger.error(f"Agent error for user {user_id}: {e}")
        await _fallback_save(user_id, text, source, status_message, metadata)

    except Exception as e:
        logger.error(f"Unexpected error for user {user_id}: {e}", exc_info=True)
        await _fallback_save(user_id, text, source, status_message, metadata)


def _format_items_response(items, links) -> str:
    """Format response message for created items."""
    type_emoji = {
        "task": "✅",
        "idea": "💡",
        "note": "📝",
        "resource": "🔗",
        "contact": "👤"
    }
    type_labels = {
        "task": "Задача",
        "idea": "Идея",
        "note": "Заметка",
        "resource": "Ресурс",
        "contact": "Контакт"
    }

    if len(items) == 1:
        item = items[0]
        emoji = type_emoji.get(item.type, "📝")
        label = type_labels.get(item.type, "Запись")
        response = f"{emoji} {label}: {item.title}"

        if item.due_at:
            # Convert to user's timezone for display (due_at is stored in UTC)
            tz = ZoneInfo(DEFAULT_TIMEZONE)
            due_local = item.due_at.astimezone(tz)
            due_display = due_local.strftime("%d.%m.%Y %H:%M")
            response += f"\n📅 Срок: {due_display}"
        elif item.due_at_raw:
            # Fallback to raw if parsing failed
            response += f"\n📅 Срок: {item.due_at_raw}"

        if item.tags:
            response += f"\n🏷️ {' '.join(item.tags)}"

        if links:
            response += f"\n🔗 Связано с {len(links)} записями"

        return response

    # Multiple items
    lines = [f"✨ Создано {len(items)} записей:"]
    for item in items:
        emoji = type_emoji.get(item.type, "📝")
        lines.append(f"  {emoji} {item.title[:50]}")

    if links:
        lines.append(f"\n🔗 Создано {len(links)} связей")

    return "\n".join(lines)


async def _fallback_save(
    user_id: int,
    text: str,
    source: str,
    status_message: Message,
    metadata: Optional[Dict[str, Any]] = None
) -> None:
    """Fallback: save original text as note in Inbox."""
    try:
        async with get_session() as session:
            item_repo = ItemRepository(session)
            
            # Prepare attachment fields from metadata
            attachment_kwargs = {}
            if metadata:
                attachment_kwargs = {
                    "attachment_file_id": metadata.get("attachment_file_id"),
                    "attachment_type": metadata.get("attachment_type"),
                    "attachment_filename": metadata.get("attachment_filename")
                }
            
            item = await item_repo.create(
                user_id=user_id,
                type="note",
                status=ItemStatus.INBOX.value,
                title=text[:100] + "..." if len(text) > 100 else text,
                content=text,
                original_input=text,
                source=source,
                **attachment_kwargs
            )

        await status_message.edit_text(
            "⚠️ Ошибка обработки, но я сохранил оригинал в Inbox",
            reply_markup=delete_item_keyboard(item.id)
        )
    except Exception as e:
        logger.error(f"Fallback save failed: {e}")
        try:
            await status_message.edit_text("❌ Ошибка сохранения")
        except Exception:
            pass


@message_router.message(F.content_type == ContentType.TEXT)
async def handle_text(message: Message) -> None:
    """Handle text messages - check for search, otherwise process with agent."""
    text = message.text.strip()

    if not text:
        return

    # 1. Check for management/search commands - redirect to WebApp
    if should_redirect_to_webapp(text):
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

    # 2. Process with agent
    await process_with_agent(message, text, ItemSource.TEXT.value)


@message_router.message(F.content_type == ContentType.VOICE)
async def handle_voice(message: Message) -> None:
    """Handle voice messages - transcribe with Whisper, then process with agent."""
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

        # Process with agent
        await process_with_agent(message, text, ItemSource.VOICE.value)

    finally:
        if file_path.exists():
            file_path.unlink()


@message_router.message(F.content_type == ContentType.PHOTO)
async def handle_photo(message: Message) -> None:
    """Handle photos - analyze with GPT-4o Vision, then process with agent."""
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

        # Prepare metadata for attachment inheritance
        metadata = {
            "attachment_file_id": photo.file_id,
            "attachment_type": "photo",
            "attachment_filename": None  # Photos don't have filenames
        }

        # Process with agent
        await process_with_agent(message, result.text, ItemSource.PHOTO.value, metadata=metadata)

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

        # Prepare metadata for attachment inheritance
        metadata = {
            "attachment_file_id": doc.file_id,
            "attachment_type": "document",
            "attachment_filename": file_name
        }

        # Process with agent
        await process_with_agent(message, result.text, source, metadata=metadata)

    finally:
        if file_path.exists():
            file_path.unlink()


@message_router.message(F.forward_from | F.forward_from_chat)
async def handle_forward(message: Message) -> None:
    """Handle forwarded messages - process with agent."""
    await message.bot.send_chat_action(chat_id=message.chat.id, action=ChatAction.TYPING)

    text = message.text or message.caption or ""

    if text:
        await process_with_agent(message, text, ItemSource.FORWARD.value)
    else:
        await message.reply("Переслано, но не удалось извлечь текст.")
