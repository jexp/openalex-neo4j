"""Hybrid search functionality for querying the Neo4j knowledge graph."""

import logging
from dataclasses import dataclass
from typing import Any

from neo4j import Driver

logger = logging.getLogger(__name__)


@dataclass
class SearchResult:
    """A single search result with work and related information."""

    work_id: str
    title: str
    publication_year: int | None
    doi: str | None
    cited_by_count: int
    is_oa: bool
    abstract: str | None
    score: float

    # Related information
    authors: list[str]
    institutions: list[str]
    topics: list[str]
    source: str | None


class HybridSearcher:
    """Performs hybrid search using vector embeddings and fulltext search."""

    def __init__(self, driver: Driver):
        """Initialize the searcher.

        Args:
            driver: Neo4j driver instance
        """
        self.driver = driver

    def search(
        self,
        query: str,
        limit: int = 10,
        vector_weight: float = 0.5,
        fulltext_weight: float = 0.5,
        k: int = 60
    ) -> list[SearchResult]:
        """Perform hybrid search using vector and fulltext search with RRF.

        Args:
            query: Search query string
            limit: Number of results to return
            vector_weight: Weight for vector search (0-1)
            fulltext_weight: Weight for fulltext search (0-1)
            k: Constant for reciprocal rank fusion (default 60)

        Returns:
            List of SearchResult objects ranked by RRF score
        """
        # Get vector search results
        vector_results = self._vector_search(query, limit * 2)

        # Get fulltext search results
        fulltext_results = self._fulltext_search(query, limit * 2)

        # Apply reciprocal rank fusion
        fused_results = self._reciprocal_rank_fusion(
            vector_results,
            fulltext_results,
            vector_weight=vector_weight,
            fulltext_weight=fulltext_weight,
            k=k
        )

        # Get top results
        top_work_ids = [work_id for work_id, _ in fused_results[:limit]]

        # Retrieve full details including related information
        results = self._get_work_details(top_work_ids, fused_results)

        return results

    def _vector_search(self, query: str, limit: int) -> dict[str, float]:
        """Perform vector similarity search.

        Args:
            query: Query text to embed and search
            limit: Number of results

        Returns:
            Dict mapping work_id to similarity score
        """
        try:
            from .embeddings import generate_embedding
        except ImportError:
            logger.warning("sentence-transformers not installed, skipping vector search")
            return {}

        # Generate embedding for query
        query_embedding = generate_embedding(query)
        if not query_embedding:
            logger.warning("Failed to generate query embedding")
            return {}

        # Search using vector index
        with self.driver.session() as session:
            try:
                result = session.run("""
                    CALL db.index.vector.queryNodes(
                        "work_embedding_vector",
                        $limit,
                        $embedding
                    )
                    YIELD node, score
                    RETURN node.id as work_id, score
                """, limit=limit, embedding=query_embedding)

                return {record["work_id"]: record["score"] for record in result}
            except Exception as e:
                logger.warning(f"Vector search failed: {e}")
                return {}

    def _fulltext_search(self, query: str, limit: int) -> dict[str, float]:
        """Perform fulltext search using Lucene.

        Args:
            query: Query string (Lucene syntax supported)
            limit: Number of results

        Returns:
            Dict mapping work_id to relevance score
        """
        with self.driver.session() as session:
            try:
                result = session.run("""
                    CALL db.index.fulltext.queryNodes(
                        "work_fulltext",
                        $query
                    )
                    YIELD node, score
                    RETURN node.id as work_id, score
                    ORDER BY score DESC
                    LIMIT $limit
                """, query=query, limit=limit)

                return {record["work_id"]: record["score"] for record in result}
            except Exception as e:
                logger.warning(f"Fulltext search failed: {e}")
                return {}

    def _reciprocal_rank_fusion(
        self,
        vector_results: dict[str, float],
        fulltext_results: dict[str, float],
        vector_weight: float = 0.5,
        fulltext_weight: float = 0.5,
        k: int = 60
    ) -> list[tuple[str, float]]:
        """Combine results using Reciprocal Rank Fusion (RRF).

        RRF formula: RRF(d) = sum over all rankings r: 1 / (k + r(d))
        where k is a constant (typically 60) and r(d) is the rank of document d.

        Args:
            vector_results: Dict of work_id -> score from vector search
            fulltext_results: Dict of work_id -> score from fulltext search
            vector_weight: Weight for vector search results
            fulltext_weight: Weight for fulltext search results
            k: RRF constant (default 60)

        Returns:
            List of (work_id, fused_score) tuples sorted by score descending
        """
        # Sort results by score to get rankings
        vector_ranked = sorted(
            vector_results.items(),
            key=lambda x: x[1],
            reverse=True
        )
        fulltext_ranked = sorted(
            fulltext_results.items(),
            key=lambda x: x[1],
            reverse=True
        )

        # Calculate RRF scores
        rrf_scores: dict[str, float] = {}

        # Add vector search scores
        for rank, (work_id, _) in enumerate(vector_ranked, start=1):
            rrf_scores[work_id] = vector_weight / (k + rank)

        # Add fulltext search scores
        for rank, (work_id, _) in enumerate(fulltext_ranked, start=1):
            rrf_scores[work_id] = rrf_scores.get(work_id, 0) + fulltext_weight / (k + rank)

        # Sort by RRF score
        fused_results = sorted(
            rrf_scores.items(),
            key=lambda x: x[1],
            reverse=True
        )

        logger.info(
            f"RRF fusion: {len(vector_results)} vector + {len(fulltext_results)} fulltext "
            f"-> {len(fused_results)} combined results"
        )

        return fused_results

    def _get_work_details(
        self,
        work_ids: list[str],
        scores: list[tuple[str, float]]
    ) -> list[SearchResult]:
        """Retrieve full work details including related entities.

        Args:
            work_ids: List of work IDs to retrieve
            scores: List of (work_id, score) tuples for scoring

        Returns:
            List of SearchResult objects
        """
        if not work_ids:
            return []

        # Create score lookup
        score_map = dict(scores)

        with self.driver.session() as session:
            result = session.run("""
                MATCH (w:Work)
                WHERE w.id IN $work_ids

                // Get authors
                OPTIONAL MATCH (w)<-[:AUTHORED]-(author:Author)
                WITH w, collect(DISTINCT author.display_name) as authors

                // Get institutions
                OPTIONAL MATCH (w)<-[:AUTHORED]-(:Author)-[:AFFILIATED_WITH]->(inst:Institution)
                WITH w, authors, collect(DISTINCT inst.display_name) as institutions

                // Get topics
                OPTIONAL MATCH (w)-[:HAS_TOPIC]->(topic:Topic)
                WITH w, authors, institutions, collect(DISTINCT topic.display_name) as topics

                // Get source
                OPTIONAL MATCH (w)-[:PUBLISHED_IN]->(source:Source)

                RETURN
                    w.id as work_id,
                    w.title as title,
                    w.publication_year as publication_year,
                    w.doi as doi,
                    w.cited_by_count as cited_by_count,
                    w.is_oa as is_oa,
                    w.abstract as abstract,
                    authors,
                    institutions,
                    topics,
                    source.display_name as source
            """, work_ids=work_ids)

            results = []
            for record in result:
                work_id = record["work_id"]
                results.append(SearchResult(
                    work_id=work_id,
                    title=record["title"],
                    publication_year=record["publication_year"],
                    doi=record["doi"],
                    cited_by_count=record["cited_by_count"] or 0,
                    is_oa=record["is_oa"] or False,
                    abstract=record["abstract"],
                    score=score_map.get(work_id, 0.0),
                    authors=record["authors"] or [],
                    institutions=record["institutions"] or [],
                    topics=record["topics"] or [],
                    source=record["source"]
                ))

            # Sort by score to maintain RRF order
            results.sort(key=lambda x: x.score, reverse=True)

            return results


def format_results_table(results: list[SearchResult], max_width: int = 80) -> str:
    """Format search results as a readable table.

    Args:
        results: List of SearchResult objects
        max_width: Maximum width for text columns

    Returns:
        Formatted table string
    """
    if not results:
        return "No results found."

    lines = []
    lines.append("=" * 120)
    lines.append(f"{'#':<4} {'Score':<8} {'Title':<50} {'Year':<6} {'Citations':<10} {'OA':<4}")
    lines.append("=" * 120)

    for i, result in enumerate(results, 1):
        # Truncate title if too long
        title = result.title or "(No title)"
        if len(title) > 47:
            title = title[:44] + "..."

        year = str(result.publication_year) if result.publication_year else "N/A"
        citations = str(result.cited_by_count)
        oa = "Yes" if result.is_oa else "No"

        lines.append(
            f"{i:<4} {result.score:<8.4f} {title:<50} {year:<6} {citations:<10} {oa:<4}"
        )

        # Add authors
        if result.authors:
            authors_str = ", ".join(result.authors[:3])
            if len(result.authors) > 3:
                authors_str += f", ... (+{len(result.authors) - 3} more)"
            lines.append(f"     Authors: {authors_str}")

        # Add institutions
        if result.institutions:
            inst_str = ", ".join(result.institutions[:3])
            if len(result.institutions) > 3:
                inst_str += f", ... (+{len(result.institutions) - 3} more)"
            lines.append(f"     Institutions: {inst_str}")

        # Add topics
        if result.topics:
            topics_str = ", ".join(result.topics[:3])
            if len(result.topics) > 3:
                topics_str += f", ... (+{len(result.topics) - 3} more)"
            lines.append(f"     Topics: {topics_str}")

        # Add source
        if result.source:
            lines.append(f"     Source: {result.source}")

        # Add DOI
        if result.doi:
            lines.append(f"     DOI: {result.doi}")

        # Add abstract preview
        if result.abstract:
            abstract_preview = result.abstract[:150]
            if len(result.abstract) > 150:
                abstract_preview += "..."
            lines.append(f"     Abstract: {abstract_preview}")

        lines.append("")  # Empty line between results

    lines.append("=" * 120)

    return "\n".join(lines)
