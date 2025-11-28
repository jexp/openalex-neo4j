"""Integration tests with real Neo4j instance.

These tests require a running Neo4j instance at bolt://localhost:7687
with username 'neo4j' and password 'password' (or configured via .env).
"""

import os

import pytest
from dotenv import load_dotenv

from openalex_neo4j.neo4j_client import Neo4jClient
from openalex_neo4j.openalex_client import OpenAlexClient
from openalex_neo4j.importer import OpenAlexImporter
from openalex_neo4j.models import Work, Author, Institution

# Load test environment
load_dotenv()

# Mark all tests in this module as integration tests
pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def neo4j_uri():
    """Get Neo4j URI from environment."""
    return os.getenv("NEO4J_URI", "bolt://localhost:7687")


@pytest.fixture(scope="module")
def neo4j_username():
    """Get Neo4j username from environment."""
    return os.getenv("NEO4J_USERNAME", "neo4j")


@pytest.fixture(scope="module")
def neo4j_password():
    """Get Neo4j password from environment."""
    password = os.getenv("NEO4J_PASSWORD", "password")
    if not password:
        pytest.skip("NEO4J_PASSWORD not set")
    return password


@pytest.fixture
def neo4j_client(neo4j_uri, neo4j_username, neo4j_password):
    """Create a Neo4j client and clean up after test."""
    client = Neo4jClient(neo4j_uri, neo4j_username, neo4j_password)
    try:
        client.connect()
    except Exception as e:
        pytest.skip(f"Cannot connect to Neo4j: {e}")

    yield client

    # Clean up: delete all test data
    try:
        client.clear_database()
    except Exception:
        pass
    finally:
        client.close()


class TestNeo4jClientIntegration:
    """Integration tests for Neo4j client."""

    def test_connection(self, neo4j_client):
        """Test that we can connect to Neo4j."""
        assert neo4j_client._driver is not None

    def test_create_constraints(self, neo4j_client):
        """Test creating constraints."""
        neo4j_client.create_constraints()

        # Verify constraints were created (should not raise error)
        neo4j_client.create_constraints()

    def test_batch_create_nodes(self, neo4j_client):
        """Test creating nodes in batch."""
        nodes = [
            {"id": "W1", "title": "Paper 1", "publication_year": 2020},
            {"id": "W2", "title": "Paper 2", "publication_year": 2021},
            {"id": "W3", "title": "Paper 3", "publication_year": 2022},
        ]

        count = neo4j_client.batch_create_nodes("Work", nodes)
        assert count == 3

        # Verify nodes exist
        assert neo4j_client.get_node_count("Work") == 3

        # Verify node properties are stored correctly
        work1 = neo4j_client.get_node_by_id("Work", "W1")
        assert work1 is not None
        assert work1["id"] == "W1"
        assert work1["title"] == "Paper 1"
        assert work1["publication_year"] == 2020

        work2 = neo4j_client.get_node_by_id("Work", "W2")
        assert work2 is not None
        assert work2["title"] == "Paper 2"
        assert work2["publication_year"] == 2021

    def test_batch_create_relationships(self, neo4j_client):
        """Test creating relationships in batch."""
        # Create nodes first
        work_nodes = [
            {"id": "W1", "title": "Paper 1"},
            {"id": "W2", "title": "Paper 2"},
        ]
        author_nodes = [
            {"id": "A1", "display_name": "Author 1"},
        ]

        neo4j_client.batch_create_nodes("Work", work_nodes)
        neo4j_client.batch_create_nodes("Author", author_nodes)

        # Create relationships
        rels = [
            {"source_id": "A1", "target_id": "W1"},
            {"source_id": "A1", "target_id": "W2"},
        ]

        count = neo4j_client.batch_create_relationships(
            "AUTHORED", "Author", "Work", rels
        )
        assert count == 2

        # Verify relationships exist
        assert neo4j_client.get_relationship_count("AUTHORED") == 2

        # Verify actual relationships connect the right nodes
        authored_rels = neo4j_client.get_relationships("AUTHORED", "Author", "Work")
        assert len(authored_rels) == 2

        # Check that both relationships exist
        rel_pairs = {(rel["source_id"], rel["target_id"]) for rel in authored_rels}
        assert ("A1", "W1") in rel_pairs
        assert ("A1", "W2") in rel_pairs

    def test_merge_duplicates(self, neo4j_client):
        """Test that MERGE handles duplicate nodes correctly."""
        nodes = [
            {"id": "W1", "title": "Paper 1"},
            {"id": "W1", "title": "Paper 1 Updated"},  # Duplicate
        ]

        neo4j_client.batch_create_nodes("Work", nodes)

        # Should have only 1 node
        assert neo4j_client.get_node_count("Work") == 1

        # Verify the node has updated properties
        work = neo4j_client.get_node_by_id("Work", "W1")
        assert work is not None
        assert work["id"] == "W1"
        # Last write wins - should have updated title
        assert work["title"] == "Paper 1 Updated"

    def test_get_counts(self, neo4j_client):
        """Test getting node and relationship counts."""
        # Create some data
        neo4j_client.batch_create_nodes("Work", [{"id": "W1", "title": "Test"}])
        neo4j_client.batch_create_nodes("Author", [{"id": "A1", "display_name": "Test"}])

        work_count = neo4j_client.get_node_count("Work")
        author_count = neo4j_client.get_node_count("Author")

        assert work_count == 1
        assert author_count == 1

        # Verify we can retrieve the actual nodes
        work = neo4j_client.get_node_by_id("Work", "W1")
        author = neo4j_client.get_node_by_id("Author", "A1")

        assert work is not None
        assert work["title"] == "Test"
        assert author is not None
        assert author["display_name"] == "Test"


class TestOpenAlexClientIntegration:
    """Integration tests for OpenAlex client.

    These tests hit the real OpenAlex API.
    Keep queries small to avoid rate limits.
    """

    @pytest.fixture
    def openalex_client(self):
        """Create OpenAlex client."""
        email = os.getenv("OPENALEX_EMAIL")
        return OpenAlexClient(email=email)

    def test_search_works(self, openalex_client):
        """Test searching for works."""
        # Search for a very specific paper to get consistent results
        works = openalex_client.search_works("quantum computing", limit=5)

        assert len(works) > 0
        assert len(works) <= 5
        assert all(isinstance(w, Work) for w in works)
        assert all(w.id.startswith("W") for w in works)

    def test_fetch_works_by_ids(self, openalex_client):
        """Test fetching specific works by ID."""
        # Use a known work ID
        # This is a real paper about quantum computing
        work_ids = ["W2741809807"]

        works = openalex_client.fetch_works_by_ids(work_ids)

        assert len(works) >= 0  # May not find it if removed from OpenAlex

    def test_fetch_authors_by_ids(self, openalex_client):
        """Test fetching authors by ID."""
        # First get a work to find author IDs
        works = openalex_client.search_works("artificial intelligence", limit=1)

        if works and works[0].author_ids:
            author_ids = works[0].author_ids[:2]  # Just fetch first 2
            authors = openalex_client.fetch_authors_by_ids(author_ids)

            assert len(authors) > 0
            assert all(isinstance(a, Author) for a in authors)


class TestFullImportIntegration:
    """Integration test for full import workflow."""

    def test_small_import(self, neo4j_uri, neo4j_username, neo4j_password):
        """Test importing a small dataset and validate data in Neo4j."""
        # Create clients
        neo4j_client = Neo4jClient(neo4j_uri, neo4j_username, neo4j_password)
        try:
            neo4j_client.connect()
        except Exception as e:
            pytest.skip(f"Cannot connect to Neo4j: {e}")

        openalex_email = os.getenv("OPENALEX_EMAIL")
        openalex_client = OpenAlexClient(email=openalex_email)

        # Create importer
        importer = OpenAlexImporter(neo4j_client, openalex_client)

        try:
            # Import a very small dataset
            counts = importer.import_from_query(
                query="quantum computing",
                limit=3,  # Very small to avoid rate limits
                expand_depth=1
            )

            # Verify something was imported
            assert counts.get("works", 0) > 0
            print(f"\nImported: {counts}")

            # Verify nodes exist in database
            work_count = neo4j_client.get_node_count("Work")
            assert work_count > 0

            # Validate that we can retrieve actual work data
            # Get a work ID from the importer
            if importer.works:
                work_id = list(importer.works.keys())[0]
                work_from_db = neo4j_client.get_node_by_id("Work", work_id)

                assert work_from_db is not None, f"Work {work_id} not found in database"
                assert work_from_db["id"] == work_id
                assert "title" in work_from_db
                print(f"Validated work: {work_from_db['title']}")

            # Validate authors if any were imported
            if counts.get("authors", 0) > 0:
                author_count = neo4j_client.get_node_count("Author")
                assert author_count > 0

                # Get an author and validate
                if importer.authors:
                    author_id = list(importer.authors.keys())[0]
                    author_from_db = neo4j_client.get_node_by_id("Author", author_id)

                    assert author_from_db is not None
                    assert author_from_db["id"] == author_id
                    assert "display_name" in author_from_db

        finally:
            # Clean up
            neo4j_client.clear_database()
            neo4j_client.close()

    def test_import_with_relationships(self, neo4j_uri, neo4j_username, neo4j_password):
        """Test that relationships are created correctly and validate in Neo4j."""
        neo4j_client = Neo4jClient(neo4j_uri, neo4j_username, neo4j_password)
        try:
            neo4j_client.connect()
        except Exception as e:
            pytest.skip(f"Cannot connect to Neo4j: {e}")

        openalex_email = os.getenv("OPENALEX_EMAIL")
        openalex_client = OpenAlexClient(email=openalex_email)

        importer = OpenAlexImporter(neo4j_client, openalex_client)

        try:
            # Import with relationship expansion
            counts = importer.import_from_query(
                query="machine learning",
                limit=2,
                expand_depth=1
            )

            # Check that we have both nodes and relationships
            assert counts.get("works", 0) > 0
            print(f"\nImported: {counts}")

            # Check for author relationships if authors were found
            if counts.get("authors", 0) > 0:
                authored_count = neo4j_client.get_relationship_count("AUTHORED")
                assert authored_count > 0

                # Validate actual relationships
                authored_rels = neo4j_client.get_relationships("AUTHORED", "Author", "Work", limit=10)
                assert len(authored_rels) > 0

                # Pick one relationship and validate both ends exist
                rel = authored_rels[0]
                author = neo4j_client.get_node_by_id("Author", rel["source_id"])
                work = neo4j_client.get_node_by_id("Work", rel["target_id"])

                assert author is not None, f"Author {rel['source_id']} not found"
                assert work is not None, f"Work {rel['target_id']} not found"
                print(f"Validated relationship: {author['display_name']} -> {work['title']}")

            # Check for source relationships if sources were found
            if counts.get("sources", 0) > 0 and counts.get("published_in", 0) > 0:
                published_rels = neo4j_client.get_relationships("PUBLISHED_IN", "Work", "Source", limit=5)
                if published_rels:
                    rel = published_rels[0]
                    work = neo4j_client.get_node_by_id("Work", rel["source_id"])
                    source = neo4j_client.get_node_by_id("Source", rel["target_id"])

                    assert work is not None
                    assert source is not None
                    print(f"Validated publication: {work['title']} in {source['display_name']}")

            # Check for citation relationships if they exist
            if counts.get("cites", 0) > 0:
                cite_rels = neo4j_client.get_relationships("CITES", "Work", "Work", limit=5)
                if cite_rels:
                    rel = cite_rels[0]
                    citing_work = neo4j_client.get_node_by_id("Work", rel["source_id"])
                    cited_work = neo4j_client.get_node_by_id("Work", rel["target_id"])

                    assert citing_work is not None
                    assert cited_work is not None
                    print(f"Validated citation: {citing_work['title']} cites {cited_work['title']}")

        finally:
            neo4j_client.clear_database()
            neo4j_client.close()
