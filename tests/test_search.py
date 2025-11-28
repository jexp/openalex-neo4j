"""Unit tests for search module."""

from unittest.mock import Mock, MagicMock
import pytest

from openalex_neo4j.search import HybridSearcher, SearchResult, format_results_table


class TestHybridSearcher:
    """Unit tests for HybridSearcher class."""

    def test_reciprocal_rank_fusion_basic(self):
        """Test RRF with simple rankings."""
        driver = Mock()
        searcher = HybridSearcher(driver)

        vector_results = {"A": 0.9, "B": 0.8, "C": 0.7}
        fulltext_results = {"B": 5.0, "C": 4.0, "D": 3.0}

        fused = searcher._reciprocal_rank_fusion(
            vector_results,
            fulltext_results,
            vector_weight=0.5,
            fulltext_weight=0.5,
            k=60
        )

        # Check that we got all unique documents
        work_ids = [work_id for work_id, _ in fused]
        assert len(work_ids) == 4
        assert set(work_ids) == {"A", "B", "C", "D"}

        # Check that B and C rank higher (in both lists)
        assert "B" in work_ids[:2] or "C" in work_ids[:2]

    def test_reciprocal_rank_fusion_weights(self):
        """Test RRF with different weights."""
        driver = Mock()
        searcher = HybridSearcher(driver)

        vector_results = {"A": 0.9}
        fulltext_results = {"B": 5.0}

        # Vector weight = 1, fulltext weight = 0 (only vector matters)
        fused = searcher._reciprocal_rank_fusion(
            vector_results,
            fulltext_results,
            vector_weight=1.0,
            fulltext_weight=0.0,
            k=60
        )
        assert fused[0][0] == "A"  # A should rank first

        # Vector weight = 0, fulltext weight = 1 (only fulltext matters)
        fused = searcher._reciprocal_rank_fusion(
            vector_results,
            fulltext_results,
            vector_weight=0.0,
            fulltext_weight=1.0,
            k=60
        )
        assert fused[0][0] == "B"  # B should rank first

    def test_reciprocal_rank_fusion_empty(self):
        """Test RRF with empty inputs."""
        driver = Mock()
        searcher = HybridSearcher(driver)

        fused = searcher._reciprocal_rank_fusion({}, {}, k=60)
        assert fused == []

    def test_get_work_details_empty(self):
        """Test get_work_details with empty input."""
        driver = Mock()
        searcher = HybridSearcher(driver)

        results = searcher._get_work_details([], [])
        assert results == []


class TestSearchResult:
    """Tests for SearchResult dataclass."""

    def test_search_result_creation(self):
        """Test creating a SearchResult."""
        result = SearchResult(
            work_id="W123",
            title="Test Paper",
            publication_year=2020,
            doi="10.1234/test",
            cited_by_count=100,
            is_oa=True,
            abstract="This is a test abstract",
            score=0.95,
            authors=["Author 1", "Author 2"],
            institutions=["Institution 1"],
            topics=["Topic 1"],
            source="Journal of Testing"
        )

        assert result.work_id == "W123"
        assert result.title == "Test Paper"
        assert len(result.authors) == 2
        assert result.score == 0.95


class TestFormatResultsTable:
    """Tests for format_results_table function."""

    def test_format_empty_results(self):
        """Test formatting with no results."""
        output = format_results_table([])
        assert output == "No results found."

    def test_format_single_result(self):
        """Test formatting with one result."""
        results = [
            SearchResult(
                work_id="W123",
                title="Test Paper",
                publication_year=2020,
                doi="10.1234/test",
                cited_by_count=100,
                is_oa=True,
                abstract="Short abstract",
                score=0.95,
                authors=["Author 1"],
                institutions=["Institution 1"],
                topics=["Topic 1"],
                source="Journal"
            )
        ]

        output = format_results_table(results)
        assert "Test Paper" in output
        assert "2020" in output
        assert "100" in output  # citations
        assert "Yes" in output  # OA
        assert "Author 1" in output
        assert "Institution 1" in output
        assert "Topic 1" in output
        assert "Journal" in output
        assert "10.1234/test" in output

    def test_format_truncates_long_title(self):
        """Test that long titles are truncated."""
        results = [
            SearchResult(
                work_id="W123",
                title="A" * 100,  # Very long title
                publication_year=2020,
                doi=None,
                cited_by_count=0,
                is_oa=False,
                abstract=None,
                score=0.5,
                authors=[],
                institutions=[],
                topics=[],
                source=None
            )
        ]

        output = format_results_table(results)
        assert "..." in output  # Should have ellipsis

    def test_format_multiple_authors(self):
        """Test formatting with many authors (should truncate)."""
        results = [
            SearchResult(
                work_id="W123",
                title="Test",
                publication_year=2020,
                doi=None,
                cited_by_count=0,
                is_oa=False,
                abstract=None,
                score=0.5,
                authors=["Author 1", "Author 2", "Author 3", "Author 4", "Author 5"],
                institutions=[],
                topics=[],
                source=None
            )
        ]

        output = format_results_table(results)
        assert "Author 1" in output
        assert "(+2 more)" in output  # Should show truncation
