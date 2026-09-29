"""Resource indexer.

Pulls resources from all registered connectors and holds them in an
in-memory index keyed by resource_id. Each indexed entry records the
ACL version observed at index time (`indexed_acl_version`) so the
retrieval pipeline can later detect staleness via the freshness checker
(supports INV3: RevokedAccessNotReusable).

The index is a snapshot for *candidate search only*. Authorization is
NEVER decided from the index — the permission filter re-fetches the live
ACL from the owning connector at query time. This separation is what makes
over-fetching safe: a stale index can surface a candidate, but it can never
grant access to it.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field

from backend.connectors.base import BaseConnector
from backend.models import Resource, Source


@dataclass
class IndexEntry:
    """A single indexed resource plus the connector that owns it.

    Attributes:
        resource: The resource as observed at index time (snapshot).
        connector: The owning connector, used to re-fetch the live ACL.
        indexed_acl_version: ACL version at index time, for freshness checks.
    """

    resource: Resource
    connector: BaseConnector
    indexed_acl_version: int


@dataclass
class Indexer:
    """In-memory index over one or more source connectors.

    Usage:
        indexer = Indexer(connectors=[ConfluenceConnector(), ...])
        indexer.reindex()
        entries = indexer.all_entries()
    """

    connectors: list[BaseConnector] = field(default_factory=list)
    _entries: dict[str, IndexEntry] = field(default_factory=dict, init=False)

    def add_connector(self, connector: BaseConnector) -> None:
        """Register a connector to be included on the next reindex."""
        self.connectors.append(connector)

    def reindex(self) -> int:
        """Rebuild the index from all registered connectors.

        Connectors are polled in parallel via a thread pool, so network
        latency from multiple sources overlaps rather than stacks.

        Returns the number of indexed resources. If two connectors expose
        the same resource_id, the later connector wins (connectors are
        expected to use source-prefixed IDs, so collisions are not expected).
        """
        entries: dict[str, IndexEntry] = {}

        # Poll all connectors in parallel.
        results: list[tuple[BaseConnector, list[Resource]]] = []
        if self.connectors:
            with ThreadPoolExecutor(max_workers=len(self.connectors)) as pool:
                futures = {
                    pool.submit(connector.list_resources): connector
                    for connector in self.connectors
                }
                for future in futures:
                    connector = futures[future]
                    try:
                        resources = future.result()
                    except Exception:
                        # A failed connector contributes no resources but
                        # does not prevent other connectors from indexing.
                        resources = []
                    results.append((connector, resources))

        for connector, resources in results:
            for resource in resources:
                entries[resource.resource_id] = IndexEntry(
                    resource=resource,
                    connector=connector,
                    indexed_acl_version=resource.acl.acl_version,
                )
        self._entries = entries
        return len(self._entries)

    def all_entries(self) -> list[IndexEntry]:
        """Return all indexed entries."""
        return list(self._entries.values())

    def all_resources(self) -> list[Resource]:
        """Return all indexed resources (snapshot)."""
        return [e.resource for e in self._entries.values()]

    def get(self, resource_id: str) -> IndexEntry | None:
        """Return the index entry for a resource_id, or None."""
        return self._entries.get(resource_id)

    def size(self) -> int:
        """Return the number of indexed resources."""
        return len(self._entries)

    def by_source(self, source: Source) -> list[IndexEntry]:
        """Return indexed entries from a given source platform."""
        return [e for e in self._entries.values() if e.resource.source == source]
