"""
Image Analyzer - analyzes images using OpenAI Vision API.
Performs OCR for text content and description for photos.
"""
import base64
import logging
from pathlib import Path

from openai import AsyncOpenAI

from src.config import config, MAX_IMAGE_SIZE
from src.services.extracted_content import ExtractedContent

logger = logging.getLogger(__name__)

ANALYSIS_PROMPT = """Проанализируй изображение:
1. Если есть текст — извлеки его полностью (OCR)
2. Если это скриншот переписки — извлеки сообщения с указанием отправителей
3. Если это фото/картинка — опиши что на ней

Отвечай только извлечённым текстом или описанием, без вступлений."""

SUPPORTED_FORMATS = {'.jpg', '.jpeg', '.png', '.gif', '.webp'}


class ImageAnalyzer:
    """Analyzes images using OpenAI Vision API."""

    def __init__(self):
        self.client = AsyncOpenAI(api_key=config.openai.api_key)

    async def analyze(
        self,
        file_path: str | Path,
        caption: str | None = None
    ) -> ExtractedContent:
        """
        Analyze image and extract text or description.

        Args:
            file_path: Path to image file
            caption: Optional caption from user

        Returns:
            ExtractedContent with extracted text or description
        """
        file_path = Path(file_path)

        # Validate file extension
        if file_path.suffix.lower() not in SUPPORTED_FORMATS:
            return ExtractedContent.from_error(
                f"Формат {file_path.suffix} не поддерживается. "
                f"Поддерживаются: {', '.join(SUPPORTED_FORMATS)}",
                source_type="image"
            )

        # Check file exists and size
        if not file_path.exists():
            return ExtractedContent.from_error(
                "Файл не найден", source_type="image"
            )

        file_size = file_path.stat().st_size
        if file_size > MAX_IMAGE_SIZE:
            return ExtractedContent.from_error(
                f"Изображение слишком большое ({file_size // 1024 // 1024}MB). "
                f"Максимум: {MAX_IMAGE_SIZE // 1024 // 1024}MB",
                source_type="image"
            )

        try:
            # Read and encode image
            with open(file_path, "rb") as f:
                image_data = base64.b64encode(f.read()).decode("utf-8")

            # Determine media type
            suffix = file_path.suffix.lower()
            media_type = {
                '.jpg': 'image/jpeg',
                '.jpeg': 'image/jpeg',
                '.png': 'image/png',
                '.gif': 'image/gif',
                '.webp': 'image/webp',
            }.get(suffix, 'image/jpeg')

            # Build prompt with caption context if provided
            prompt = ANALYSIS_PROMPT
            if caption:
                prompt = f"Контекст от пользователя: {caption}\n\n{prompt}"

            # Call Vision API
            response = await self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:{media_type};base64,{image_data}",
                                    "detail": "high"
                                }
                            }
                        ]
                    }
                ],
                max_tokens=1500
            )

            text = response.choices[0].message.content.strip()

            if not text:
                return ExtractedContent.from_error(
                    "Не удалось проанализировать изображение",
                    source_type="image"
                )

            # Combine with caption if provided
            if caption:
                text = f"[Подпись: {caption}]\n\n{text}"

            return ExtractedContent(
                text=text,
                title=caption,
                source_type="image",
                metadata={
                    "file_size": file_size,
                    "format": suffix,
                    "has_caption": caption is not None,
                }
            )

        except Exception as e:
            logger.error(f"Image analysis error: {e}")
            return ExtractedContent.from_error(
                f"Ошибка анализа изображения: {str(e)}",
                source_type="image"
            )
