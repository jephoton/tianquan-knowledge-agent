# Design — Retrieval Pipeline and Invariant Enforcement

<!-- Generated implementation reconciliation, 2026-10-11. -->

## Actual query sequence

1. Query scanner flags suspicious input for audit; it does not block access.
2. Candidate search ranks indexed content across sources, boosting named platforms. Exact Q-number tokens constrain labelled report requests.
3. Permission filter fetches each connector ACL and calls the policy engine. It returns both allowed candidates and all policy decisions.
4. Context assembler bounds allowed indexed content (8,000 characters by default) and assigns citation markers.
5. Orchestrator appends all allow/deny decisions, with the question, before answer generation.
6. Answer agent returns the canonical no-access message for empty context, otherwise asks ADP/stub for a cited answer and validates citation markers. Live-call failures use the extractive stub.
7. Lexical grounding checks can remove sentences. If every sentence is rejected, the orchestrator retains the original citation-validated answer; this is not strict semantic grounding.
8. Orchestrator audits the exact served answer and citation mapping, then the API hides denial details from non-auditors.

## Invariant mapping and limits

| ID | Implementation location | Assurance scope |
|---|---|---|
| INV1 RetrievedOnlyIfAuthorized | PermissionFilter | Allowed candidates only; missing live ACL currently falls back to snapshot |
| INV2 LLMSeesOnlyRetrievedContent | Filter + ContextAssembler | Prompt receives assembled allowed sources; keep ADP knowledge base empty |
| INV3 RevokedAccessNotReusable | Filter live ACL fetch | Supported connector revoke affects next query without reindex; no proof of all Python schedules |
| INV4 EveryDecisionAudited | Orchestrator | Policy decisions appended before generation; answer also logged |
| INV5 NoPrivilegeEscalation | Deferred | Action delegation removed from scope |
| INV6 NoUnauthorizedCitation | AnswerAgent | Removes citation markers absent from authorized context; not factual entailment |
| INV7 NoMetadataLeakOnDeny | AnswerAgent/API | Canonical no-access/no-match text; denied metadata withheld from non-auditors |
| INV8 GroundedAnswerOnly | GroundingChecker/Orchestrator | Lexical heuristic with all-rejected fallback; Python-only, not TLA+ |

TLA+ checks six active invariants in a finite abstract model, independently of the Python tests. See [formal boundary](../architecture.md#8-formal-model-boundary).

## Policy gates

`PolicyEngine.decide(user, resource, action)` applies deny-list override, source-specific rules, sensitivity clearance and role/action permission, in that order. The generic unknown-source path requires an explicit user or role grant; it does not default to allow. The engine evaluates the resource passed to it; **the filter**, rather than the engine, fetches the ACL.

The index supplies content and an ACL-version snapshot. For supported connector resources, the current ACL replaces the snapshot before policy evaluation; freshness compares versions for observability. Content is refreshed by reindexing, not each query. If `connector.get_acl()` returns `None`, the filter currently returns the indexed resource and the engine may permit it. Future connector failure/deletion handling needs an explicit deny and regression coverage. This documented gap must not be described as fail-closed retrieval.

The [current-state limitations](../current-state.md#known-boundaries-and-follow-ups) also cover concurrency, restart persistence, demo identity and grounding. Deployment is [planned only](../superpowers/plans/2026-10-11-cloud-demo-deployment.md).
