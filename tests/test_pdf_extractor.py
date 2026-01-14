# tests/test_pdf_extractor.py
"""Tests for PDF Extractor."""
import pytest
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, patch, MagicMock

from src.services.pdf_extractor import PDFExtractor
from src.config import MAX_FILE_SIZE, MAX_DOCUMENT_PAGES


class TestPDFExtractor:
    """Tests for PDFExtractor class."""

    @pytest.fixture
    def extractor(self):
        """Create PDFExtractor with mocked client."""
        with patch('src.services.pdf_extractor.AsyncOpenAI'):
            return PDFExtractor()

    @pytest.mark.asyncio
    async def test_extract_text_pdf(self):
        """Test extracting text from normal PDF."""
        long_text = "This is a test PDF document with enough content to pass the threshold for text extraction. " * 3

        mock_page = MagicMock()
        mock_page.extract_text.return_value = long_text

        # Create a list-like mock for pages
        pages_list = [mock_page]
        mock_reader = MagicMock()
        mock_reader.pages = pages_list

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            f.write(b"%PDF-1.4 fake pdf content")
            path = Path(f.name)

        try:
            with patch('src.services.pdf_extractor.PdfReader', return_value=mock_reader):
                with patch('src.services.pdf_extractor.AsyncOpenAI'):
                    extractor = PDFExtractor()
                    result = await extractor.extract(path)

            assert result.is_error is False, f"Error: {result.error}"
            assert "test PDF document" in result.text
            assert result.source_type == "pdf"
            assert result.metadata["extraction_method"] == "text"
            assert result.metadata["page_count"] == 1
        finally:
            path.unlink()

    @pytest.mark.asyncio
    async def test_extract_file_not_found(self, extractor):
        """Test with missing file."""
        result = await extractor.extract("/nonexistent/file.pdf")

        assert result.is_error is True
        assert "не найден" in result.error

    @pytest.mark.asyncio
    async def test_extract_file_too_large(self, extractor):
        """Test with oversized file."""
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            path = Path(f.name)

        try:
            with patch.object(Path, 'stat') as mock_stat:
                mock_stat.return_value.st_size = MAX_FILE_SIZE + 1000

                result = await extractor.extract(path)

                assert result.is_error is True
                assert "слишком большой" in result.error
        finally:
            path.unlink()

    @pytest.mark.asyncio
    async def test_extract_too_many_pages(self, extractor):
        """Test with too many pages."""
        mock_reader = MagicMock()
        mock_reader.pages = [MagicMock()] * (MAX_DOCUMENT_PAGES + 10)

        with patch('src.services.pdf_extractor.PdfReader', return_value=mock_reader):
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
                f.write(b"%PDF-1.4")
                path = Path(f.name)

            try:
                result = await extractor.extract(path)

                assert result.is_error is True
                assert "страниц" in result.error
            finally:
                path.unlink()

    @pytest.mark.asyncio
    async def test_extract_scanned_pdf_ocr(self, extractor):
        """Test OCR fallback for scanned PDF."""
        # Mock page with no text (scanned)
        mock_page = MagicMock()
        mock_page.extract_text.return_value = ""
        mock_page.__getitem__ = MagicMock(side_effect=KeyError('/Resources'))

        mock_reader = MagicMock()
        mock_reader.pages = [mock_page]

        with patch('src.services.pdf_extractor.PdfReader', return_value=mock_reader):
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
                f.write(b"%PDF-1.4")
                path = Path(f.name)

            try:
                result = await extractor.extract(path)

                # Should fail to OCR without real images
                assert result.is_error is True
            finally:
                path.unlink()

    @pytest.mark.asyncio
    async def test_extract_error_handling(self, extractor):
        """Test error handling during extraction."""
        with patch('src.services.pdf_extractor.PdfReader', side_effect=Exception("PDF Error")):
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
                f.write(b"%PDF-1.4")
                path = Path(f.name)

            try:
                result = await extractor.extract(path)

                assert result.is_error is True
                assert "Ошибка" in result.error
            finally:
                path.unlink()

    def test_extract_title(self, extractor):
        """Test title extraction from first page."""
        # Good title (11-200 chars)
        title = extractor._extract_title("Document Title\n\nContent here...")
        assert title == "Document Title"

        # Too short (< 10 chars), falls through to next line
        title = extractor._extract_title("Hi\n\nThis is a longer second line")
        assert title == "This is a longer second line"

        # All lines too short
        title = extractor._extract_title("Hi\n\nBye\n\nOk")
        assert title is None

        # Empty
        title = extractor._extract_title("")
        assert title is None

        # None
        title = extractor._extract_title(None)
        assert title is None

    @pytest.mark.asyncio
    async def test_extract_multipage_pdf(self, extractor):
        """Test extracting from multi-page PDF."""
        pages = []
        for i in range(5):
            mock_page = MagicMock()
            mock_page.extract_text.return_value = f"Page {i+1} content with sufficient text."
            pages.append(mock_page)

        mock_reader = MagicMock()
        mock_reader.pages = pages

        with patch('src.services.pdf_extractor.PdfReader', return_value=mock_reader):
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
                f.write(b"%PDF-1.4")
                path = Path(f.name)

            try:
                result = await extractor.extract(path)

                assert result.is_error is False
                assert "Page 1" in result.text
                assert "Page 5" in result.text
                assert result.metadata["page_count"] == 5
            finally:
                path.unlink()
