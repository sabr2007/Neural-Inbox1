# tests/test_search.py
"""Tests for search functionality (isolated unit tests)."""
import pytest
from dataclasses import dataclass
from typing import Optional


@dataclass
class SearchResult:
    """Mock SearchResult for testing."""
    id: int
    title: str
    content: Optional[str]
    type: str
    score: float
    fts_score: float
    vector_score: float


class TestSearchResult:
    """Tests for SearchResult dataclass."""

    def test_search_result_creation(self):
        """Test creating SearchResult."""
        result = SearchResult(
            id=1,
            title="Test",
            content="Content",
            type="task",
            score=0.8,
            fts_score=0.3,
            vector_score=0.9
        )

        assert result.id == 1
        assert result.title == "Test"
        assert result.content == "Content"
        assert result.type == "task"
        assert result.score == 0.8
        assert result.fts_score == 0.3
        assert result.vector_score == 0.9

    def test_search_result_none_content(self):
        """Test SearchResult with None content."""
        result = SearchResult(
            id=1,
            title="Test",
            content=None,
            type="note",
            score=0.5,
            fts_score=0.5,
            vector_score=0.0
        )

        assert result.content is None


class TestHybridScoreCalculation:
    """Tests for hybrid score calculation logic."""

    def test_hybrid_score_default_weights(self):
        """Test hybrid score with default weights."""
        fts_score = 0.5
        vector_score = 0.9
        fts_weight = 0.3
        vector_weight = 0.7

        hybrid_score = fts_score * fts_weight + vector_score * vector_weight

        assert hybrid_score == pytest.approx(0.78)

    def test_hybrid_score_equal_weights(self):
        """Test hybrid score with equal weights."""
        fts_score = 0.6
        vector_score = 0.8
        fts_weight = 0.5
        vector_weight = 0.5

        hybrid_score = fts_score * fts_weight + vector_score * vector_weight

        assert hybrid_score == pytest.approx(0.7)

    def test_hybrid_score_fts_only(self):
        """Test score when only FTS matches."""
        fts_score = 0.8
        vector_score = 0.0
        fts_weight = 0.3
        vector_weight = 0.7

        hybrid_score = fts_score * fts_weight + vector_score * vector_weight

        assert hybrid_score == pytest.approx(0.24)

    def test_hybrid_score_vector_only(self):
        """Test score when only vector matches."""
        fts_score = 0.0
        vector_score = 0.9
        fts_weight = 0.3
        vector_weight = 0.7

        hybrid_score = fts_score * fts_weight + vector_score * vector_weight

        assert hybrid_score == pytest.approx(0.63)


class TestSearchFiltering:
    """Tests for search filtering logic."""

    def test_filter_by_type(self):
        """Test filtering results by type."""
        results = [
            SearchResult(1, "Task 1", None, "task", 0.9, 0.5, 0.9),
            SearchResult(2, "Note 1", None, "note", 0.8, 0.4, 0.8),
            SearchResult(3, "Task 2", None, "task", 0.7, 0.3, 0.7),
        ]

        type_filter = "task"
        filtered = [r for r in results if r.type == type_filter]

        assert len(filtered) == 2
        assert all(r.type == "task" for r in filtered)

    def test_filter_by_min_score(self):
        """Test filtering results by minimum score."""
        results = [
            SearchResult(1, "High", None, "task", 0.9, 0.5, 0.9),
            SearchResult(2, "Medium", None, "note", 0.6, 0.4, 0.6),
            SearchResult(3, "Low", None, "task", 0.3, 0.2, 0.3),
        ]

        min_score = 0.5
        filtered = [r for r in results if r.score >= min_score]

        assert len(filtered) == 2
        assert all(r.score >= min_score for r in filtered)


class TestResultSorting:
    """Tests for result sorting logic."""

    def test_sort_by_score_desc(self):
        """Test sorting results by score descending."""
        results = [
            SearchResult(1, "Low", None, "task", 0.3, 0.2, 0.3),
            SearchResult(2, "High", None, "note", 0.9, 0.5, 0.9),
            SearchResult(3, "Medium", None, "task", 0.6, 0.3, 0.6),
        ]

        sorted_results = sorted(results, key=lambda r: r.score, reverse=True)

        assert sorted_results[0].score == 0.9
        assert sorted_results[1].score == 0.6
        assert sorted_results[2].score == 0.3

    def test_limit_results(self):
        """Test limiting number of results."""
        results = [
            SearchResult(i, f"Result {i}", None, "task", 0.9 - i * 0.1, 0.5, 0.5)
            for i in range(10)
        ]

        limit = 5
        limited = results[:limit]

        assert len(limited) == 5


class TestSimilarityThreshold:
    """Tests for similarity threshold logic."""

    def test_min_similarity_filter(self):
        """Test filtering by minimum similarity."""
        similarities = [0.9, 0.75, 0.6, 0.5, 0.3]
        min_similarity = 0.7

        filtered = [s for s in similarities if s >= min_similarity]

        assert len(filtered) == 2
        assert 0.9 in filtered
        assert 0.75 in filtered

    def test_vector_score_threshold(self):
        """Test vector score threshold for inclusion."""
        results = [
            {"fts": 0.0, "vector": 0.6},  # Should include (vector > 0.5)
            {"fts": 0.3, "vector": 0.4},  # Should include (fts > 0)
            {"fts": 0.0, "vector": 0.4},  # Should NOT include
        ]

        threshold = 0.5
        included = [
            r for r in results
            if r["fts"] > 0 or r["vector"] > threshold
        ]

        assert len(included) == 2
