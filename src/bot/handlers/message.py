"""
Message handler - routes ALL inputs through AI Router.
No commands, only natural language understanding.
"""
import logging
import tempfile
from pathlib import Path

from aiogram import Router, F, Bot
from aiogram.types import Message
from aiogram.enums import ContentType, ChatAction

from src.ai.router import router as intent_router, Intent
from src.config import MAX_VOICE_DURATION, MAX_FILE_SIZE
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
from src.db.search import hybrid_search
from src.db.models import ItemSource
from src.bot.keyboards import clarification_keyboard, item_actions_keyboard, agent_confirmation_keyboard
from src.utils.history import message_history

logger = logging.getLogger(__name__)

message_router = Router()


async def download_temp_file(bot: Bot, file_id: str, suffix: str = "") -> Path:
    """Download a file from Telegram to a temporary location."""
    file = await bot.get_file(file_id)
    temp_dir = Path(tempfile.gettempdir()) / "neural_inbox"
    temp_dir.mkdir(exist_ok=True)

    # Create temp file with appropriate suffix
    temp_file = temp_dir / f"{file_id}{suffix}"
    await bot.download_file(file.file_path, temp_file)
    return temp_file

# Store pending clarifications (in production use Redis)
pending_clarifications: dict[int, str] = {}


@message_router.message(F.content_type == ContentType.TEXT)
async def handle_text(message: Message) -> None:
    """Handle text messages - route through AI."""
    user_id = message.from_user.id
    text = message.text.strip()

    if not text:
        return

    # Show typing indicator
    await message.bot.send_chat_action(chat_id=message.chat.id, action=ChatAction.TYPING)

    # Check if this is a response to a clarification
    if user_id in pending_clarifications:
        # Clear pending and process as save
        original_text = pending_clarifications.pop(user_id)
        await process_save(message, original_text, ItemSource.TEXT.value)
        return

    # Detect and parse URLs
    urls = extract_urls(text)
    if urls:
        url_parser = URLParser()
        result = await url_parser.parse(urls[0])
        if not result.is_error and result.text:
            text = f"{text}\n\n--- Содержимое ссылки ---\n{result.text}"

    # Get conversation context (last 5 messages)
    context = message_history.get_context_string(user_id, limit=5)

    # Save user message to history
    message_history.add(user_id, "user", text)

    # Route through AI with context
    result, clarification = await intent_router.classify_with_clarification(text, context)

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
    """Handle voice messages - transcribe with Whisper, then route through AI."""
    # Show typing indicator
    await message.bot.send_chat_action(chat_id=message.chat.id, action=ChatAction.TYPING)

    user_id = message.from_user.id
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

        # Show transcription
        await message.reply(f"🎤 Распознано: {text[:200]}{'...' if len(text) > 200 else ''}")

        # Save to history
        message_history.add(user_id, "user", text)

        # Route through AI intent classifier (same as text messages)
        context = message_history.get_context_string(user_id, limit=5)
        router_result, clarification = await intent_router.classify_with_clarification(text, context)

        logger.info(f"Voice intent: {router_result.intent.value}, confidence: {router_result.confidence}")

        if router_result.intent == Intent.UNCLEAR:
            pending_clarifications[user_id] = text
            await message.reply(
                clarification or "Сохранить это или найти в записях?",
                reply_markup=clarification_keyboard(text)
            )
        elif router_result.intent == Intent.SAVE:
            await process_save(message, text, ItemSource.VOICE.value)
        elif router_result.intent == Intent.QUERY:
            await process_query(message, text)
        elif router_result.intent == Intent.ACTION:
            await process_action(message, text)
        elif router_result.intent == Intent.CHAT:
            await process_chat(message, text)

    finally:
        # Cleanup temp file
        if file_path.exists():
            file_path.unlink()


@message_router.message(F.content_type == ContentType.PHOTO)
async def handle_photo(message: Message) -> None:
    """Handle photos - use GPT-4o Vision for understanding."""
    # Show typing indicator
    await message.bot.send_chat_action(chat_id=message.chat.id, action=ChatAction.TYPING)

    photo = message.photo[-1]  # Get highest resolution
    caption = message.caption

    # Download photo
    file_path = await download_temp_file(message.bot, photo.file_id, suffix=".jpg")

    try:
        # Analyze image
        analyzer = ImageAnalyzer()
        result = await analyzer.analyze(file_path, caption=caption)

        if result.is_error:
            await message.reply(result.error)
            return

        # Save with extracted text
        await process_save(
            message,
            result.text,
            ItemSource.PHOTO.value,
            attachment_file_id=photo.file_id,
            attachment_type="photo"
        )

    finally:
        # Cleanup temp file
        if file_path.exists():
            file_path.unlink()


@message_router.message(F.content_type == ContentType.DOCUMENT)
async def handle_document(message: Message) -> None:
    """Handle documents - extract text from PDFs, Word docs, etc."""
    # Show typing indicator
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

    # Download document
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
            source = ItemSource.PDF.value  # Using PDF source for all documents
        else:
            await message.reply(f"Формат {ext} пока не поддерживается")
            return

        if result.is_error:
            await message.reply(result.error)
            return

        # Notify user about extraction
        title_info = f"📄 {result.title}" if result.title else f"📄 {file_name}"
        pages_info = result.metadata.get("page_count", result.metadata.get("estimated_pages", "?"))
        await message.reply(f"{title_info}\nСтраниц: {pages_info}")

        # Save extracted text
        await process_save(
            message,
            result.text,
            source,
            attachment_file_id=doc.file_id,
            attachment_type="document"
        )

    finally:
        # Cleanup temp file
        if file_path.exists():
            file_path.unlink()


@message_router.message(F.forward_from | F.forward_from_chat)
async def handle_forward(message: Message) -> None:
    """Handle forwarded messages - save with origin context."""
    # Show typing indicator
    await message.bot.send_chat_action(chat_id=message.chat.id, action=ChatAction.TYPING)

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

        # Generate embedding for semantic search
        embedding_text = f"{classification.title} {text}"
        embedding = await get_embedding(embedding_text)
        if embedding:
            await item_repo.update(item.id, user_id, embedding=embedding)

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
            # Format: "Срок: завтра к двум (16.01.2026 14:00)"
            due_display = classification.due_at_raw
            if classification.due_at:
                parsed_date = classification.due_at.strftime("%d.%m.%Y %H:%M")
                due_display += f" ({parsed_date})"
            response += f"\n📅 Срок: {due_display}"

        if classification.tags:
            response += f"\n🏷️ Теги: {' '.join(classification.tags)}"

        await message.reply(
            response,
            reply_markup=item_actions_keyboard(item.id, classification.type)
        )

        # Save bot response to history
        message_history.add(user_id, "assistant", response)


async def process_query(message: Message, text: str) -> None:
    """Process QUERY intent - search and return results.

    Logic:
    - If top_score > 0.4: show results
    - If top_score <= 0.4 or no results: fallback to agent for reformulation
    - If 1 result: show full content
    - If 2+ results: show list with inline buttons
    """
    from src.bot.keyboards import search_result_buttons_keyboard
    from src.db.repository import ItemRepository

    user_id = message.from_user.id
    SCORE_THRESHOLD = 0.4

    async with get_session() as session:
        results = await hybrid_search(session, user_id, text, limit=5)

        # Check if results are good enough
        top_score = results[0].score if results else 0

        # Fallback to agent if results are poor
        if not results or top_score <= SCORE_THRESHOLD:
            # Try agent reformulation
            agent_result = await _search_with_agent_fallback(user_id, text, session)
            if agent_result:
                await message.reply(agent_result)
                message_history.add(user_id, "assistant", agent_result)
                return
            else:
                response = "Ничего не нашел по твоему запросу."
                await message.reply(response)
                message_history.add(user_id, "assistant", response)
                return

        type_emoji = {
            "task": "📝", "idea": "💡", "note": "📄",
            "resource": "🔗", "contact": "👤", "event": "📅"
        }

        # Build search results metadata for agent context
        search_metadata = {
            "search_results": [
                {"id": r.id, "title": r.title, "position": i}
                for i, r in enumerate(results, 1)
            ]
        }

        if len(results) == 1:
            # Single result - show full content
            r = results[0]
            item_repo = ItemRepository(session)
            item = await item_repo.get(r.id, user_id)

            if item:
                emoji = type_emoji.get(item.type, "📄")
                lines = [f"{emoji} **{item.title}**"]

                # Show content or original_input
                content_text = item.content or item.original_input
                if content_text:
                    lines.append(f"\n{content_text[:500]}")
                    if len(content_text) > 500:
                        lines.append("...")

                if item.due_at_raw:
                    due_display = item.due_at_raw
                    if item.due_at:
                        due_display += f" ({item.due_at.strftime('%d.%m.%Y %H:%M')})"
                    lines.append(f"\n📅 Срок: {due_display}")

                if item.tags:
                    lines.append(f"🏷️ Теги: {' '.join(item.tags)}")

                response = "\n".join(lines)
                await message.reply(
                    response,
                    reply_markup=item_actions_keyboard(item.id, item.type),
                    parse_mode="Markdown"
                )
            else:
                response = f"📄 {r.title}"
                await message.reply(response)

            message_history.add(user_id, "assistant", response, metadata=search_metadata)

        else:
            # Multiple results - show list with buttons
            lines = [f"Найдено {len(results)} записей:\n"]
            for i, r in enumerate(results, 1):
                emoji = type_emoji.get(r.type, "📄")
                score_pct = int(r.score * 100)
                lines.append(f"{i}. {emoji} {r.title} ({score_pct}%)")

            response = "\n".join(lines)
            await message.reply(
                response,
                reply_markup=search_result_buttons_keyboard(results)
            )
            message_history.add(user_id, "assistant", response, metadata=search_metadata)


async def _search_with_agent_fallback(
    user_id: int,
    query: str,
    session
) -> str | None:
    """Use agent to reformulate search query and find results.

    Returns formatted response or None if nothing found.
    """
    from src.ai.agent import run_agent_loop

    # Build special prompt for search reformulation
    prompt = f"""Поиск по запросу '{query}' не дал хороших результатов (score < 0.4).

Попробуй переформулировать запрос:
- Используй синонимы
- Попробуй английский/русский варианты
- Ищи по связанным терминам

Используй search_items несколько раз с разными формулировками.
Если нашёл релевантные записи — покажи их.
Если ничего не нашёл — так и скажи."""

    context = message_history.get_context_with_search_info(user_id, limit=3)
    result = await run_agent_loop(user_id, prompt, context)

    if result.success and "ничего" not in result.response.lower():
        return result.response

    return None


async def process_action(message: Message, text: str) -> None:
    """Process ACTION intent - run agent loop."""
    from src.ai.agent import run_agent_loop

    user_id = message.from_user.id
    context = message_history.get_context_string(user_id, limit=5)

    result = await run_agent_loop(user_id, text, context)

    if result.needs_confirmation:
        await message.reply(
            result.response,
            reply_markup=agent_confirmation_keyboard()
        )
    else:
        await message.reply(result.response)

    message_history.add(user_id, "assistant", result.response)


async def process_chat(message: Message, text: str) -> None:
    """Process CHAT intent - respond to small talk."""
    user_id = message.from_user.id
    greetings = ["привет", "здравствуй", "хай", "hello", "hi"]
    thanks = ["спасибо", "благодарю", "thanks"]

    text_lower = text.lower()

    if any(g in text_lower for g in greetings):
        response = "Привет! Я твой второй мозг в Telegram.\nПросто отправляй мне что угодно - я сохраню и помогу найти."
    elif any(t in text_lower for t in thanks):
        response = "Всегда пожалуйста!"
    else:
        response = "Я готов сохранять и искать твои заметки, задачи и идеи. Просто отправь мне что-нибудь!"

    await message.reply(response)
    message_history.add(user_id, "assistant", response)
