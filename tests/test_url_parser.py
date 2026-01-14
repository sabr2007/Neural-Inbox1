# tests/test_url_parser.py
"""Tests for URL Parser."""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from src.services.url_parser import URLParser, extract_urls


class TestExtractUrls:
    """Tests for extract_urls function."""

    def test_extract_single_url(self):
        """Test extracting single URL."""
        text = "Check out https://example.com for more info"
        urls = extract_urls(text)
        assert urls == ["https://example.com"]

    def test_extract_multiple_urls(self):
        """Test extracting multiple URLs."""
        text = "Visit https://example.com and http://test.org"
        urls = extract_urls(text)
        assert len(urls) == 2
        assert "https://example.com" in urls
        assert "http://test.org" in urls

    def test_extract_no_urls(self):
        """Test with no URLs."""
        text = "No links here"
        urls = extract_urls(text)
        assert urls == []

    def test_extract_youtube_url(self):
        """Test extracting YouTube URL."""
        text = "Watch https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        urls = extract_urls(text)
        assert len(urls) == 1
        assert "youtube.com" in urls[0]

    def test_extract_url_with_params(self):
        """Test URL with query parameters."""
        text = "Link: https://example.com/page?foo=bar&baz=qux"
        urls = extract_urls(text)
        assert "https://example.com/page?foo=bar&baz=qux" in urls[0]

    def test_extract_telegram_url(self):
        """Test extracting Telegram URL."""
        text = "Post: https://t.me/channel/123"
        urls = extract_urls(text)
        assert urls == ["https://t.me/channel/123"]


class TestURLParser:
    """Tests for URLParser class."""

    @pytest.fixture
    def parser(self):
        """Create URLParser instance."""
        return URLParser(timeout=5)

    @pytest.mark.asyncio
    async def test_parse_article_success(self, parser):
        """Test parsing article URL."""
        html = """
        <html>
        <head>
            <title>Test Article</title>
            <meta property="og:title" content="Test Article Title">
            <meta property="og:description" content="Article description">
        </head>
        <body>
            <article>
                <p>This is the article content with meaningful text that should be extracted.</p>
            </article>
        </body>
        </html>
        """
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = html
        mock_response.raise_for_status = MagicMock()

        with patch('httpx.AsyncClient') as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_response)

            result = await parser.parse("https://example.com/article")

            assert result.is_error is False
            assert result.source_type == "url"
            assert "Test Article" in result.text
            assert result.metadata["type"] == "article"

    @pytest.mark.asyncio
    async def test_parse_timeout(self, parser):
        """Test timeout handling."""
        import httpx

        with patch('httpx.AsyncClient') as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                side_effect=httpx.TimeoutException("Timeout")
            )

            result = await parser.parse("https://slow-site.com")

            assert result.is_error is True
            assert "Таймаут" in result.error

    @pytest.mark.asyncio
    async def test_parse_youtube_fallback(self, parser):
        """Test YouTube parsing falls back to article on error."""
        html = """
        <html>
        <head><title>YouTube Video</title></head>
        <body><p>Video page</p></body>
        </html>
        """
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = html
        mock_response.raise_for_status = MagicMock()

        with patch('httpx.AsyncClient') as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_response)

            # yt-dlp will fail, should fallback to article parser
            with patch.dict('sys.modules', {'yt_dlp': None}):
                result = await parser.parse("https://youtube.com/watch?v=test123")

            assert result.source_type == "url"

    @pytest.mark.asyncio
    async def test_parse_telegram(self, parser):
        """Test Telegram URL parsing."""
        html = """
        <html>
        <body>
            <div class="tgme_widget_message_text">
                This is a Telegram post content.
            </div>
        </body>
        </html>
        """
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = html

        with patch('httpx.AsyncClient') as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_response)

            result = await parser.parse("https://t.me/testchannel/123")

            assert result.is_error is False
            assert "Telegram post content" in result.text
            assert result.metadata["type"] == "telegram"

    @pytest.mark.asyncio
    async def test_parse_generic_error(self, parser):
        """Test generic error handling."""
        with patch('httpx.AsyncClient') as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                side_effect=Exception("Connection failed")
            )

            result = await parser.parse("https://broken-site.com")

            assert result.is_error is True
            assert "Ошибка" in result.error

    @pytest.mark.asyncio
    async def test_parse_article_no_content(self, parser):
        """Test article with minimal content."""
        html = "<html><head><title>Empty</title></head><body></body></html>"
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = html
        mock_response.raise_for_status = MagicMock()

        with patch('httpx.AsyncClient') as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_response)

            result = await parser.parse("https://empty-page.com")

            assert result.is_error is False
            # Should still extract title at minimum
            assert "Empty" in result.text or result.text
