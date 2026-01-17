# neural-inbox1/src/ai/model_selector.py
"""Adaptive model selection based on input complexity."""


class ModelSelector:
    """Select model based on input text complexity."""

    FAST_MODEL = "gpt-4o-mini"   # ~1 sec, cheap
    SMART_MODEL = "gpt-4o"       # ~2-3 sec, smart

    LONG_TEXT_THRESHOLD = 500

    MULTI_INTENT_MARKERS = [
        " и ", " а также ", " плюс ", " ещё ", "\n",
        "во-первых", "во-вторых", "1.", "2.", "1)", "2)"
    ]

    COMPLEX_MARKERS = [
        "с одной стороны", "с другой стороны",
        "если", "то", "потому что", "следовательно"
    ]

    @classmethod
    def select(cls, text: str, source: str) -> str:
        """
        Select appropriate model based on text complexity.

        Args:
            text: Input text to analyze
            source: Source type ("voice", "text", etc.)

        Returns:
            Model name (FAST_MODEL or SMART_MODEL)
        """
        # Voice messages > 2 minutes -> smart model
        if source == "voice" and len(text) > 1000:
            return cls.SMART_MODEL

        # Long text
        if len(text) > cls.LONG_TEXT_THRESHOLD:
            return cls.SMART_MODEL

        # Multiple intent markers
        text_lower = text.lower()
        multi_intent_count = sum(
            1 for marker in cls.MULTI_INTENT_MARKERS
            if marker in text_lower
        )
        if multi_intent_count >= 2:
            return cls.SMART_MODEL

        # Complex structure markers
        if any(marker in text_lower for marker in cls.COMPLEX_MARKERS):
            return cls.SMART_MODEL

        return cls.FAST_MODEL
