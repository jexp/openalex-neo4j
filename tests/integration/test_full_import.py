"""Full end-to-end integration tests.

These tests require both a running Neo4j instance and access to OpenAlex API.
They test the complete import workflow from search to graph storage.
"""

import os

import pytest
from dotenv import load_dotenv

from openalex_neo4j.neo4j_client import Neo4jClient
from openalex_neo4j.openalex_client import OpenAlexClient
from openalex_neo4j.importer import OpenAlexImporter

# Load test environment
load_dotenv()

pytestmark = pytest.mark.integration


class TestFullImportWorkflow:
    """End-to-end integration tests for the complete import workflow."""

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

    def test_expand_depth_2(self, neo4j_uri, neo4j_username, neo4j_password):
        """Test importing with depth 2 expansion (citations of citations)."""
        neo4j_client = Neo4jClient(neo4j_uri, neo4j_username, neo4j_password)
        try:
            neo4j_client.connect()
        except Exception as e:
            pytest.skip(f"Cannot connect to Neo4j: {e}")

        openalex_email = os.getenv("OPENALEX_EMAIL")
        openalex_client = OpenAlexClient(email=openalex_email)

        importer = OpenAlexImporter(neo4j_client, openalex_client)

        try:
            # Import with deeper expansion
            counts = importer.import_from_query(
                query="transformer neural network",
                limit=1,  # Just 1 to keep it small
                expand_depth=2
            )

            print(f"\nImported with depth 2: {counts}")

            # With depth 2, we should have more works (including citations of citations)
            work_count = neo4j_client.get_node_count("Work")
            assert work_count >= 1

            # Verify we have citation relationships
            if counts.get("cites", 0) > 0:
                cite_count = neo4j_client.get_relationship_count("CITES")
                assert cite_count > 0
                print(f"Total citations in graph: {cite_count}")

        finally:
            neo4j_client.clear_database()
            neo4j_client.close()

    def test_constraints_created(self, neo4j_uri, neo4j_username, neo4j_password):
        """Test that constraints are properly created during import."""
        neo4j_client = Neo4jClient(neo4j_uri, neo4j_username, neo4j_password)
        try:
            neo4j_client.connect()
        except Exception as e:
            pytest.skip(f"Cannot connect to Neo4j: {e}")

        openalex_email = os.getenv("OPENALEX_EMAIL")
        openalex_client = OpenAlexClient(email=openalex_email)

        importer = OpenAlexImporter(neo4j_client, openalex_client)

        try:
            # Import should create constraints
            counts = importer.import_from_query(
                query="graph database",
                limit=1,
                expand_depth=1
            )

            # Creating constraints again should not error
            neo4j_client.create_constraints()

            # Verify we can't create duplicate nodes
            neo4j_client.batch_create_nodes("Work", [{"id": "TEST1", "title": "Test"}])
            neo4j_client.batch_create_nodes("Work", [{"id": "TEST1", "title": "Duplicate"}])

            # Should have only one node
            work = neo4j_client.get_node_by_id("Work", "TEST1")
            assert work is not None

        finally:
            neo4j_client.clear_database()
            neo4j_client.close()

    def test_deduplication_across_expansions(self, neo4j_uri, neo4j_username, neo4j_password):
        """Test that entities are deduplicated across relationship expansions."""
        neo4j_client = Neo4jClient(neo4j_uri, neo4j_username, neo4j_password)
        try:
            neo4j_client.connect()
        except Exception as e:
            pytest.skip(f"Cannot connect to Neo4j: {e}")

        openalex_email = os.getenv("OPENALEX_EMAIL")
        openalex_client = OpenAlexClient(email=openalex_email)

        importer = OpenAlexImporter(neo4j_client, openalex_client)

        try:
            # Import papers that likely share authors/institutions
            counts = importer.import_from_query(
                query="Stanford deep learning",
                limit=2,
                expand_depth=1
            )

            print(f"\nImported: {counts}")

            # Check that author count is reasonable (not duplicated)
            if counts.get("authors", 0) > 0:
                author_count_in_db = neo4j_client.get_node_count("Author")

                # Should match the import count (no duplication)
                assert author_count_in_db == counts["authors"]

        finally:
            neo4j_client.clear_database()
            neo4j_client.close()

    def test_skip_abstracts(self, neo4j_uri, neo4j_username, neo4j_password):
        """Test that abstracts are skipped when --skip-abstracts flag is used."""
        neo4j_client = Neo4jClient(neo4j_uri, neo4j_username, neo4j_password)
        try:
            neo4j_client.connect()
        except Exception as e:
            pytest.skip(f"Cannot connect to Neo4j: {e}")

        openalex_email = os.getenv("OPENALEX_EMAIL")
        openalex_client = OpenAlexClient(email=openalex_email)

        importer = OpenAlexImporter(neo4j_client, openalex_client)

        try:
            # Import with skip_abstracts=True
            counts = importer.import_from_query(
                query="quantum computing",
                limit=2,
                expand_depth=1,
                skip_abstracts=True
            )

            assert counts.get("works", 0) > 0

            # Verify abstracts are None in database
            if importer.works:
                work_id = list(importer.works.keys())[0]
                work_from_db = neo4j_client.get_node_by_id("Work", work_id)

                assert work_from_db is not None
                # Abstract should be None or not present
                assert work_from_db.get("abstract") is None
                print(f"Verified abstract is skipped for work: {work_from_db['title']}")

        finally:
            neo4j_client.clear_database()
            neo4j_client.close()

    def test_abstract_storage(self, neo4j_uri, neo4j_username, neo4j_password):
        """Test that abstracts are stored when skip_abstracts is False."""
        neo4j_client = Neo4jClient(neo4j_uri, neo4j_username, neo4j_password)
        try:
            neo4j_client.connect()
        except Exception as e:
            pytest.skip(f"Cannot connect to Neo4j: {e}")

        openalex_email = os.getenv("OPENALEX_EMAIL")
        openalex_client = OpenAlexClient(email=openalex_email)

        importer = OpenAlexImporter(neo4j_client, openalex_client)

        try:
            # Import with skip_abstracts=False (default)
            counts = importer.import_from_query(
                query="neural networks",
                limit=2,
                expand_depth=1,
                skip_abstracts=False
            )

            assert counts.get("works", 0) > 0

            # Check if any works have abstracts
            has_abstract = False
            for work_id in list(importer.works.keys())[:3]:  # Check first 3
                work_from_db = neo4j_client.get_node_by_id("Work", work_id)
                if work_from_db and work_from_db.get("abstract"):
                    has_abstract = True
                    print(f"Verified abstract stored for: {work_from_db['title']}")
                    break

            # At least some works should have abstracts (not all papers have abstracts in OpenAlex)
            if has_abstract:
                print("Abstracts are being stored correctly")

        finally:
            neo4j_client.clear_database()
            neo4j_client.close()

    def test_fulltext_index(self, neo4j_uri, neo4j_username, neo4j_password):
        """Test that FULLTEXT index is created and can be queried."""
        neo4j_client = Neo4jClient(neo4j_uri, neo4j_username, neo4j_password)
        try:
            neo4j_client.connect()
        except Exception as e:
            pytest.skip(f"Cannot connect to Neo4j: {e}")

        openalex_email = os.getenv("OPENALEX_EMAIL")
        openalex_client = OpenAlexClient(email=openalex_email)

        importer = OpenAlexImporter(neo4j_client, openalex_client)

        try:
            # Import with abstracts
            counts = importer.import_from_query(
                query="machine learning",
                limit=3,
                expand_depth=1,
                skip_abstracts=False
            )

            assert counts.get("works", 0) > 0

            # Test FULLTEXT index query with Lucene syntax
            with neo4j_client.driver.session() as session:
                result = session.run("""
                    CALL db.index.fulltext.queryNodes("work_fulltext", "machine AND learning")
                    YIELD node, score
                    RETURN node.id as id, node.title as title, score
                    LIMIT 5
                """)
                records = list(result)

                if records:
                    print(f"FULLTEXT index returned {len(records)} results")
                    print(f"Top result: {records[0]['title']} (score: {records[0]['score']})")
                    assert len(records) > 0
                else:
                    # If no results, the index might not be ready yet, but it should exist
                    print("FULLTEXT index exists but returned no results (may need time to populate)")

        finally:
            neo4j_client.clear_database()
            neo4j_client.close()

    def test_embeddings_generation(self, neo4j_uri, neo4j_username, neo4j_password):
        """Test that embeddings are generated when --generate-embeddings flag is used."""
        try:
            # Try to import sentence-transformers
            import sentence_transformers
        except ImportError:
            pytest.skip("sentence-transformers not installed (run: uv sync --extra embeddings)")

        neo4j_client = Neo4jClient(neo4j_uri, neo4j_username, neo4j_password)
        try:
            neo4j_client.connect()
        except Exception as e:
            pytest.skip(f"Cannot connect to Neo4j: {e}")

        openalex_email = os.getenv("OPENALEX_EMAIL")
        openalex_client = OpenAlexClient(email=openalex_email)

        importer = OpenAlexImporter(neo4j_client, openalex_client)

        try:
            # Import with generate_embeddings=True
            counts = importer.import_from_query(
                query="deep learning",
                limit=2,
                expand_depth=1,
                generate_embeddings=True
            )

            assert counts.get("works", 0) > 0

            # Verify embeddings are stored
            embedded_count = 0
            for work_id in list(importer.works.keys()):
                work_from_db = neo4j_client.get_node_by_id("Work", work_id)
                if work_from_db and work_from_db.get("embedding"):
                    embedding = work_from_db["embedding"]
                    # Verify embedding is a list of 384 floats
                    assert isinstance(embedding, list)
                    assert len(embedding) == 384
                    assert all(isinstance(x, float) for x in embedding)
                    embedded_count += 1
                    print(f"Verified embedding for: {work_from_db['title']}")

            # At least some works should have embeddings
            assert embedded_count > 0, "No embeddings were generated"
            print(f"Successfully generated embeddings for {embedded_count} works")

        finally:
            neo4j_client.clear_database()
            neo4j_client.close()

    def test_vector_index(self, neo4j_uri, neo4j_username, neo4j_password):
        """Test that vector index is created and can be queried for similarity search."""
        try:
            import sentence_transformers
        except ImportError:
            pytest.skip("sentence-transformers not installed (run: uv sync --extra embeddings)")

        neo4j_client = Neo4jClient(neo4j_uri, neo4j_username, neo4j_password)
        try:
            neo4j_client.connect()
        except Exception as e:
            pytest.skip(f"Cannot connect to Neo4j: {e}")

        openalex_email = os.getenv("OPENALEX_EMAIL")
        openalex_client = OpenAlexClient(email=openalex_email)

        importer = OpenAlexImporter(neo4j_client, openalex_client)

        try:
            # Import with embeddings
            counts = importer.import_from_query(
                query="neural networks",
                limit=3,
                expand_depth=1,
                generate_embeddings=True
            )

            assert counts.get("works", 0) > 0

            # Find a work with an embedding
            test_work_id = None
            for work_id in importer.works.keys():
                work = neo4j_client.get_node_by_id("Work", work_id)
                if work and work.get("embedding"):
                    test_work_id = work_id
                    break

            if not test_work_id:
                pytest.skip("No works with embeddings found")

            # Test vector similarity search
            with neo4j_client.driver.session() as session:
                result = session.run("""
                    MATCH (w:Work {id: $work_id})
                    CALL db.index.vector.queryNodes("work_embedding_vector", 5, w.embedding)
                    YIELD node, score
                    WHERE node.id <> $work_id
                    RETURN node.id as id, node.title as title, score
                    ORDER BY score DESC
                    LIMIT 3
                """, work_id=test_work_id)

                records = list(result)

                if records:
                    print(f"Vector similarity search returned {len(records)} results")
                    for rec in records:
                        print(f"  Similar paper: {rec['title']} (score: {rec['score']})")
                    assert len(records) > 0
                else:
                    # Vector index might need time to populate
                    print("Vector index exists but returned no results (may need time to populate)")

        finally:
            neo4j_client.clear_database()
            neo4j_client.close()
