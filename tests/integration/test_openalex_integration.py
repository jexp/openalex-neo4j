"""Integration tests for OpenAlex client.

These tests hit the real OpenAlex API.
Keep queries small to avoid rate limits.
"""

import pytest

from openalex_neo4j.models import Work, Author

pytestmark = pytest.mark.integration


class TestOpenAlexClientIntegration:
    """Integration tests for OpenAlex client with real API."""

    def test_search_works(self, openalex_client):
        """Test searching for works via OpenAlex API."""
        # Search for a very specific topic to get consistent results
        works = openalex_client.search_works("quantum computing", limit=5)

        assert len(works) > 0
        assert len(works) <= 5
        assert all(isinstance(w, Work) for w in works)
        assert all(w.id.startswith("W") for w in works)

        # Verify work has expected properties
        first_work = works[0]
        assert first_work.id is not None
        assert first_work.title is not None

    def test_fetch_works_by_ids(self, openalex_client):
        """Test fetching specific works by ID."""
        # Use a known work ID
        # This is a real paper about quantum computing
        work_ids = ["W2741809807"]

        works = openalex_client.fetch_works_by_ids(work_ids)

        # May not find it if removed from OpenAlex, but shouldn't error
        assert isinstance(works, list)
        if works:
            assert all(w.id.startswith("W") for w in works)

    def test_fetch_authors_by_ids(self, openalex_client):
        """Test fetching authors by ID."""
        # First get a work to find author IDs
        works = openalex_client.search_works("artificial intelligence", limit=1)

        if works and works[0].author_ids:
            author_ids = works[0].author_ids[:2]  # Just fetch first 2
            authors = openalex_client.fetch_authors_by_ids(author_ids)

            assert len(authors) > 0
            assert all(isinstance(a, Author) for a in authors)
            assert all(a.id.startswith("A") for a in authors)

            # Verify author has expected properties
            first_author = authors[0]
            assert first_author.id is not None
            assert first_author.display_name is not None

    def test_fetch_institutions_by_ids(self, openalex_client):
        """Test fetching institutions by ID."""
        # Get a work with institution data
        works = openalex_client.search_works("machine learning", limit=1)

        if works and works[0].institution_ids:
            institution_ids = works[0].institution_ids[:2]
            institutions = openalex_client.fetch_institutions_by_ids(institution_ids)

            if institutions:
                assert all(i.id.startswith("I") for i in institutions)
                assert all(i.display_name is not None for i in institutions)

    def test_fetch_sources_by_ids(self, openalex_client):
        """Test fetching sources by ID."""
        # Get a work with source data
        works = openalex_client.search_works("deep learning", limit=1)

        if works and works[0].source_id:
            sources = openalex_client.fetch_sources_by_ids([works[0].source_id])

            if sources:
                assert all(s.id.startswith("S") for s in sources)
                assert all(s.display_name is not None for s in sources)

    def test_fetch_topics_by_ids(self, openalex_client):
        """Test fetching topics by ID."""
        # Get a work with topic data
        works = openalex_client.search_works("neural networks", limit=1)

        if works and works[0].topic_ids:
            topic_ids = works[0].topic_ids[:2]
            topics = openalex_client.fetch_topics_by_ids(topic_ids)

            if topics:
                assert all(t.id.startswith("T") for t in topics)
                assert all(t.display_name is not None for t in topics)

    def test_search_respects_limit(self, openalex_client):
        """Test that search respects the limit parameter."""
        works = openalex_client.search_works("computer science", limit=3)

        # Should return at most 3 works
        assert len(works) <= 3

    def test_work_has_relationships(self, openalex_client):
        """Test that fetched works have relationship data."""
        works = openalex_client.search_works("natural language processing", limit=2)

        if works:
            work = works[0]

            # At least one of these should be present for most papers
            has_relationships = (
                len(work.author_ids) > 0 or
                len(work.institution_ids) > 0 or
                work.source_id is not None or
                len(work.topic_ids) > 0 or
                len(work.referenced_work_ids) > 0
            )

            assert has_relationships, "Work should have at least some relationship data"
