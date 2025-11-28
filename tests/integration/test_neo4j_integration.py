"""Integration tests for Neo4j client.

These tests require a running Neo4j instance.
Configure connection via environment variables or .env file.
"""

import pytest

from openalex_neo4j.neo4j_client import Neo4jClient

pytestmark = pytest.mark.integration


class TestNeo4jClientIntegration:
    """Integration tests for Neo4j client operations."""

    def test_connection(self, neo4j_client):
        """Test that we can connect to Neo4j."""
        assert neo4j_client._driver is not None

    def test_create_constraints(self, neo4j_client):
        """Test creating constraints."""
        neo4j_client.create_constraints()

        # Verify constraints were created (should not raise error)
        neo4j_client.create_constraints()

    def test_batch_create_nodes(self, neo4j_client):
        """Test creating nodes in batch and validating properties."""
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
        """Test creating relationships in batch and validating connections."""
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

    def test_query_methods(self, neo4j_client):
        """Test node and relationship query methods."""
        # Create test data
        neo4j_client.batch_create_nodes("Work", [
            {"id": "W1", "title": "Work 1"},
            {"id": "W2", "title": "Work 2"},
        ])
        neo4j_client.batch_create_nodes("Author", [{"id": "A1", "display_name": "Author"}])

        neo4j_client.batch_create_relationships(
            "AUTHORED", "Author", "Work",
            [{"source_id": "A1", "target_id": "W1"}]
        )

        # Test get_node_by_id
        work = neo4j_client.get_node_by_id("Work", "W1")
        assert work["title"] == "Work 1"

        # Test get_node_by_id with non-existent node
        missing = neo4j_client.get_node_by_id("Work", "W999")
        assert missing is None

        # Test get_relationships
        rels = neo4j_client.get_relationships("AUTHORED")
        assert len(rels) == 1
        assert rels[0]["source_id"] == "A1"
        assert rels[0]["target_id"] == "W1"
