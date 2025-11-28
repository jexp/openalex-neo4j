# OpenAlex to Neo4j Import Tool

A Python CLI tool for importing OpenAlex scholarly data into a Neo4j graph database and performing intelligent hybrid search. Import data starting from a search query, expand relationships, and query the knowledge graph using combined vector similarity and fulltext search.

## Features

### Data Import
- Search OpenAlex using natural language queries
- Import scholarly data as a graph structure
- Automatically create Neo4j constraints for data integrity
- Efficient batch import using Cypher UNWIND statements
- Expand relationships to configurable depth
- Support for all major OpenAlex entities:
  - Works (papers, articles, books)
  - Authors
  - Institutions
  - Sources (journals, conferences)
  - Topics
  - Publishers
  - Funders

### Hybrid Search
- **Vector similarity search** using sentence embeddings (all-MiniLM-L6-v2)
- **Fulltext search** using Lucene-based FULLTEXT indexes
- **Reciprocal Rank Fusion (RRF)** for intelligent result merging
- Comprehensive results with authors, institutions, topics, citations
- Configurable weights for vector vs fulltext search
- Tabular output with detailed paper information

## Requirements

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) (recommended) or pip
- Neo4j 4.0+ (local or remote instance)

## Installation

### Using uv (recommended)

```bash
# Clone the repository
git clone <repository-url>
cd openalex-neo4j

# Install dependencies (uv handles venv automatically)
uv sync

# Optional: Install with embedding support for semantic search
uv sync --extra embeddings

# Or install in development mode
uv pip install -e ".[dev]"
```

### Using pip

```bash
# Clone the repository
git clone <repository-url>
cd openalex-neo4j

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -e ".[dev]"
```

## Configuration

Create a `.env` file in the project root (or use environment variables):

```bash
NEO4J_URI=bolt://localhost:7687
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=password
OPENALEX_EMAIL=your.email@example.com
```

See `.env.example` for a template.

## Usage

The CLI has two main commands: `import` for loading data from OpenAlex, and `search` for querying the knowledge graph.

### Import Data

Import scholarly data from OpenAlex into Neo4j:

```bash
# Basic import
uv run openalex-neo4j import --query "artificial intelligence" --limit 50

# Import with embeddings for semantic search
uv run openalex-neo4j import \
  --query "machine learning ethics" \
  --limit 100 \
  --generate-embeddings \
  --expand-depth 2
```

**Import Options:**

- `--query, -q`: OpenAlex search query (required)
- `--limit, -l`: Maximum number of works to fetch (default: 100)
- `--neo4j-uri`: Neo4j connection URI (env: NEO4J_URI)
- `--neo4j-username`: Neo4j username (env: NEO4J_USERNAME)
- `--neo4j-password`: Neo4j password (env: NEO4J_PASSWORD)
- `--email`: Email for OpenAlex polite pool (env: OPENALEX_EMAIL)
- `--expand-depth`: Levels of relationship expansion (default: 1)
- `--skip-abstracts`: Skip storing abstracts (faster import, less storage)
- `--generate-embeddings`: Generate embeddings for semantic search (requires `--extra embeddings`)
- `--verbose, -v`: Enable verbose logging

### Search the Knowledge Graph

Perform hybrid search combining vector similarity and fulltext search:

```bash
# Basic search
uv run openalex-neo4j search --query "neural networks for computer vision"

# Advanced search with custom weights
uv run openalex-neo4j search \
  --query "transformer architectures" \
  --limit 20 \
  --vector-weight 0.7 \
  --fulltext-weight 0.3
```

**Search Options:**

- `--query, -q`: Search query in natural language (required)
- `--limit, -l`: Number of results to return (default: 10)
- `--neo4j-uri`: Neo4j connection URI (env: NEO4J_URI)
- `--neo4j-username`: Neo4j username (env: NEO4J_USERNAME)
- `--neo4j-password`: Neo4j password (env: NEO4J_PASSWORD)
- `--vector-weight`: Weight for vector search, 0-1 (default: 0.5)
- `--fulltext-weight`: Weight for fulltext search, 0-1 (default: 0.5)
- `--rrf-k`: RRF constant for rank fusion (default: 60)
- `--verbose, -v`: Enable verbose logging

**How Hybrid Search Works:**

The search command combines two search methods using Reciprocal Rank Fusion (RRF):

1. **Vector Similarity Search**: Generates an embedding for your query and finds papers with similar embeddings (semantic similarity)
2. **Fulltext Search**: Uses Lucene-based fulltext index to find papers matching keywords in titles and abstracts
3. **Reciprocal Rank Fusion**: Merges results from both methods using RRF, which gives higher scores to papers that rank well in both searches

Results include comprehensive information: title, authors, institutions, topics, source, DOI, citations, and abstract preview.

## Architecture

The tool follows a two-phase import process:

1. **Node Creation**: All entities are created first using batch MERGE operations
2. **Relationship Creation**: Relationships are created after all nodes exist

This approach ensures referential integrity and optimal performance.

### Entity Types & Relationships

```
Work --AUTHORED--> Author
Work --PUBLISHED_IN--> Source
Work --CITES--> Work
Work --HAS_TOPIC--> Topic
Work --FUNDED_BY--> Funder
Author --AFFILIATED_WITH--> Institution
Source --PUBLISHED_BY--> Publisher
```

### Indexes for Search Performance

The tool automatically creates indexes for common search fields:

**FULLTEXT Index** (Lucene-based, multi-property search):
- `work_fulltext` - Searches across both `Work.title` and `Work.abstract`
  - Requires procedure call: `db.index.fulltext.queryNodes()`
  - Supports Lucene query syntax (AND, OR, NOT, wildcards, fuzzy search)
  - Returns relevance scores

**TEXT Indexes** (for simple string matching):
- `Work.title` - Simple title search in regular Cypher queries
- `Author.display_name` - Find authors by name
- `Institution.display_name` - Search institutions
- `Source.display_name` - Find journals/venues
- `Topic.display_name` - Search by research topics

**Regular Indexes** (for exact matches and range queries):
- `Work.doi` - Lookup papers by DOI
- `Work.publication_year` - Filter/sort by year
- `Work.type` - Filter by publication type
- `Work.is_oa` - Filter open access papers
- `Author.orcid` - Find authors by ORCID
- `Institution.ror` - Lookup by ROR identifier
- `Institution.country_code` - Filter by country
- `Source.issn_l` - Find journals by ISSN

**Vector Index** (for semantic search, optional):
- `Work.embedding` - Similarity search on paper content (384-dimensional)
  - Enabled with `--generate-embeddings` flag
  - Uses all-MiniLM-L6-v2 model for embeddings
  - Requires Neo4j 5.11+ and `sentence-transformers` package

These indexes improve query performance for common search patterns. See the [Example Queries](#example-queries) section for usage examples.

## Testing

The project has comprehensive test coverage with unit and integration tests.

### Unit Tests

Unit tests use mocked dependencies and don't require external services:

```bash
# Run all unit tests
uv run pytest tests/ -v -m "not integration"

# Run with coverage
uv run pytest --cov=openalex_neo4j tests/ -m "not integration"
```

### Integration Tests

Integration tests are organized by component and require external services:

```bash
# Run all integration tests (requires Neo4j + internet)
uv run pytest tests/integration/ -v

# Run Neo4j-only integration tests (requires running Neo4j instance)
uv run pytest tests/integration/test_neo4j_integration.py -v

# Run OpenAlex API integration tests (requires internet)
uv run pytest tests/integration/test_openalex_integration.py -v

# Run full end-to-end import tests (requires both Neo4j + internet)
uv run pytest tests/integration/test_full_import.py -v
```

### All Tests

```bash
# Run all tests (unit + integration)
uv run pytest tests/ -v

# Run with coverage
uv run pytest --cov=openalex_neo4j tests/
```

### Test Organization

- `tests/test_*.py` - Unit tests with mocked dependencies
- `tests/integration/test_neo4j_integration.py` - Neo4j database operations
- `tests/integration/test_openalex_integration.py` - OpenAlex API calls
- `tests/integration/test_full_import.py` - End-to-end import workflow

## Development

The project structure:

```
openalex-neo4j/
├── src/openalex_neo4j/
│   ├── cli.py              # CLI interface
│   ├── neo4j_client.py     # Neo4j operations
│   ├── openalex_client.py  # OpenAlex data fetching
│   ├── models.py           # Data models
│   └── importer.py         # Import orchestration
└── tests/
    ├── test_neo4j_client.py
    ├── test_openalex_client.py
    ├── test_importer.py
    └── test_integration.py
```

## License

MIT

## Contributing

Contributions welcome! Please open an issue or submit a pull request.

## Example Queries

Once data is imported, you can query it using Cypher. Here are some examples:

```cypher
// Find works by DOI (exact match)
MATCH (w:Work {doi: "10.1038/nature12373"})
RETURN w.title, w.publication_year

// Find open access works from 2023
MATCH (w:Work)
WHERE w.is_oa = true AND w.publication_year = 2023
RETURN w.title, w.doi
LIMIT 10

// FULLTEXT search across title and abstract (Lucene syntax)
CALL db.index.fulltext.queryNodes("work_fulltext", "quantum AND computing")
YIELD node, score
RETURN node.title, node.publication_year, score
ORDER BY score DESC
LIMIT 20

// FULLTEXT search with wildcards and fuzzy matching
CALL db.index.fulltext.queryNodes("work_fulltext", "machinelearning~ OR \"deep learning\"")
YIELD node, score
WHERE score > 0.5
RETURN node.title, node.abstract, score
ORDER BY score DESC
LIMIT 10

// Simple substring search on title (when fulltext not needed)
MATCH (w:Work)
WHERE w.title CONTAINS "neural"
RETURN w.title, w.publication_year
ORDER BY w.cited_by_count DESC
LIMIT 20

// Find authors by ORCID
MATCH (a:Author {orcid: "0000-0001-2345-6789"})
RETURN a.display_name, a.works_count

// Find an author's works
MATCH (a:Author {display_name: "Geoffrey Hinton"})-[:AUTHORED]->(w:Work)
RETURN w.title, w.publication_year
ORDER BY w.publication_year DESC
LIMIT 10

// Find works citing a specific paper
MATCH (citing:Work)-[:CITES]->(cited:Work {id: "W2741809807"})
RETURN citing.title, citing.publication_year
ORDER BY citing.cited_by_count DESC
LIMIT 20

// Find collaborators (authors who co-authored papers)
MATCH (a1:Author)-[:AUTHORED]->(w:Work)<-[:AUTHORED]-(a2:Author)
WHERE a1.display_name = "Yann LeCun" AND a1 <> a2
RETURN DISTINCT a2.display_name, count(w) as collaborations
ORDER BY collaborations DESC
LIMIT 10

// Find papers by institution
MATCH (i:Institution {display_name: "Stanford University"})<-[:AFFILIATED_WITH]-(a:Author)-[:AUTHORED]->(w:Work)
RETURN DISTINCT w.title, w.publication_year
ORDER BY w.cited_by_count DESC
LIMIT 20

// Citation network around a topic
MATCH (t:Topic {display_name: "Machine learning"})<-[:HAS_TOPIC]-(w1:Work)-[:CITES]->(w2:Work)
RETURN w1.title, w2.title, w1.publication_year
LIMIT 50

// Find similar papers using vector similarity (requires --generate-embeddings)
MATCH (w:Work {id: "W2741809807"})
CALL db.index.vector.queryNodes("work_embedding_vector", 10, w.embedding)
YIELD node, score
WHERE node <> w
RETURN node.title, node.publication_year, score
ORDER BY score DESC
LIMIT 10
```

## Resources

- [OpenAlex API Documentation](https://docs.openalex.org/)
- [PyAlex Library](https://github.com/J535D165/pyalex)
- [Neo4j Python Driver](https://neo4j.com/docs/python-manual/current/)
- [Cypher Query Language](https://neo4j.com/docs/cypher-manual/current/)
