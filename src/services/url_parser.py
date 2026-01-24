"""
URL Parser - extracts content from various URL types.
Supports YouTube, Twitter/X, Telegram, articles, and generic pages.
"""
import re
import logging
import socket
import ipaddress
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup

from src.config import URL_FETCH_TIMEOUT
from src.services.extracted_content import ExtractedContent

logger = logging.getLogger(__name__)

# URL patterns
YOUTUBE_PATTERN = re.compile(
    r'(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/shorts/)([a-zA-Z0-9_-]+)'
)
TWITTER_PATTERN = re.compile(r'(?:twitter\.com|x\.com)/\w+/status/(\d+)')
TELEGRAM_PATTERN = re.compile(r't\.me/([^/]+)/(\d+)')

# Blocked hostnames (case-insensitive)
BLOCKED_HOSTNAMES = {
    'localhost',
    'localhost.localdomain',
    'ip6-localhost',
    'ip6-loopback',
}


def is_ip_blocked(ip_str: str) -> bool:
    """Check if an IP address is internal/blocked for SSRF protection."""
    try:
        ip = ipaddress.ip_address(ip_str)
        # Block private, loopback, link-local, reserved, and multicast addresses
        return (
            ip.is_private or
            ip.is_loopback or
            ip.is_link_local or
            ip.is_reserved or
            ip.is_multicast or
            ip.is_unspecified
        )
    except ValueError:
        return False


def is_url_safe(url: str) -> tuple[bool, str]:
    """
    Validate URL to prevent SSRF attacks.
    Returns (is_safe, error_message).
    """
    try:
        parsed = urlparse(url)
    except Exception:
        return False, "Некорректный URL"

    # Only allow http and https schemes
    if parsed.scheme not in ('http', 'https'):
        return False, f"Недопустимая схема URL: {parsed.scheme}"

    hostname = parsed.hostname
    if not hostname:
        return False, "URL не содержит хоста"

    hostname_lower = hostname.lower()

    # Block known localhost hostnames
    if hostname_lower in BLOCKED_HOSTNAMES:
        return False, "Доступ к localhost запрещён"

    # Check if hostname is an IP address
    try:
        ip = ipaddress.ip_address(hostname)
        if is_ip_blocked(str(ip)):
            return False, "Доступ к внутренним IP-адресам запрещён"
    except ValueError:
        # Not an IP, it's a hostname - resolve and check
        try:
            # Resolve hostname to IP addresses
            addr_info = socket.getaddrinfo(hostname, None, socket.AF_UNSPEC, socket.SOCK_STREAM)
            for family, _, _, _, sockaddr in addr_info:
                ip_str = sockaddr[0]
                if is_ip_blocked(ip_str):
                    return False, "Доступ к внутренним IP-адресам запрещён"
        except socket.gaierror:
            # Can't resolve - let the request fail naturally
            pass

    return True, ""


def extract_urls(text: str) -> list[str]:
    """Extract URLs from text."""
    url_pattern = re.compile(
        r'https?://[^\s<>"{}|\\^`\[\]]+'
    )
    return url_pattern.findall(text)


class URLParser:
    """Parses URLs and extracts content."""

    def __init__(self, timeout: int = URL_FETCH_TIMEOUT):
        self.timeout = timeout

    async def parse(self, url: str) -> ExtractedContent:
        """Parse URL and extract content."""
        # SSRF protection: validate URL before any network request
        is_safe, error_msg = is_url_safe(url)
        if not is_safe:
            logger.warning(f"Blocked potentially malicious URL: {url} - {error_msg}")
            return ExtractedContent.from_error(error_msg, source_type="url")

        try:
            parsed = urlparse(url)
            domain = parsed.netloc.lower()

            # YouTube
            if 'youtube.com' in domain or 'youtu.be' in domain:
                return await self._parse_youtube(url)

            # Twitter/X
            if 'twitter.com' in domain or 'x.com' in domain:
                return await self._parse_twitter(url)

            # Telegram
            if 't.me' in domain:
                return await self._parse_telegram(url)

            # Generic article/page
            return await self._parse_article(url)

        except httpx.TimeoutException:
            return ExtractedContent.from_error(
                f"Таймаут при загрузке: {url}", source_type="url"
            )
        except Exception as e:
            logger.error(f"URL parse error: {e}")
            return ExtractedContent.from_error(
                f"Ошибка при обработке ссылки: {str(e)}", source_type="url"
            )

    async def _parse_youtube(self, url: str) -> ExtractedContent:
        """Extract YouTube video metadata using yt-dlp."""
        try:
            import yt_dlp

            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
                'extract_flat': False,
                'writesubtitles': False,
                'writeautomaticsub': False,
            }

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)

            title = info.get('title', 'YouTube Video')
            description = info.get('description', '')[:2000]
            channel = info.get('channel', info.get('uploader', ''))
            duration = info.get('duration', 0)

            # Try to get subtitles/captions
            subtitles_text = ""
            if info.get('subtitles') or info.get('automatic_captions'):
                subs = info.get('subtitles', {}) or info.get('automatic_captions', {})
                for lang in ['ru', 'en']:
                    if lang in subs:
                        subtitles_text = f"\n[Субтитры доступны на {lang}]"
                        break

            text = f"{title}\n\nКанал: {channel}\n\n{description}{subtitles_text}"

            return ExtractedContent(
                text=text.strip(),
                title=title,
                source_type="url",
                metadata={
                    "url": url,
                    "type": "youtube",
                    "channel": channel,
                    "duration": duration,
                }
            )
        except Exception as e:
            logger.warning(f"yt-dlp failed, falling back to article parser: {e}")
            return await self._parse_article(url)

    async def _parse_twitter(self, url: str) -> ExtractedContent:
        """Extract Twitter/X post content."""
        # Twitter requires authentication, use nitter or fallback
        nitter_instances = [
            "nitter.privacydev.net",
            "nitter.poast.org",
        ]

        match = TWITTER_PATTERN.search(url)
        if not match:
            return await self._parse_article(url)

        # Try nitter instances
        for instance in nitter_instances:
            try:
                nitter_url = url.replace("twitter.com", instance).replace("x.com", instance)
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.get(nitter_url, follow_redirects=True)
                    if response.status_code == 200:
                        soup = BeautifulSoup(response.text, 'html.parser')

                        # Find tweet content
                        tweet_content = soup.select_one('.tweet-content')
                        if tweet_content:
                            text = tweet_content.get_text(strip=True)
                            username = soup.select_one('.username')
                            username_text = username.get_text(strip=True) if username else ""

                            return ExtractedContent(
                                text=f"{username_text}: {text}",
                                title=f"Tweet от {username_text}",
                                source_type="url",
                                metadata={"url": url, "type": "twitter"}
                            )
            except Exception as e:
                logger.debug(f"Nitter instance {instance} failed: {e}")
                continue

        # Fallback to basic fetch
        return await self._parse_article(url)

    async def _parse_telegram(self, url: str) -> ExtractedContent:
        """Extract Telegram post content."""
        match = TELEGRAM_PATTERN.search(url)
        if not match:
            return await self._parse_article(url)

        channel, post_id = match.groups()
        embed_url = f"https://t.me/{channel}/{post_id}?embed=1"

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(embed_url, follow_redirects=True)
                if response.status_code == 200:
                    soup = BeautifulSoup(response.text, 'html.parser')

                    # Find message text
                    message_div = soup.select_one('.tgme_widget_message_text')
                    if message_div:
                        text = message_div.get_text(separator='\n', strip=True)
                        return ExtractedContent(
                            text=text,
                            title=f"Telegram: {channel}",
                            source_type="url",
                            metadata={"url": url, "type": "telegram", "channel": channel}
                        )
        except Exception as e:
            logger.warning(f"Telegram embed failed: {e}")

        return await self._parse_article(url)

    async def _parse_article(self, url: str) -> ExtractedContent:
        """Extract article content using heuristics."""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(url, follow_redirects=True)
            response.raise_for_status()

        soup = BeautifulSoup(response.text, 'html.parser')

        # Extract title
        title = None
        og_title = soup.find('meta', property='og:title')
        if og_title:
            title = og_title.get('content')
        if not title:
            title_tag = soup.find('title')
            title = title_tag.get_text(strip=True) if title_tag else None

        # Extract description
        description = None
        og_desc = soup.find('meta', property='og:description')
        if og_desc:
            description = og_desc.get('content')
        if not description:
            meta_desc = soup.find('meta', attrs={'name': 'description'})
            if meta_desc:
                description = meta_desc.get('content')

        # Extract main content
        content_text = ""

        # Try common article containers
        for selector in ['article', '[role="main"]', '.post-content', '.article-content',
                         '.entry-content', '.content', 'main']:
            container = soup.select_one(selector)
            if container:
                # Remove unwanted elements
                for tag in container.select('script, style, nav, header, footer, aside, .ad, .advertisement'):
                    tag.decompose()
                content_text = container.get_text(separator='\n', strip=True)
                if len(content_text) > 100:
                    break

        # Fallback: get all paragraphs
        if len(content_text) < 100:
            paragraphs = soup.find_all('p')
            content_text = '\n'.join(p.get_text(strip=True) for p in paragraphs[:20])

        # Combine title, description, and content
        parts = []
        if title:
            parts.append(title)
        if description and description not in (content_text[:200] if content_text else ""):
            parts.append(description)
        if content_text:
            # Limit content length
            if len(content_text) > 3000:
                content_text = content_text[:3000] + "..."
            parts.append(content_text)

        text = '\n\n'.join(parts) if parts else "Не удалось извлечь содержимое"

        return ExtractedContent(
            text=text,
            title=title,
            source_type="url",
            metadata={"url": url, "type": "article"}
        )
