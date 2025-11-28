"""Shared fixtures for integration tests."""

import os

import pytest
from dotenv import load_dotenv

from openalex_neo4j.neo4j_client import Neo4jClient
from openalex_neo4j.openalex_client import OpenAlexClient

# Load test environment
load_dotenv()


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


@pytest.fixture
def openalex_client():
    """Create OpenAlex client."""
    email = os.getenv("OPENALEX_EMAIL")
    return OpenAlexClient(email=email)
