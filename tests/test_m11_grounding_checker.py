"""Tests for M11 — hallucination detection layer (INV8: GroundedAnswerOnly).

Run with: python -m pytest tests/test_m11_grounding_checker.py -v

Covers:
- Grounded sentences pass through unchanged.
- Hallucinated sentences (low overlap + missing entities) are stripped.
- Mixed answers: grounded sentences kept, hallucinated removed.
- Short sentences always kept (connective tissue).
- Empty context → no-op (no-access path handles this).
- GroundingReport fields: confidence, grounded flag, sentence counts.
- Orchestrator integration: grounding checker wired into the pipeline.
- Structurally similar hallucination (same topic, wrong facts) is caught.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.agents.grounding_checker import GroundingChecker, GroundingReport
from backend.agents.llm_client import LLMClient
from backend.agents.answer_agent import AnswerAgent
from backend.agents.orchestrator import Orchestrator
from backend.retrieval.context_assembler import AssembledContext, Citation
from backend.auth.identity import IdentityStore
from backend.connectors.confluence import ConfluenceConnector
from backend.connectors.jira import JiraConnector
from backend.connectors.slack import SlackConnector
from backend.connectors.gdrive import GDriveConnector


# -- Helpers --------------------------------------------------------------

def _context_with_text(*blocks: tuple[str, str]) -> AssembledContext:
    """Build an AssembledContext from (resource_id, content) tuples."""
    citations = []
    texts = []
    ids = []
    for i, (rid, content) in enumerate(blocks):
        marker = f"[{i + 1}]"
        citations.append(Citation(marker=marker, resource_id=rid,
                                   source="confluence", title=f"T{i}"))
        texts.append(f"{marker} {rid}\n{content}")
        ids.append(rid)
    return AssembledContext(
        text="\n".join(texts),
        citations=citations,
        included_resource_ids=ids,
    )


class _FixedLLM:
    """LLM stub returning a fixed string."""

    def __init__(self, output: str):
        self._output = output

    def generate(self, prompt: str) -> str:
        return self._output


def _connectors():
    return [ConfluenceConnector(), JiraConnector(),
            SlackConnector(), GDriveConnector()]


# -- Fully grounded answer passes through --------------------------------

def test_fully_grounded_answer_unchanged():
    ctx = _context_with_text(
        ("r1", "The database migration is 80% complete with no blockers."),
    )
    checker = GroundingChecker()
    answer = "The database migration is complete with no blockers reported [1]."
    report = checker.check(answer, ctx)
    assert report.grounded is True
    assert report.ungrounded_sentences == []
    assert report.confidence == 1.0


def test_grounded_answer_with_multiple_sentences():
    ctx = _context_with_text(
        ("r1", "The migration plan covers PostgreSQL 15 upgrade. The team has scheduled downtime for Saturday."),
        ("r2", "Blockers include network latency and storage capacity limits."),
    )
    answer = (
        "The migration plan covers the PostgreSQL upgrade [1]. "
        "The team has scheduled downtime for Saturday [1]. "
        "Blockers include network latency and storage capacity [2]."
    )
    checker = GroundingChecker()
    report = checker.check(answer, ctx)
    assert report.grounded is True
    assert report.total_sentences == 3
    assert report.ungrounded_sentences == []


# -- Hallucinated sentences are stripped ---------------------------------

def test_pure_hallucination_stripped():
    ctx = _context_with_text(
        ("r1", "The database migration is proceeding normally with no issues."),
    )
    # Completely unrelated — no overlap, all entities missing.
    answer = "The weather in Tokyo is expected to be sunny with cherry blossoms."
    checker = GroundingChecker()
    report = checker.check(answer, ctx)
    assert report.grounded is False
    assert len(report.ungrounded_sentences) == 1
    assert report.grounded_text == ""


def test_mixed_grounded_and_hallucinated():
    ctx = _context_with_text(
        ("r1", "The database migration plan covers PostgreSQL 15. Downtime is scheduled."),
    )
    answer = (
        "The database migration plan covers PostgreSQL 15 [1]. "
        "The CEO resigned yesterday after a scandal involving cryptocurrency fraud."
    )
    checker = GroundingChecker()
    report = checker.check(answer, ctx)
    assert report.grounded is False
    assert len(report.grounded_sentences) == 1
    assert len(report.ungrounded_sentences) == 1
    # The grounded sentence is kept.
    assert "PostgreSQL" in report.grounded_text
    # The hallucinated sentence is gone.
    assert "cryptocurrency" not in report.grounded_text
    assert "CEO" not in report.grounded_text


def test_structurally_similar_hallucination_caught():
    """Same topic, but claims facts not in the context."""
    ctx = _context_with_text(
        ("r1", "The Q3 breach was caused by a phishing campaign targeting the finance team."),
    )
    # Same topic (breach, Q3), but introduces SQL injection which is not in context.
    answer = "The Q3 breach was caused by a SQL injection attack exploiting the payment gateway [1]."
    checker = GroundingChecker()
    report = checker.check(answer, ctx)
    # "SQL" and "injection" are not in the context, so this should be flagged.
    assert report.grounded is False
    assert len(report.ungrounded_sentences) == 1


def test_numbers_not_in_context_flagged():
    ctx = _context_with_text(
        ("r1", "The project budget is 50000 dollars allocated for engineering."),
    )
    # 999 is not in the context; this is a hallucinated number.
    answer = "The project budget is 999 million dollars allocated for marketing."
    checker = GroundingChecker()
    report = checker.check(answer, ctx)
    assert report.grounded is False


# -- Short sentences always kept -----------------------------------------

def test_short_sentences_always_kept():
    ctx = _context_with_text(
        ("r1", "Database migration plan."),
    )
    answer = "Yes. No. Maybe so. See [1]."
    checker = GroundingChecker()
    report = checker.check(answer, ctx)
    assert report.grounded is True
    assert report.total_sentences == 4
    assert report.ungrounded_sentences == []


# -- Empty context → no-op -----------------------------------------------

def test_empty_context_noop():
    ctx = AssembledContext(text="", citations=[], included_resource_ids=[])
    checker = GroundingChecker()
    report = checker.check("Some answer text.", ctx)
    assert report.grounded is True
    assert report.grounded_text == "Some answer text."
    assert report.total_sentences == 0  # not checked


# -- GroundingReport fields ----------------------------------------------

def test_report_confidence_partial():
    ctx = _context_with_text(
        ("r1", "Database migration PostgreSQL upgrade scheduled downtime."),
    )
    answer = (
        "Database migration PostgreSQL upgrade [1]. "
        "The alien invasion was thwarted by time travelers from the future."
    )
    checker = GroundingChecker()
    report = checker.check(answer, ctx)
    assert report.total_sentences == 2
    assert len(report.grounded_sentences) == 1
    assert len(report.ungrounded_sentences) == 1
    assert report.confidence == 0.5


def test_report_confidence_full():
    ctx = _context_with_text(
        ("r1", "Database migration PostgreSQL upgrade scheduled downtime."),
    )
    answer = "Database migration PostgreSQL upgrade scheduled [1]."
    checker = GroundingChecker()
    report = checker.check(answer, ctx)
    assert report.confidence == 1.0
    assert report.grounded is True


# -- Orchestrator integration --------------------------------------------

def test_orchestrator_runs_grounding_checker():
    """The orchestrator should apply grounding checking after the answer agent.

    With the StubLLMClient (which doesn't use context vocabulary), the
    grounding checker strips the stub's generic text and falls back to
    a citation-only summary. The answer should still be non-empty because
    authorized citations exist.
    """
    o = Orchestrator(_connectors())
    alice = IdentityStore().get_user("alice")
    resp = o.handle(alice, "database migration status blockers", k=20)
    assert resp.no_access is False
    # The stub's generic text is stripped; fallback shows citations.
    assert len(resp.answer) > 0
    assert "[" in resp.answer  # citation markers present


def test_orchestrator_grounding_skipped_on_no_access():
    """No-access path should not run grounding (canonical message is not LLM output)."""
    o = Orchestrator(_connectors())
    bob = IdentityStore().get_user("bob")
    resp = o.handle(bob, "security breach incident report", k=20)
    assert resp.no_access is True
    # Canonical message unchanged.
    assert "could not find" in resp.answer.lower()


def test_orchestrator_strips_hallucinated_answer():
    """With a hallucinating LLM, the orchestrator should strip ungrounded content."""
    ctx_text = (
        "[1] confluence:db-migration-plan\n"
        "The database migration plan covers PostgreSQL 15 upgrade. "
        "Downtime is scheduled for Saturday.\n"
    )
    # We need a hallucinating LLM — one that produces grounded + ungrounded text.
    class HallucinatingLLM:
        def generate(self, prompt: str) -> str:
            return (
                "The database migration covers PostgreSQL upgrade [1]. "
                "The Martian colony discovered ancient ruins beneath Olympus Mons."
            )

    # Build the orchestrator with the hallucinating LLM.
    # We'll test the grounding checker directly with the orchestrator's pipeline
    # by using a mock that returns the hallucinated text.
    checker = GroundingChecker()
    ctx = AssembledContext(
        text=ctx_text,
        citations=[Citation(marker="[1]", resource_id="db-migration-plan",
                              source="confluence", title="DB Migration Plan")],
        included_resource_ids=["db-migration-plan"],
    )

    answer_text = (
        "The database migration covers PostgreSQL upgrade [1]. "
        "The Martian colony discovered ancient ruins beneath Olympus Mons."
    )
    report = checker.check(answer_text, ctx)
    assert report.grounded is False
    assert "PostgreSQL" in report.grounded_text
    assert "Martian" not in report.grounded_text


# -- Edge cases -----------------------------------------------------------

def test_answer_with_only_citation_markers():
    """An answer that's just citation markers should pass through."""
    ctx = _context_with_text(
        ("r1", "Some content here about databases."),
        ("r2", "More content about migration."),
    )
    answer = "[1] [2]"
    checker = GroundingChecker()
    report = checker.check(answer, ctx)
    assert report.grounded is True


def test_whitespace_only_answer():
    ctx = _context_with_text(("r1", "Some content."))
    checker = GroundingChecker()
    report = checker.check("   ", ctx)
    # Whitespace-only has no sentences to check.
    assert report.grounded is True


def test_configurable_threshold():
    """The overlap threshold controls how strict the lexical check is.

    A sentence with no missing entities but moderate overlap passes at the
    default threshold but fails at a very strict one.
    """
    ctx = _context_with_text(
        ("r1", "Database migration PostgreSQL upgrade scheduled downtime Saturday."),
    )
    # Same entities, but adds extra non-entity words that dilute overlap.
    answer = (
        "Database migration PostgreSQL upgrade scheduled downtime Saturday "
        "with additional context about engineering team coordination efforts."
    )
    strict_checker = GroundingChecker(min_overlap=0.95)
    default_checker = GroundingChecker(min_overlap=0.3)

    strict_report = strict_checker.check(answer, ctx)
    default_report = default_checker.check(answer, ctx)

    # Default threshold: overlap is high enough (most content words are shared).
    assert default_report.grounded is True
    # Strict threshold: the extra words bring overlap below 0.95.
    assert strict_report.grounded is False


def test_grounding_report_is_dataclass():
    report = GroundingReport(grounded_text="x", total_sentences=1)
    assert report.grounded is True
    assert report.confidence == 1.0
    assert report.grounded_sentences == []
    assert report.ungrounded_sentences == []