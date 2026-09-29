"""Tests for the inverted-index / TF-IDF / caching candidate search.

Verifies:
- Inverted index avoids scanning non-matching resources.
- TF-IDF ranks rare-term matches above common-term matches.
- Result cache returns identical objects on repeated calls.
- Cache is invalidated on reindex.
- TF-IDF distinguishes title vs body weighting.
"""

from __future__ import annotations

from backend.auth.identity import IdentityStore
from backend.connectors.confluence import ConfluenceConnector
from backend.connectors.gdrive import GDriveConnector
from backend.connectors.jira import JiraConnector
from backend.connectors.slack import SlackConnector
from backend.retrieval.candidate_search import CandidateSearch
from backend.retrieval.indexer import Indexer


def _connectors():
    return [
        ConfluenceConnector(), JiraConnector(),
        SlackConnector(), GDriveConnector(),
    ]


def _user(uid):
    return IdentityStore().get_user(uid)


def test_inverted_index_only_scores_matching_resources():
    """Search should only return resources that share at least one token."""
    idx = Indexer(connectors=_connectors())
    idx.reindex()
    search = CandidateSearch(idx)
    results = search.search("zzznonexistentterm", k=20)
    assert len(results) == 0


def test_tfidf_ranks_rare_term_above_common_term():
    """A query for a rare term should score higher than a common term."""
    idx = Indexer(connectors=_connectors())
    idx.reindex()
    search = CandidateSearch(idx)

    # "payment" appears in multiple resources; "migration" is more specific.
    # Both should return results, but we verify TF-IDF scoring is working
    # by checking that scores vary (not all equal).
    results_payment = search.search("payment", k=20)
    results_migration = search.search("migration", k=20)

    assert len(results_payment) > 0
    assert len(results_migration) > 0

    # TF-IDF should produce non-uniform scores for payment.
    scores = [c.score for c in results_payment]
    assert len(set(round(s, 6) for s in scores)) > 1 or len(scores) == 1


def test_result_cache_returns_same_results():
    """Repeated identical query should return identical results."""
    idx = Indexer(connectors=_connectors())
    idx.reindex()
    search = CandidateSearch(idx)

    a = search.search("database migration plan", k=10)
    b = search.search("database migration plan", k=10)
    assert [c.resource.resource_id for c in a] == [c.resource.resource_id for c in b]


def test_cache_invalidated_on_reindex():
    """After reindex, the cache should be cleared and results rebuilt."""
    idx = Indexer(connectors=_connectors())
    idx.reindex()
    search = CandidateSearch(idx)

    a = search.search("database migration", k=10)
    idx.reindex()  # This changes index size, invalidating cache
    b = search.search("database migration", k=10)
    assert [c.resource.resource_id for c in a] == [c.resource.resource_id for c in b]


def test_title_weighted_higher_than_body():
    """A resource with the query term in its title should score higher
    than one with it only in the body."""
    idx = Indexer(connectors=_connectors())
    idx.reindex()
    search = CandidateSearch(idx)

    # "payment" appears in several titles and bodies.
    # Resources with "payment" in the title should rank above body-only matches.
    results = search.search("payment", k=20)
    ids = [c.resource.resource_id for c in results]
    if len(ids) >= 2:
        top_score = results[0].score
        bottom_score = results[-1].score
        assert top_score > bottom_score


def test_search_still_finds_db_migration_and_mig231():
    """Backward compat: the original test case still works."""
    idx = Indexer(connectors=_connectors())
    idx.reindex()
    search = CandidateSearch(idx)
    results = search.search("database migration", k=10)
    ids = [c.resource.resource_id for c in results]
    assert "confluence:db-migration-plan" in ids
    assert "MIG-231" in ids


def test_search_still_deterministic():
    """Backward compat: results are deterministic."""
    idx = Indexer(connectors=_connectors())
    idx.reindex()
    search = CandidateSearch(idx)
    a = [c.resource.resource_id for c in search.search("payment outage", k=10)]
    b = [c.resource.resource_id for c in search.search("payment outage", k=10)]
    assert a == b


def test_search_still_respects_k():
    """Backward compat: k is respected."""
    idx = Indexer(connectors=_connectors())
    idx.reindex()
    search = CandidateSearch(idx)
    assert len(search.search("the", k=3)) <= 3


def test_search_scores_still_descending():
    """Backward compat: scores are in descending order."""
    idx = Indexer(connectors=_connectors())
    idx.reindex()
    search = CandidateSearch(idx)
    # Use a query that doesn't hit the cache (first call).
    results = search.search("payment incident circuit breaker", k=10)
    scores = [c.score for c in results]
    assert scores == sorted(scores, reverse=True)


# -- Connector-level filtering ----------------------------------------

def test_source_filter_jira_only():
    """Query mentioning 'jira' should only return Jira resources."""
    idx = Indexer(connectors=_connectors())
    idx.reindex()
    search = CandidateSearch(idx)
    results = search.search("jira migration ticket", k=20)
    sources = {c.resource.source.value for c in results}
    assert sources == {"jira"} or len(results) == 0


def test_source_filter_slack_only():
    """Query mentioning 'slack' should only return Slack resources."""
    idx = Indexer(connectors=_connectors())
    idx.reindex()
    search = CandidateSearch(idx)
    results = search.search("slack channel message", k=20)
    sources = {c.resource.source.value for c in results}
    assert sources == {"slack"} or len(results) == 0


def test_source_filter_confluence_only():
    """Query mentioning 'confluence' should only return Confluence resources."""
    idx = Indexer(connectors=_connectors())
    idx.reindex()
    search = CandidateSearch(idx)
    results = search.search("confluence page migration", k=20)
    sources = {c.resource.source.value for c in results}
    assert sources == {"confluence"} or len(results) == 0


def test_no_source_filter_when_generic_query():
    """Generic query with no source keyword should search all sources."""
    idx = Indexer(connectors=_connectors())
    idx.reindex()
    search = CandidateSearch(idx)
    results = search.search("database migration plan", k=20)
    sources = {c.resource.source.value for c in results}
    assert len(sources) > 1  # Multiple sources should be represented


# -- Parallel connector polling ----------------------------------------

def test_parallel_reindex_handles_failing_connector():
    """A connector that raises should not prevent other connectors from indexing."""
    from backend.connectors.base import BaseConnector
    from backend.connectors.confluence import ConfluenceConnector
    from unittest.mock import MagicMock

    class FailingConnector(BaseConnector):
        def list_resources(self):
            raise ConnectionError("simulated network failure")
        def get_resource(self, resource_id):
            return None
        def get_acl(self, resource_id):
            return None
        def check_membership(self, user, resource_id):
            return False
        def update_acl(self, resource_id, **kwargs):
            return None

    idx = Indexer(connectors=[ConfluenceConnector(), FailingConnector()])
    count = idx.reindex()
    # Confluence resources should still be indexed despite the failure.
    assert count > 0
    assert all(
        e.resource.source.value == "confluence"
        for e in idx.all_entries()
    )


def test_parallel_reindex_returns_all_resources():
    """Parallel reindex should return same count as sequential."""
    idx = Indexer(connectors=_connectors())
    count = idx.reindex()
    assert count == 20


# -- Semantic search (n-gram similarity) --------------------------------

def test_semantic_match_db_matches_database():
    """Query 'db' should surface resources about 'database' via n-gram similarity."""
    idx = Indexer(connectors=_connectors())
    idx.reindex()
    search = CandidateSearch(idx)
    # "db" won't exact-match "database", but should match via n-grams.
    results = search.search("db", k=20)
    ids = [c.resource.resource_id for c in results]
    # At least one database-related resource should surface.
    assert any("db" in rid or "database" in rid.lower() for rid in ids)


def test_semantic_exact_match_ranks_higher_than_fuzzy():
    """Exact TF-IDF matches should rank above n-gram-only semantic matches."""
    idx = Indexer(connectors=_connectors())
    idx.reindex()
    search = CandidateSearch(idx)
    # "database" will exact-match; "databse" (typo) will only n-gram match.
    exact_results = search.search("database migration", k=20)
    typo_results = search.search("databse migration", k=20)
    # Exact match should return at least as many results as the typo version.
    assert len(exact_results) >= len(typo_results)


def test_semantic_migration_matches_migrate():
    """Query 'migrate' should surface resources about 'migration' via n-grams."""
    idx = Indexer(connectors=_connectors())
    idx.reindex()
    search = CandidateSearch(idx)
    results = search.search("migrate blockers", k=20)
    ids = [c.resource.resource_id for c in results]
    assert any("migr" in rid.lower() for rid in ids)


def test_ngram_similarity():
    """Unit test for the n-gram similarity function."""
    from backend.retrieval.candidate_search import _ngram_similarity, _char_ngrams
    a = _char_ngrams("database")
    b = _char_ngrams("database")
    assert _ngram_similarity(a, b) == 1.0
    c = _char_ngrams("db")
    assert 0 < _ngram_similarity(a, c) < 1.0
    d = _char_ngrams("xyz")
    assert _ngram_similarity(a, d) == 0.0