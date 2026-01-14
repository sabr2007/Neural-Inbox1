"""
PDF Extractor - extracts text from PDF files.
Uses pypdf for text extraction, falls back to Vision API for scanned documents.
"""
import base64
import io
import logging
from pathlib import Path

from pypdf import PdfReader
from PIL import Image
from openai import AsyncOpenAI

from src.config import config, MAX_DOCUMENT_PAGES, MAX_FILE_SIZE, OCR_MAX_PAGES
from src.services.extracted_content import ExtractedContent

logger = logging.getLogger(__name__)

OCR_PROMPT = """Извлеки весь текст с этой страницы документа.
Сохраняй структуру: заголовки, абзацы, списки.
Отвечай только извлечённым текстом."""


class PDFExtractor:
    """Extracts text from PDF files."""

    def __init__(self):
        self.client = AsyncOpenAI(api_key=config.openai.api_key)

    async def extract(
        self,
        file_path: str | Path,
    ) -> ExtractedContent:
        """
        Extract text from PDF file.

        Args:
            file_path: Path to PDF file

        Returns:
            ExtractedContent with extracted text
        """
        file_path = Path(file_path)

        # Check file exists
        if not file_path.exists():
            return ExtractedContent.from_error(
                "Файл не найден", source_type="pdf"
            )

        # Check file size
        file_size = file_path.stat().st_size
        if file_size > MAX_FILE_SIZE:
            return ExtractedContent.from_error(
                f"PDF слишком большой ({file_size // 1024 // 1024}MB). "
                f"Максимум: {MAX_FILE_SIZE // 1024 // 1024}MB",
                source_type="pdf"
            )

        try:
            reader = PdfReader(file_path)
            total_pages = len(reader.pages)

            if total_pages > MAX_DOCUMENT_PAGES:
                return ExtractedContent.from_error(
                    f"PDF содержит {total_pages} страниц. "
                    f"Максимум: {MAX_DOCUMENT_PAGES}",
                    source_type="pdf"
                )

            # Try to extract text from all pages
            text_parts = []
            for page in reader.pages:
                page_text = page.extract_text() or ""
                text_parts.append(page_text)

            full_text = "\n\n".join(text_parts).strip()

            # Check if we got meaningful text (not a scanned document)
            if len(full_text) > 100:
                # Extract title from first page if possible
                title = self._extract_title(text_parts[0]) if text_parts else None

                return ExtractedContent(
                    text=full_text,
                    title=title,
                    source_type="pdf",
                    metadata={
                        "page_count": total_pages,
                        "file_size": file_size,
                        "extraction_method": "text",
                    }
                )

            # Scanned document - use OCR via Vision API
            logger.info(f"PDF appears to be scanned, using OCR for first {OCR_MAX_PAGES} pages")
            return await self._ocr_pdf(file_path, reader, total_pages)

        except Exception as e:
            logger.error(f"PDF extraction error: {e}")
            return ExtractedContent.from_error(
                f"Ошибка извлечения текста из PDF: {str(e)}",
                source_type="pdf"
            )

    async def _ocr_pdf(
        self,
        file_path: Path,
        reader: PdfReader,
        total_pages: int
    ) -> ExtractedContent:
        """OCR scanned PDF pages using Vision API."""
        try:
            # We need pdf2image or similar, but let's use a simpler approach
            # Convert pages to images using pypdf + PIL
            ocr_texts = []
            pages_to_ocr = min(total_pages, OCR_MAX_PAGES)

            for page_num in range(pages_to_ocr):
                page = reader.pages[page_num]

                # Try to extract images from the page
                page_images = self._extract_page_images(page)

                if page_images:
                    # OCR the first/main image
                    image_data = page_images[0]
                    text = await self._ocr_image(image_data)
                    if text:
                        ocr_texts.append(f"--- Страница {page_num + 1} ---\n{text}")

            if not ocr_texts:
                return ExtractedContent.from_error(
                    "Не удалось извлечь текст из отсканированного PDF",
                    source_type="pdf"
                )

            full_text = "\n\n".join(ocr_texts)

            note = ""
            if total_pages > OCR_MAX_PAGES:
                note = f"\n\n[Распознаны первые {OCR_MAX_PAGES} из {total_pages} страниц]"

            return ExtractedContent(
                text=full_text + note,
                title=None,
                source_type="pdf",
                metadata={
                    "page_count": total_pages,
                    "ocr_pages": pages_to_ocr,
                    "extraction_method": "ocr",
                }
            )

        except Exception as e:
            logger.error(f"PDF OCR error: {e}")
            return ExtractedContent.from_error(
                f"Ошибка OCR: {str(e)}",
                source_type="pdf"
            )

    def _extract_page_images(self, page) -> list[bytes]:
        """Extract images from a PDF page."""
        images = []
        try:
            if '/XObject' in page['/Resources']:
                x_objects = page['/Resources']['/XObject'].get_object()
                for obj_name in x_objects:
                    obj = x_objects[obj_name]
                    if obj['/Subtype'] == '/Image':
                        # Get image data
                        if '/Filter' in obj:
                            if obj['/Filter'] == '/DCTDecode':
                                # JPEG
                                images.append(obj._data)
                            elif obj['/Filter'] == '/FlateDecode':
                                # PNG-like, need to reconstruct
                                try:
                                    width = obj['/Width']
                                    height = obj['/Height']
                                    data = obj.get_data()

                                    # Try to create image
                                    if '/ColorSpace' in obj:
                                        color_space = obj['/ColorSpace']
                                        if color_space == '/DeviceRGB':
                                            mode = 'RGB'
                                        elif color_space == '/DeviceGray':
                                            mode = 'L'
                                        else:
                                            mode = 'RGB'
                                    else:
                                        mode = 'RGB'

                                    img = Image.frombytes(mode, (width, height), data)
                                    buffer = io.BytesIO()
                                    img.save(buffer, format='PNG')
                                    images.append(buffer.getvalue())
                                except Exception:
                                    pass
        except Exception as e:
            logger.debug(f"Error extracting images from page: {e}")

        return images

    async def _ocr_image(self, image_data: bytes) -> str:
        """OCR a single image using Vision API."""
        try:
            base64_image = base64.b64encode(image_data).decode('utf-8')

            # Detect format
            if image_data[:2] == b'\xff\xd8':
                media_type = 'image/jpeg'
            else:
                media_type = 'image/png'

            response = await self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": OCR_PROMPT},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:{media_type};base64,{base64_image}",
                                    "detail": "high"
                                }
                            }
                        ]
                    }
                ],
                max_tokens=2000
            )

            return response.choices[0].message.content.strip()

        except Exception as e:
            logger.error(f"OCR error: {e}")
            return ""

    def _extract_title(self, first_page_text: str) -> str | None:
        """Try to extract title from first page text."""
        if not first_page_text:
            return None

        lines = first_page_text.strip().split('\n')
        for line in lines[:5]:  # Check first 5 lines
            line = line.strip()
            if 10 < len(line) < 200:  # Reasonable title length
                return line

        return None
