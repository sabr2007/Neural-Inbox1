# tests/test_document_extractor.py
"""Tests for Document Extractor."""
import pytest
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.services.document_extractor import DocumentExtractor
from src.config import MAX_FILE_SIZE


class TestDocumentExtractor:
    """Tests for DocumentExtractor class."""

    @pytest.fixture
    def extractor(self):
        """Create DocumentExtractor instance."""
        return DocumentExtractor()

    @pytest.mark.asyncio
    async def test_extract_docx_success(self, extractor):
        """Test successful .docx extraction."""
        mock_para1 = MagicMock()
        mock_para1.text = "Document Title"
        mock_para2 = MagicMock()
        mock_para2.text = "This is the main content of the document."

        mock_doc = MagicMock()
        mock_doc.paragraphs = [mock_para1, mock_para2]
        mock_doc.tables = []
        mock_doc.core_properties.title = "My Document"

        with patch('src.services.document_extractor.Document', return_value=mock_doc):
            with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as f:
                f.write(b"fake docx content")
                path = Path(f.name)

            try:
                result = await extractor.extract(path)

                assert result.is_error is False
                assert "Document Title" in result.text
                assert "main content" in result.text
                assert result.source_type == "docx"
                assert result.title == "My Document"
            finally:
                path.unlink()

    @pytest.mark.asyncio
    async def test_extract_file_not_found(self, extractor):
        """Test with missing file."""
        result = await extractor.extract("/nonexistent/file.docx")

        assert result.is_error is True
        assert "не найден" in result.error

    @pytest.mark.asyncio
    async def test_extract_unsupported_format(self, extractor):
        """Test with unsupported file format."""
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
            f.write(b"text content")
            path = Path(f.name)

        try:
            result = await extractor.extract(path)

            assert result.is_error is True
            assert "не поддерживается" in result.error
        finally:
            path.unlink()

    @pytest.mark.asyncio
    async def test_extract_old_doc_format(self, extractor):
        """Test with old .doc format."""
        with tempfile.NamedTemporaryFile(suffix=".doc", delete=False) as f:
            f.write(b"old doc content")
            path = Path(f.name)

        try:
            result = await extractor.extract(path)

            assert result.is_error is True
            assert ".doc" in result.error
            assert ".docx" in result.error
        finally:
            path.unlink()

    @pytest.mark.asyncio
    async def test_extract_file_too_large(self, extractor):
        """Test with oversized file."""
        with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as f:
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
    async def test_extract_empty_document(self, extractor):
        """Test with empty document."""
        mock_doc = MagicMock()
        mock_doc.paragraphs = []
        mock_doc.tables = []

        with patch('src.services.document_extractor.Document', return_value=mock_doc):
            with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as f:
                f.write(b"fake")
                path = Path(f.name)

            try:
                result = await extractor.extract(path)

                assert result.is_error is True
                assert "пуст" in result.error
            finally:
                path.unlink()

    @pytest.mark.asyncio
    async def test_extract_with_tables(self, extractor):
        """Test extraction includes table content."""
        mock_para = MagicMock()
        mock_para.text = "Document with table"

        mock_cell1 = MagicMock()
        mock_cell1.text = "Cell 1"
        mock_cell2 = MagicMock()
        mock_cell2.text = "Cell 2"

        mock_row = MagicMock()
        mock_row.cells = [mock_cell1, mock_cell2]

        mock_table = MagicMock()
        mock_table.rows = [mock_row]

        mock_doc = MagicMock()
        mock_doc.paragraphs = [mock_para]
        mock_doc.tables = [mock_table]
        mock_doc.core_properties.title = None

        with patch('src.services.document_extractor.Document', return_value=mock_doc):
            with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as f:
                f.write(b"fake")
                path = Path(f.name)

            try:
                result = await extractor.extract(path)

                assert result.is_error is False
                assert "Cell 1" in result.text
                assert "Cell 2" in result.text
                assert result.metadata["table_count"] == 1
            finally:
                path.unlink()

    @pytest.mark.asyncio
    async def test_extract_error_handling(self, extractor):
        """Test error handling during extraction."""
        with patch('src.services.document_extractor.Document', side_effect=Exception("Parse error")):
            with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as f:
                f.write(b"fake")
                path = Path(f.name)

            try:
                result = await extractor.extract(path)

                assert result.is_error is True
                assert "Ошибка" in result.error
            finally:
                path.unlink()

    def test_extract_title_from_properties(self, extractor):
        """Test title extraction from document properties."""
        mock_doc = MagicMock()
        mock_doc.core_properties.title = "Property Title"

        title = extractor._extract_title(mock_doc, ["First paragraph"])
        assert title == "Property Title"

    def test_extract_title_from_first_paragraph(self, extractor):
        """Test title extraction from first paragraph."""
        mock_doc = MagicMock()
        mock_doc.core_properties.title = None

        title = extractor._extract_title(mock_doc, ["Document Heading", "Content..."])
        assert title == "Document Heading"

    def test_extract_title_too_short(self, extractor):
        """Test title extraction skips very short text."""
        mock_doc = MagicMock()
        mock_doc.core_properties.title = None

        title = extractor._extract_title(mock_doc, ["Hi", "Actual content paragraph here"])
        assert title is None

    @pytest.mark.asyncio
    async def test_extract_metadata(self, extractor):
        """Test metadata is properly populated."""
        mock_para = MagicMock()
        mock_para.text = "Content that is long enough to pass."

        mock_doc = MagicMock()
        mock_doc.paragraphs = [mock_para]
        mock_doc.tables = []
        mock_doc.core_properties.title = None

        with patch('src.services.document_extractor.Document', return_value=mock_doc):
            with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as f:
                f.write(b"x" * 1000)
                path = Path(f.name)

            try:
                result = await extractor.extract(path)

                assert result.is_error is False
                assert "file_size" in result.metadata
                assert "paragraph_count" in result.metadata
                assert "estimated_pages" in result.metadata
                assert "table_count" in result.metadata
            finally:
                path.unlink()
