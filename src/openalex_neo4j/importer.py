"""Import orchestration for OpenAlex data into Neo4j."""

import logging
from collections import defaultdict
from typing import Any

from .models import Work, Author, Institution, Source, Topic, Publisher, Funder
from .neo4j_client import Neo4jClient
from .openalex_client import OpenAlexClient

logger = logging.getLogger(__name__)


class OpenAlexImporter:
    """Orchestrates import of OpenAlex data into Neo4j."""

    def __init__(self, neo4j_client: Neo4jClient, openalex_client: OpenAlexClient):
        """Initialize importer.

        Args:
            neo4j_client: Neo4j client instance
            openalex_client: OpenAlex client instance
        """
        self.neo4j = neo4j_client
        self.openalex = openalex_client

        # Storage for collected entities (deduplicated by ID)
        self.works: dict[str, Work] = {}
        self.authors: dict[str, Author] = {}
        self.institutions: dict[str, Institution] = {}
        self.sources: dict[str, Source] = {}
        self.topics: dict[str, Topic] = {}
        self.publishers: dict[str, Publisher] = {}
        self.funders: dict[str, Funder] = {}

    def import_from_query(
        self,
        query: str,
        limit: int = 100,
        expand_depth: int = 1
    ) -> dict[str, int]:
        """Import data starting from a search query.

        Args:
            query: Search query string
            limit: Maximum number of initial works to fetch
            expand_depth: How many levels to expand relationships
                1 = Direct relationships only
                2 = Include citations of citations, etc.

        Returns:
            Dictionary with counts of imported entities
        """
        logger.info(f"Starting import: query='{query}', limit={limit}, depth={expand_depth}")

        # Step 1: Search for initial works
        initial_works = self.openalex.search_works(query, limit)
        self._add_works(initial_works)

        # Step 2: Expand to related entities
        for depth in range(1, expand_depth + 1):
            logger.info(f"Expanding relationships at depth {depth}")
            self._expand_relationships()

        # Step 3: Create constraints and indexes in Neo4j
        self.neo4j.create_constraints()
        self.neo4j.create_indexes()

        # Step 4: Import nodes
        logger.info("Importing nodes to Neo4j")
        node_counts = self._import_nodes()

        # Step 5: Import relationships
        logger.info("Importing relationships to Neo4j")
        rel_counts = self._import_relationships()

        # Combine and return counts
        counts = {**node_counts, **rel_counts}
        logger.info(f"Import complete: {counts}")
        return counts

    def _add_works(self, works: list[Work]) -> None:
        """Add works to collection (deduplicates by ID)."""
        for work in works:
            if work.id not in self.works:
                self.works[work.id] = work

    def _expand_relationships(self) -> None:
        """Fetch and add all related entities for collected works."""
        # Collect all IDs we need to fetch
        author_ids = set()
        institution_ids = set()
        source_ids = set()
        topic_ids = set()
        funder_ids = set()
        referenced_work_ids = set()

        for work in self.works.values():
            author_ids.update(work.author_ids)
            institution_ids.update(work.institution_ids)
            if work.source_id:
                source_ids.add(work.source_id)
            topic_ids.update(work.topic_ids)
            funder_ids.update(work.funder_ids)
            referenced_work_ids.update(work.referenced_work_ids)

        # Remove IDs we already have
        author_ids -= self.authors.keys()
        institution_ids -= self.institutions.keys()
        source_ids -= self.sources.keys()
        topic_ids -= self.topics.keys()
        funder_ids -= self.funders.keys()
        referenced_work_ids -= self.works.keys()

        # Fetch authors
        if author_ids:
            authors = self.openalex.fetch_authors_by_ids(list(author_ids))
            for author in authors:
                self.authors[author.id] = author

        # Fetch institutions
        if institution_ids:
            institutions = self.openalex.fetch_institutions_by_ids(list(institution_ids))
            for inst in institutions:
                self.institutions[inst.id] = inst

        # Fetch sources
        if source_ids:
            sources = self.openalex.fetch_sources_by_ids(list(source_ids))
            for source in sources:
                self.sources[source.id] = source

                # Track publisher IDs from sources
                if source.publisher_id and source.publisher_id not in self.publishers:
                    self.publishers[source.publisher_id] = None  # Placeholder

        # Fetch topics
        if topic_ids:
            topics = self.openalex.fetch_topics_by_ids(list(topic_ids))
            for topic in topics:
                self.topics[topic.id] = topic

        # Fetch funders
        if funder_ids:
            funders = self.openalex.fetch_funders_by_ids(list(funder_ids))
            for funder in funders:
                self.funders[funder.id] = funder

        # Fetch referenced works (citations)
        if referenced_work_ids:
            works = self.openalex.fetch_works_by_ids(list(referenced_work_ids))
            self._add_works(works)

        # Fetch publishers (for sources)
        publisher_ids = [pid for pid, pub in self.publishers.items() if pub is None]
        if publisher_ids:
            publishers = self.openalex.fetch_publishers_by_ids(publisher_ids)
            for pub in publishers:
                self.publishers[pub.id] = pub

    def _import_nodes(self) -> dict[str, int]:
        """Import all collected nodes to Neo4j.

        Returns:
            Dictionary with node counts
        """
        counts = {}

        # Works
        if self.works:
            work_nodes = [w.to_node_dict() for w in self.works.values()]
            counts["works"] = self.neo4j.batch_create_nodes("Work", work_nodes)

        # Authors
        if self.authors:
            author_nodes = [a.to_node_dict() for a in self.authors.values()]
            counts["authors"] = self.neo4j.batch_create_nodes("Author", author_nodes)

        # Institutions
        if self.institutions:
            inst_nodes = [i.to_node_dict() for i in self.institutions.values()]
            counts["institutions"] = self.neo4j.batch_create_nodes("Institution", inst_nodes)

        # Sources
        if self.sources:
            source_nodes = [s.to_node_dict() for s in self.sources.values()]
            counts["sources"] = self.neo4j.batch_create_nodes("Source", source_nodes)

        # Topics
        if self.topics:
            topic_nodes = [t.to_node_dict() for t in self.topics.values()]
            counts["topics"] = self.neo4j.batch_create_nodes("Topic", topic_nodes)

        # Publishers
        if self.publishers:
            pub_nodes = [
                p.to_node_dict() for p in self.publishers.values()
                if p is not None  # Filter out placeholders
            ]
            if pub_nodes:
                counts["publishers"] = self.neo4j.batch_create_nodes("Publisher", pub_nodes)

        # Funders
        if self.funders:
            funder_nodes = [f.to_node_dict() for f in self.funders.values()]
            counts["funders"] = self.neo4j.batch_create_nodes("Funder", funder_nodes)

        return counts

    def _import_relationships(self) -> dict[str, int]:
        """Import all relationships to Neo4j.

        Returns:
            Dictionary with relationship counts
        """
        counts = {}

        # AUTHORED relationships (Author -> Work)
        authored_rels = []
        for work in self.works.values():
            for author_id in work.author_ids:
                if author_id in self.authors:
                    authored_rels.append({
                        "source_id": author_id,
                        "target_id": work.id,
                    })

        if authored_rels:
            counts["authored"] = self.neo4j.batch_create_relationships(
                "AUTHORED", "Author", "Work", authored_rels
            )

        # AFFILIATED_WITH relationships (Author -> Institution)
        # Note: We get these from works' authorship data
        affiliated_rels = []
        for work in self.works.values():
            for author_id in work.author_ids:
                for inst_id in work.institution_ids:
                    if author_id in self.authors and inst_id in self.institutions:
                        affiliated_rels.append({
                            "source_id": author_id,
                            "target_id": inst_id,
                        })

        if affiliated_rels:
            # Deduplicate affiliations
            unique_rels = {
                (rel["source_id"], rel["target_id"]): rel
                for rel in affiliated_rels
            }
            counts["affiliated_with"] = self.neo4j.batch_create_relationships(
                "AFFILIATED_WITH", "Author", "Institution", list(unique_rels.values())
            )

        # PUBLISHED_IN relationships (Work -> Source)
        published_rels = []
        for work in self.works.values():
            if work.source_id and work.source_id in self.sources:
                published_rels.append({
                    "source_id": work.id,
                    "target_id": work.source_id,
                })

        if published_rels:
            counts["published_in"] = self.neo4j.batch_create_relationships(
                "PUBLISHED_IN", "Work", "Source", published_rels
            )

        # CITES relationships (Work -> Work)
        cites_rels = []
        for work in self.works.values():
            for ref_id in work.referenced_work_ids:
                if ref_id in self.works:
                    cites_rels.append({
                        "source_id": work.id,
                        "target_id": ref_id,
                    })

        if cites_rels:
            counts["cites"] = self.neo4j.batch_create_relationships(
                "CITES", "Work", "Work", cites_rels
            )

        # HAS_TOPIC relationships (Work -> Topic)
        topic_rels = []
        for work in self.works.values():
            for topic_id in work.topic_ids:
                if topic_id in self.topics:
                    topic_rels.append({
                        "source_id": work.id,
                        "target_id": topic_id,
                    })

        if topic_rels:
            counts["has_topic"] = self.neo4j.batch_create_relationships(
                "HAS_TOPIC", "Work", "Topic", topic_rels
            )

        # FUNDED_BY relationships (Work -> Funder)
        funded_rels = []
        for work in self.works.values():
            for funder_id in work.funder_ids:
                if funder_id in self.funders:
                    funded_rels.append({
                        "source_id": work.id,
                        "target_id": funder_id,
                    })

        if funded_rels:
            counts["funded_by"] = self.neo4j.batch_create_relationships(
                "FUNDED_BY", "Work", "Funder", funded_rels
            )

        # PUBLISHED_BY relationships (Source -> Publisher)
        publisher_rels = []
        for source in self.sources.values():
            if source.publisher_id and source.publisher_id in self.publishers:
                publisher_rels.append({
                    "source_id": source.id,
                    "target_id": source.publisher_id,
                })

        if publisher_rels:
            counts["published_by"] = self.neo4j.batch_create_relationships(
                "PUBLISHED_BY", "Source", "Publisher", publisher_rels
            )

        return counts
