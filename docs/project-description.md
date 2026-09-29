# Project Description — VeriBrain

> **Auditable AI answers that never overstep access rights.**

Built for the **Tencent Cloud AI CAN DO IT Singapore Hackathon 2026 — Track 4: FinTech (Aspire)**.

---

## Overview

VeriBrain is a permission-aware enterprise knowledge agent that unifies context across Confluence, Jira, Slack, and Google Drive, answers natural-language questions grounded in that unified context, and does so under the uncompromising constraint that **every piece of information it exposes respects the original platform's access controls**, with full auditability.

The core constraint:

> **The LLM cannot leak what it never receives.**

Filtering happens **before** the LLM, not after. The model only ever sees content the asker is authorized to view. Every retrieval, denial, answer, and audit event is checked against a formally specified access-control model.

## Real-world scenario

Aspire (a B2B FinTech) has engineers, contractors, security teams, finance teams, and compliance officers — each with different access levels across Confluence, Jira, Slack, and Google Drive. An engineer asks: *"What's the status of the database migration and were there blockers raised in Slack?"* The answer should draw from the migration Jira ticket, the Slack thread, and the Confluence plan — but must **not** include the confidential security incident report that also mentions the migration, because the engineer lacks security-team clearance.

Today, most "AI over your data" demos retrieve documents into LLM context with no regard for who is asking. VeriBrain solves this by making the policy engine the authoritative gate **before** retrieval reaches the model.

## Solution design

### Business architecture

VeriBrain sits between the user and four enterprise knowledge sources. The user asks a question through the query console. The system:

1. Resolves the user's identity and roles.
2. Searches across all four sources for candidate documents.
3. **Filters candidates through the policy engine** — each document is checked against the user's permissions using the source-native permission model (Confluence space/page, Jira project-role-issue-security, Slack channel membership, GDrive file-folder sharing).
4. Assembles only the **allowed** documents into the LLM context window.
5. Generates a grounded answer with citations.
6. Logs every decision (allow and deny) to a tamper-evident hash-chained audit trail.

Denied documents are never passed to the LLM. The user receives the same generic "could not find accessible information" message whether the content doesn't exist or they simply can't see it — preventing metadata side-channel leakage.

### Technical architecture

| Layer | Technology | Role |
|-------|-----------|------|
| Frontend | Static HTML/JS (Miora-generated) | Query console, policy inspector, audit explorer, persona switcher, revocation controls |
| API | Python / FastAPI | Thin REST adapter over the orchestrator |
| Orchestrator | Python | Wires retrieval → audit → answer → audit |
| Retrieval | Python | Keyword candidate search → live-ACL permission filter → context assembler |
| Policy Engine | Python | Source-specific permission mapping + sensitivity clearance + action permissions → Decision |
| Formal Model | TLA+ / TLC | Model-checked safety invariants (7 invariants, safe + broken variants) |
| Audit | Python | Hash-chained JSON event log with tamper detection |
| LLM | Tencent Cloud LLM (via interface) | Swappable; stub for dev, live provider for demo |
| Dev Tool | CodeBuddy | Required proof of usage |

### Trust boundaries

1. **Identity verified** — user is authenticated with roles.
2. **Policy engine is authoritative** — all authorization decisions go through the policy engine against live ACLs.
3. **Only authorized content passes** — the permission filter drops denied candidates before context assembly.
4. **LLM sees only filtered context** — the model receives only the assembled, authorized context.
5. **Answer + citations logged** — every decision and the final answer are recorded in the audit trail.

### How prompts drive AI generation

The user's natural-language question drives the candidate search (keyword/token-overlap scoring). The retrieved candidates are then filtered through the policy engine — **no AI is involved in the authorization decision**. The LLM only enters the pipeline after filtering, receiving a context window containing exclusively authorized content with citation markers. The answer agent generates a grounded response and strips any citation not backed by the context (INV6: NoUnauthorizedCitation).

### Formal verification

The access-control model is specified in TLA+ with 7 safety invariants:

| ID | Invariant | Meaning |
|----|-----------|---------|
| INV1 | RetrievedOnlyIfAuthorized | No retrieved resource may be outside the asker's effective permission set. |
| INV2 | LLMSeesOnlyRetrievedContent | The model never receives unauthorized content. |
| INV3 | RevokedAccessNotReusable | After permission revocation, future queries cannot use the old permission. |
| INV4 | EveryDecisionAudited | Every allow/deny decision creates an audit event. |
| INV5 | NoPrivilegeEscalation | Agent effective permissions ⊆ delegating user's permissions (stretch). |
| INV6 | NoUnauthorizedCitation | Every citation corresponds to an authorized retrieved resource. |
| INV7 | NoMetadataLeakOnDeny | Denied content is not exposed through answer text or source titles. |

TLC model-checks all invariants in the safe configuration (28 states, no error). A deliberately broken variant (filter-after-retrieval) produces an INV1 counterexample at depth 4 — demonstrating the value of pre-LLM filtering in 60 seconds.

## Business value

- **Compliance-ready AI**: every decision is auditable in a tamper-evident trail. Compliance officers can query who accessed what, when, and whether the chain is intact.
- **No data leakage**: the LLM structurally cannot leak restricted content because it never receives it. This is a architectural guarantee, not a prompt-level hope.
- **Live revocation**: permission changes take effect on the next query with no reindexing — the policy filter re-fetches live ACLs every time.
- **Source-native semantics**: each platform's permission model is preserved (Confluence spaces/pages, Jira issue security, Slack channel membership, GDrive sharing) rather than flattened into a generic ACL.
- **Formally verified**: the safety properties are model-checked, not just implemented — providing provable guarantees that matter in a FinTech context.

## Demo scenarios

1. **Allowed answer (multi-source)** — Alice gets an answer spanning 4 sources with 8 citations; 2 security docs are denied and filtered.
2. **Negative case, no metadata leak** — Bob (contractor) gets the same "could not find" message as a nonexistent topic; denial is recorded in audit but never surfaced.
3. **Live revocation** — Revoke Alice's engineer role from a Confluence page; ACL version bumps v1→v2; next query excludes it with no reindex.
4. **Audit inquiry** — Compliance officer queries the trail by user, resource, or decision; chain verification badge confirms tamper-evidence.
5. **Formal verification** — TLC output showing all invariants pass (safe) and a counterexample found (broken variant).

## CodeBuddy / WorkBuddy usage

VeriBrain was built end-to-end using CodeBuddy as the primary development tool. The development log (`docs/dev-log/dev-log.md`) tracks each session with dates, tasks, and screenshots. The frontend UI was generated using Miora (Tencent Cloud AI creative studio).

## Repository

- **GitHub:** [tencent-hackathon](.) — complete source code
- **Docs:** `docs/` — plan, architecture, current-state, ADRs, demo runbook, dev log
- **Tests:** 138 passing (`python -m pytest -q`)
- **Formal model:** `formal/` — TLA+ specification with TLC model configs
