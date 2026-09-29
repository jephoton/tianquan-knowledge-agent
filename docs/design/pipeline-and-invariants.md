# Design — Retrieval Pipeline & Invariant Enforcement

> **Last updated:** 2026-09-29

## Pipeline overview

```
user + query
  │
  ▼
1. CandidateSearch.search(query, k)        ← over-fetches (recall > precision)
  │    returns list[ScoredCandidate]
  ▼
2. PermissionFilter.filter(user, candidates)  ← the enforcement gate
  │    re-fetches LIVE ACL per candidate
  │    runs PolicyEngine.decide() on each
  │    records allow AND deny decisions
  │    returns FilterOutcome { allowed, decisions }
  ▼
3. ContextAssembler.assemble(outcome.allowed) ← builds LLM context
  │    bounded to max_chars (8000 default)
  │    assigns citation markers [1], [2], ...
  │    returns AssembledContext { text, citations, included_resource_ids }
  ▼
4. AnswerAgent.answer(query, context)         ← LLM generates answer
  │    strips unauthorized citations (INV6)
  │    no-leak message on empty context (INV7)
  ▼
5. GroundingChecker.check(answer, context)    ← strips hallucinations (INV8)
  │    lexical overlap + entity extraction
  ▼
6. Orchestrator audits every decision (INV4)
```

## Where each invariant is enforced

| INV | Name | Enforcement point | How |
|-----|------|-------------------|-----|
| INV1 | RetrievedOnlyIfAuthorized | PermissionFilter | Only `allowed` candidates reach the assembler |
| INV2 | LLMSeesOnlyRetrievedContent | PermissionFilter (before context) | Filtering happens before assembly, not after |
| INV3 | RevokedAccessNotReusable | PermissionFilter + FreshnessChecker | Live ACL re-fetch; freshness check flags stale snapshots |
| INV4 | EveryDecisionAudited | Orchestrator | `append_decisions(all)` before answer generation |
| INV5 | NoPrivilegeEscalation | Deferred | Action agent removed from roadmap |
| INV6 | NoUnauthorizedCitation | AnswerAgent._validate_citations | Strips `[N]` markers not backed by context |
| INV7 | NoMetadataLeakOnDeny | AnswerAgent.answer | Canonical message on empty context; identical to "not found" |
| INV8 | GroundedAnswerOnly | GroundingChecker.check | Post-LLM sentence-level grounding verification |

## The 4 policy gates

`PolicyEngine.decide(user, resource, action)` runs 4 gates in order. If any
fails, the decision is DENY with the reason set to the failing gate:

1. **Deny-list override** — if `user.user_id in acl.denied_users` → immediate
   DENY (`explicit_deny_list`). Deny always wins.
2. **Source-specific rules** — `check_source_specific(user, resource)` applies
   native semantics (Confluence page restrictions, Jira issue security, Slack
   channel type, GDrive sharing).
3. **Sensitivity clearance** — `check_sensitivity_clearance(user, resource)`
   checks the `SENSITIVITY_CLEARANCE` matrix (e.g. only `security_team` /
   `compliance_officer` / `admin` can see `CONFIDENTIAL`).
4. **Action permission** — `check_action_permission(user, action)` checks
   whether the user's role permits the requested action (e.g. `contractor`
   can `read` but not `export`).

All 4 pass → ALLOW.

The engine is **stateless** — every call reads the live ACL from the
connector. No caching. This is critical for INV3.

## Why the index is not trusted for authorization

The `Indexer` snapshots resources (including their ACL at snapshot time) for
search. But authorization is **never** decided from the snapshot. The
`PermissionFilter` always calls `connector.get_acl(resource_id)` to get the
**live** ACL, then runs the policy engine on that.

The `indexed_acl_version` is only used by the `FreshnessChecker` to flag
staleness — it doesn't gate access. Even if the index is stale, the live ACL
is authoritative.

This means a revoke between indexing and query is honored without a reindex.