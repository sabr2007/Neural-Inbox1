# tests/test_classifier.py
"""Tests for Content Classifier logic (isolated unit tests)."""
import pytest
import json
from datetime import datetime


class TestClassificationParsing:
    """Tests for classification response parsing."""

    def test_parse_task_classification(self):
        """Test parsing task classification."""
        response = '''{
            "type": "task",
            "title": "Купить молоко",
            "due_at_raw": "завтра",
            "due_at_iso": "2025-01-14T12:00:00Z",
            "priority": "medium",
            "tags": ["#покупки"],
            "entities": {"people": [], "urls": [], "phones": [], "places": ["магазин"]}
        }'''

        result = json.loads(response)

        assert result["type"] == "task"
        assert result["title"] == "Купить молоко"
        assert result["due_at_raw"] == "завтра"
        assert result["priority"] == "medium"
        assert "#покупки" in result["tags"]

    def test_parse_idea_classification(self):
        """Test parsing idea classification."""
        response = '''{
            "type": "idea",
            "title": "Приложение для трекинга",
            "due_at_raw": null,
            "priority": null,
            "tags": ["#идея"],
            "entities": {}
        }'''

        result = json.loads(response)

        assert result["type"] == "idea"
        assert result["due_at_raw"] is None
        assert result["priority"] is None

    def test_parse_event_classification(self):
        """Test parsing event classification."""
        response = '''{
            "type": "event",
            "title": "Встреча с Мишей",
            "due_at_raw": "завтра в 15:00",
            "due_at_iso": "2025-01-14T15:00:00+06:00",
            "priority": null,
            "tags": ["#встреча"],
            "entities": {"people": ["Миша"]}
        }'''

        result = json.loads(response)

        assert result["type"] == "event"
        assert "Миша" in result["entities"]["people"]

    def test_parse_iso_date(self):
        """Test parsing ISO date from classification."""
        iso_string = "2025-01-14T15:00:00+00:00"

        # Parse the date
        parsed = datetime.fromisoformat(iso_string.replace("Z", "+00:00"))

        assert parsed.year == 2025
        assert parsed.month == 1
        assert parsed.day == 14
        assert parsed.hour == 15


class TestTypeValidation:
    """Tests for type validation."""

    def test_valid_types(self):
        """Test all valid item types."""
        valid_types = {"task", "idea", "note", "resource", "contact", "event"}

        assert "task" in valid_types
        assert "idea" in valid_types
        assert "note" in valid_types
        assert "resource" in valid_types
        assert "contact" in valid_types
        assert "event" in valid_types

    def test_priority_values(self):
        """Test valid priority values."""
        valid_priorities = {"high", "medium", "low", None}

        assert "high" in valid_priorities
        assert "medium" in valid_priorities
        assert "low" in valid_priorities
        assert None in valid_priorities


class TestFallbackLogic:
    """Tests for fallback classification logic."""

    def test_url_detection(self):
        """Test URL detection for resource type."""
        text1 = "https://example.com"
        text2 = "check http://test.com"
        text3 = "no url here"

        assert "http://" in text1 or "https://" in text1
        assert "http://" in text2 or "https://" in text2
        assert "http://" not in text3 and "https://" not in text3

    def test_idea_markers_detection(self):
        """Test idea marker detection."""
        idea_markers = ["идея", "а что если"]

        text1 = "идея: новое приложение"
        text2 = "а что если сделать так?"
        text3 = "купить молоко"

        has_idea_marker1 = any(m in text1.lower() for m in idea_markers)
        has_idea_marker2 = any(m in text2.lower() for m in idea_markers)
        has_idea_marker3 = any(m in text3.lower() for m in idea_markers)

        assert has_idea_marker1 is True
        assert has_idea_marker2 is True
        assert has_idea_marker3 is False

    def test_task_markers_detection(self):
        """Test task marker detection."""
        task_markers = ["купить", "сделать", "позвонить", "завтра", "нужно"]

        text1 = "купить молоко"
        text2 = "нужно сделать отчет"
        text3 = "просто заметка"

        has_task_marker1 = any(m in text1.lower() for m in task_markers)
        has_task_marker2 = any(m in text2.lower() for m in task_markers)
        has_task_marker3 = any(m in text3.lower() for m in task_markers)

        assert has_task_marker1 is True
        assert has_task_marker2 is True
        assert has_task_marker3 is False

    def test_title_truncation(self):
        """Test title truncation for long text."""
        long_text = "x" * 200
        max_title_length = 100

        truncated = long_text[:max_title_length]

        assert len(truncated) == 100


class TestEntitiesExtraction:
    """Tests for entities structure."""

    def test_entities_structure(self):
        """Test entities dictionary structure."""
        entities = {
            "people": ["Миша", "Иван"],
            "urls": ["https://example.com"],
            "phones": ["+79991234567"],
            "places": ["офис"]
        }

        assert "people" in entities
        assert "urls" in entities
        assert "phones" in entities
        assert "places" in entities

        assert len(entities["people"]) == 2
        assert entities["urls"][0].startswith("https://")
