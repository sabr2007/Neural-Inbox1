# tests/test_extracted_content.py
"""Tests for ExtractedContent dataclass."""
import pytest
from src.services.extracted_content import ExtractedContent


class TestExtractedContent:
    """Tests for ExtractedContent."""

    def test_create_basic(self):
        """Test basic creation."""
        content = ExtractedContent(text="Hello world")
        assert content.text == "Hello world"
        assert content.title is None
        assert content.source_type == ""
        assert content.metadata == {}
        assert content.error is None

    def test_create_full(self):
        """Test creation with all fields."""
        content = ExtractedContent(
            text="Content text",
            title="My Title",
            source_type="pdf",
            metadata={"page_count": 5},
            error=None
        )
        assert content.text == "Content text"
        assert content.title == "My Title"
        assert content.source_type == "pdf"
        assert content.metadata == {"page_count": 5}
        assert content.is_error is False

    def test_is_error_property(self):
        """Test is_error property."""
        content_ok = ExtractedContent(text="OK")
        assert content_ok.is_error is False

        content_err = ExtractedContent(text="", error="Something went wrong")
        assert content_err.is_error is True

    def test_from_error(self):
        """Test from_error factory method."""
        content = ExtractedContent.from_error("Failed to process", source_type="voice")
        assert content.text == ""
        assert content.error == "Failed to process"
        assert content.source_type == "voice"
        assert content.is_error is True

    def test_from_error_default_source(self):
        """Test from_error with default source type."""
        content = ExtractedContent.from_error("Error")
        assert content.source_type == ""
        assert content.error == "Error"

    def test_metadata_default(self):
        """Test that metadata defaults to empty dict."""
        content1 = ExtractedContent(text="A")
        content2 = ExtractedContent(text="B")

        # Ensure they don't share the same dict
        content1.metadata["key"] = "value"
        assert "key" not in content2.metadata
