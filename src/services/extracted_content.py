"""
ExtractedContent - unified result structure for all input processors.
"""
from dataclasses import dataclass, field


@dataclass
class ExtractedContent:
    """Result of content extraction from various input types."""
    text: str  # Основной текст для роутера
    title: str | None = None  # Заголовок (для URL/документов)
    source_type: str = ""  # "voice", "image", "pdf", "url", "docx"
    metadata: dict = field(default_factory=dict)  # Доп. данные (duration, page_count, url)
    error: str | None = None  # Если что-то пошло не так

    @property
    def is_error(self) -> bool:
        """Check if extraction resulted in an error."""
        return self.error is not None

    @classmethod
    def from_error(cls, error: str, source_type: str = "") -> "ExtractedContent":
        """Create an error result."""
        return cls(text="", source_type=source_type, error=error)
