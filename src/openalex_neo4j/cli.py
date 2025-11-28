"""Command-line interface for OpenAlex to Neo4j import tool."""

import logging
import os
import sys

import click
from dotenv import load_dotenv

from .neo4j_client import Neo4jClient
from .openalex_client import OpenAlexClient
from .importer import OpenAlexImporter

# Load environment variables from .env file
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@click.command()
@click.option(
    "--query", "-q",
    required=True,
    help="OpenAlex search query (e.g., 'artificial intelligence')",
)
@click.option(
    "--limit", "-l",
    default=100,
    type=int,
    help="Maximum number of works to fetch (default: 100)",
)
@click.option(
    "--neo4j-uri",
    default=lambda: os.getenv("NEO4J_URI", "bolt://localhost:7687"),
    help="Neo4j connection URI (env: NEO4J_URI)",
)
@click.option(
    "--neo4j-username",
    default=lambda: os.getenv("NEO4J_USERNAME", "neo4j"),
    help="Neo4j username (env: NEO4J_USERNAME)",
)
@click.option(
    "--neo4j-password",
    default=lambda: os.getenv("NEO4J_PASSWORD"),
    help="Neo4j password (env: NEO4J_PASSWORD)",
)
@click.option(
    "--email",
    default=lambda: os.getenv("OPENALEX_EMAIL"),
    help="Email for OpenAlex polite pool (env: OPENALEX_EMAIL)",
)
@click.option(
    "--expand-depth",
    default=1,
    type=int,
    help="Levels of relationship expansion (default: 1)",
)
@click.option(
    "--skip-abstracts",
    is_flag=True,
    help="Skip storing abstracts (faster import, less storage)",
)
@click.option(
    "--generate-embeddings",
    is_flag=True,
    help="Generate embeddings for semantic search (requires sentence-transformers)",
)
@click.option(
    "--verbose", "-v",
    is_flag=True,
    help="Enable verbose logging",
)
def main(
    query: str,
    limit: int,
    neo4j_uri: str,
    neo4j_username: str,
    neo4j_password: str | None,
    email: str | None,
    expand_depth: int,
    skip_abstracts: bool,
    generate_embeddings: bool,
    verbose: bool,
) -> None:
    """Import OpenAlex scholarly data into Neo4j.

    Search OpenAlex using a natural language query and import the results
    along with related entities (authors, institutions, citations, etc.)
    into a Neo4j graph database.

    Example:

        openalex-neo4j --query "machine learning" --limit 50

    """
    # Set logging level
    if verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Validate inputs
    if not neo4j_password:
        click.echo("Error: Neo4j password is required (use --neo4j-password or NEO4J_PASSWORD env var)", err=True)
        sys.exit(1)

    if limit <= 0:
        click.echo("Error: --limit must be positive", err=True)
        sys.exit(1)

    if expand_depth < 1:
        click.echo("Error: --expand-depth must be at least 1", err=True)
        sys.exit(1)

    # Display configuration
    click.echo("=" * 70)
    click.echo("OpenAlex to Neo4j Import")
    click.echo("=" * 70)
    click.echo(f"Query: {query}")
    click.echo(f"Limit: {limit} works")
    click.echo(f"Expand depth: {expand_depth}")
    click.echo(f"Neo4j URI: {neo4j_uri}")
    click.echo(f"Neo4j username: {neo4j_username}")
    click.echo(f"OpenAlex email: {email or '(not set - using anonymous pool)'}")
    click.echo("=" * 70)
    click.echo()

    try:
        # Initialize clients
        click.echo("Connecting to Neo4j...")
        neo4j_client = Neo4jClient(neo4j_uri, neo4j_username, neo4j_password)
        neo4j_client.connect()

        click.echo("Initializing OpenAlex client...")
        openalex_client = OpenAlexClient(email)

        click.echo("Starting import...")
        click.echo()

        # Create importer and run
        importer = OpenAlexImporter(neo4j_client, openalex_client)
        counts = importer.import_from_query(
            query, limit, expand_depth,
            skip_abstracts=skip_abstracts,
            generate_embeddings=generate_embeddings
        )

        # Display results
        click.echo()
        click.echo("=" * 70)
        click.echo("Import Complete!")
        click.echo("=" * 70)
        click.echo()
        click.echo("Nodes created:")
        click.echo(f"  Works: {counts.get('works', 0)}")
        click.echo(f"  Authors: {counts.get('authors', 0)}")
        click.echo(f"  Institutions: {counts.get('institutions', 0)}")
        click.echo(f"  Sources: {counts.get('sources', 0)}")
        click.echo(f"  Topics: {counts.get('topics', 0)}")
        click.echo(f"  Publishers: {counts.get('publishers', 0)}")
        click.echo(f"  Funders: {counts.get('funders', 0)}")
        click.echo()
        click.echo("Relationships created:")
        click.echo(f"  AUTHORED: {counts.get('authored', 0)}")
        click.echo(f"  AFFILIATED_WITH: {counts.get('affiliated_with', 0)}")
        click.echo(f"  PUBLISHED_IN: {counts.get('published_in', 0)}")
        click.echo(f"  CITES: {counts.get('cites', 0)}")
        click.echo(f"  HAS_TOPIC: {counts.get('has_topic', 0)}")
        click.echo(f"  FUNDED_BY: {counts.get('funded_by', 0)}")
        click.echo(f"  PUBLISHED_BY: {counts.get('published_by', 0)}")
        click.echo("=" * 70)

        # Clean up
        neo4j_client.close()

    except KeyboardInterrupt:
        click.echo("\nImport cancelled by user", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"\nError: {e}", err=True)
        logger.exception("Import failed")
        sys.exit(1)


if __name__ == "__main__":
    main()
