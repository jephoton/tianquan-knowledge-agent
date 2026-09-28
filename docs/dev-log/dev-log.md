# Development Log — VeriBrain

> **Purpose:** Track CodeBuddy / WorkBuddy / Miora usage throughout development. This is a **required submission deliverable** — the handbook requires a minimum of 3 screenshots or screen recordings of chat logs from CodeBuddy or WorkBuddy during the development process.
>
> **Rule:** Take a screenshot at the end of any significant CodeBuddy/WorkBuddy session. Don't wait until M13 — conversation history cannot be reconstructed retroactively.

## Entries

### 2026-09-27 — M0: Project bootstrap

- **Tool:** CodeBuddy
- **Task:** Read Track 4 (Aspire FinTech) challenge from handbook PDF. Analyzed the challenge requirements. Designed the VeriBrain project concept. Wrote formal plan, architecture, and ADRs. Scaffolded repo structure.
- **Summary:** Initial project planning session. Read the Aspire "Internal Brain" challenge. Compared user's original idea (formally constrained enterprise agents) against the track requirements. Refined scope to focus on permission-aware retrieval as the core, with formal methods as the differentiator. Created the handoff layer (`docs/`), roadmap with 13 milestones, 3 ADRs, and repo skeleton.
- **Screenshot captured:** Y — [Screenshot 2026-09-27 215926.png](Screenshot%202026-09-27%20215926.png)

---

### 2026-09-28 — M2: Policy engine + handoff-layer steering

- **Tool:** CodeBuddy
- **Task:** Onboarded to the repo via the handoff layer. Added a global-style steering rule for the persistent handoff layer + conventional-commit discipline. Committed and completed M2 (policy engine).
- **Summary:** Read the full handoff layer (plan, architecture, current-state, ADRs, dev-log) to understand VeriBrain. Created `.kiro/steering/handoff-layer.md` codifying the docs/ handoff structure and commit conventions. Found uncommitted M2 policy code (policy_engine, permission_mapping, freshness_checker) with no tests; verified it imports and matches the data model, wrote 22 positive/negative/freshness tests (all 55 tests pass), then committed engine and tests as separate atomic commits. Updated current-state.md and plan.md to mark M2 complete and set M3 (retrieval pipeline) as next.
- **Screenshot captured:** Y — [Screenshot 2026-09-28 100832.png](Screenshot%202026-09-28%20100832.png), [Screenshot 2026-09-28 100923.png](Screenshot%202026-09-28%20100923.png)

---

### 2026-09-28 — M3 planning: retrieval pipeline

- **Tool:** CodeBuddy
- **Task:** Committed the hackathon handbook as reference. Planned M3 (permission-aware retrieval pipeline).
- **Summary:** Reviewed connector interfaces to ground the plan. Wrote ADR-0004 choosing keyword/token-overlap candidate search over vector embeddings for V1 (small corpus, determinism, no external deps, filter is the real gate). Broke M3 into indexer → candidate_search → permission_filter → context_assembler + integration tests, with the filter re-fetching live ACLs so over-fetched candidates cannot leak revoked content. Recorded the task breakdown and integration-test plan (INV1/INV2, over-fetch safety, revocation, role differentiation) in current-state.md.
- **Screenshot captured:** N — capture at end of session.

---

### 2026-09-28 — M3: retrieval pipeline implementation

- **Tool:** CodeBuddy
- **Task:** Implemented the M3 permission-aware retrieval pipeline end to end.
- **Summary:** Built `indexer` (connector snapshot with ACL-version stamp), `candidate_search` (deterministic keyword/token-overlap, over-fetch), `permission_filter` (re-fetches live ACLs, runs the policy engine, records freshness, drops denied resources), `context_assembler` (bounded, citation-marked context with INV6 hook), and `pipeline` wiring the four. Verified the safety property manually: contractor Bob gets zero security-breach content while security-team Charlie sees the confidential report. Wrote 20 integration tests (INV1/INV2/INV3, over-fetch safety, revocation-after-indexing honored without reindex, contractor⊂engineer). Full suite: 75 passing. Marked M3 complete and outlined M4 (TLA+) in the handoff layer.
- **Screenshot captured:** N — capture at end of session.

---

### 2026-09-28 — M4: TLA+ formal specification

- **Tool:** CodeBuddy + TLA+ VS Code extension (TLC via bundled tla2tools.jar, Java 25)
- **Task:** Wrote and model-checked the TLA+ access-control specification.
- **Summary:** Modeled the query lifecycle (search → decide → retrieve → answer, with revocation) as a state machine in `access_control.tla`, parameterised by a `BROKEN` flag. Encoded INV1–INV4, INV6, INV7 (INV5 delegation deferred to M11). Built MC harness modules to supply the `Authorized` ACL function that a .cfg literal can't express. Ran TLC: `MC_safe` passes all invariants (28 states); `MC_broken` (filter-after-retrieval) produces an INV1 counterexample at depth 4 — an over-fetched, denied resource (r2) reaches alice's context. That's the Demo 5 payoff. Cleaned up TLC output artifacts and gitignored them. Marked M4 complete, outlined M5 (audit trail).
- **Screenshot captured:** N — capture at end of session (TLC output worth capturing for the demo).

---

### 2026-09-28 — M5: tamper-evident audit trail

- **Tool:** CodeBuddy
- **Task:** Implemented the M5 hash-chained audit trail and query API.
- **Summary:** Built `event_schema` (canonical AuditEvent with deterministic sorted-key JSON payload, `event_from_decision`), `hash_chain` (`event_hash = SHA256(prev_hash + canonical_json)`, append/verify, JSON persistence), and `audit_query` (filter by user/resource-substring/query/decision/action/time window, reports chain verification — backs Demo 4). Verified end to end against the M3 pipeline: 6 real decisions chained and verified, tampering a field detected. Wrote 18 tests covering clean verification, field tampering, decision-flip, broken links, reordering, deletion, INV4 (every pipeline decision audited incl. denies), query filters, and time windows. Full suite: 93 passing. Marked M5 complete, outlined M6 (LLM answer agent) and flagged the LLM-client stub-vs-live decision.
- **Screenshot captured:** N — capture at end of session.

---

<!-- Template for future entries:

### YYYY-MM-DD — Mn: milestone/task

- **Tool:** CodeBuddy / WorkBuddy / Miora
- **Task:** What was being worked on
- **Summary:** What the conversation accomplished
- **Screenshot captured:** Y/N

-->