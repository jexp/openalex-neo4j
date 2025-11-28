"""Unit tests for Neo4j utility functions."""

import pytest

from openalex_neo4j.neo4j_client import to_camel_case_label


class TestToCamelCaseLabel:
    """Tests for to_camel_case_label function."""

    def test_simple_hyphenated(self):
        """Test converting simple hyphenated text."""
        assert to_camel_case_label("journal-article") == "JournalArticle"
        assert to_camel_case_label("book-chapter") == "BookChapter"
        assert to_camel_case_label("proceedings-article") == "ProceedingsArticle"

    def test_single_word(self):
        """Test converting single word."""
        assert to_camel_case_label("article") == "Article"
        assert to_camel_case_label("book") == "Book"

    def test_multiple_hyphens(self):
        """Test converting text with multiple hyphens."""
        assert to_camel_case_label("peer-review-journal-article") == "PeerReviewJournalArticle"

    def test_none_input(self):
        """Test with None input."""
        assert to_camel_case_label(None) is None

    def test_empty_string(self):
        """Test with empty string."""
        assert to_camel_case_label("") is None

    def test_preserves_capitalization(self):
        """Test that it capitalizes each part."""
        assert to_camel_case_label("JOURNAL-ARTICLE") == "JournalArticle"
        assert to_camel_case_label("journal-ARTICLE") == "JournalArticle"
