# Project Description — Tianquan 天权

> **Auditable AI answers that never overstep access rights.**

Built for the **Tencent Cloud AI CAN DO IT Singapore Hackathon 2026 — Track 4: FinTech (Aspire)**.

---

## The problem, told straight

A FinTech rolls out an internal AI assistant over all its company knowledge — Confluence, Jira, Slack, Google Drive. It's brilliant and everyone loves it. Then a **contractor** asks: *"What's our biggest client's default risk and the Q3 breach details?"* — and the assistant, trained to be helpful, answers. It pulls from a confidential incident report and a restricted finance doc the contractor was never cleared to see.

In most industries that's an embarrassing bug. **In regulated finance it's a reportable data breach** — a MAS compliance failure, a client-confidentiality violation, and a headline. The irony: the AI didn't get hacked. It did exactly what it was built to do. The access control was simply never there.

Here's the uncomfortable truth about today's "AI over your data" tools: they retrieve documents into the model's context with **no regard for who is asking**, or they bolt on filtering *after* generation and trust the model not to leak. Both approaches leak. You cannot prompt your way to a security guarantee.

## The insight

The problem isn't the model's intelligence — it's that it answers from information the user was never authorized to receive. So the fix isn't a smarter prompt or a post-hoc filter. It's structural:

> **The LLM cannot leak what it never receives.**

Tianquan (天权 — "heaven's authority") filters by permission **before** the model sees anything. The model only ever receives content the asker is authorized to view — and every retrieval, denial, and answer is checked against an access-control model we **formally proved** correct, then written to a tamper-evident audit trail a regulator can verify.

Not "we tested it and it seemed fine." **Proven, and provable.**

## Real-world scenario

Aspire (a B2B FinTech) has engineers, contractors, security teams, finance teams, and compliance officers — each with different access across Confluence, Jira, Slack, and Google Drive. An engineer asks: *"What's the status of the database migration and were there blockers raised in Slack?"* The answer should draw from the migration Jira ticket, the Slack thread, and the Confluence plan — but must **not** include the confidential Q3 security incident report that *also* mentions the migration, because the engineer lacks security-team clearance.

A contractor asking the same question — or fishing for the breach report directly — gets nothing, and crucially **cannot even tell whether the restricted content exists**. Same response as a question about something that isn't there. No side channel, no confirmation, no leak.

Tianquan makes the policy engine the authoritative gate **before** retrieval reaches the model, so these outcomes are architectural guarantees, not best-effort hopes.

## Solution design

### Business architecture

Tianquan sits between the user and four enterprise knowledge sources. The user asks a question through the query console. The system:

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
| INV6 | NoUnauthorizedCitation | Every citation corresponds to an authorized retrieved resource. |
| INV7 | NoMetadataLeakOnDeny | Denied content is not exposed through answer text or source titles. |

TLC model-checks every invariant across all reachable states of the pipeline (safe configuration: no error). The spec models **revocation interleaved with the query lifecycle** — so it explores orderings a human would never think to unit-test.

**What the model checker found (and why it matters):** the hard part of this system is not the permission check itself — that's a simple lookup. The hard part is *timing*. The checker proved that even a correctly-filtering implementation **leaks under a race**: if a resource is authorized at decision time but the user is revoked a moment later, a naive implementation that trusts the earlier decision serves content the user can no longer see (a time-of-check/time-of-use bug). The safe implementation re-checks the **live** ACL at retrieval time and is proven race-free. Flip one line in the spec and TLC hands you the exact exploit trace in seconds.

This is the distinction that matters: **tests check the cases you imagined; the model checker exhaustively finds the ones you didn't.** For a FinTech security control, "we proved no interleaving leaks" is a categorically stronger claim than "our tests passed."

## Business value — why a FinTech would deploy this

The thing blocking every bank and FinTech from rolling out an internal LLM today is exactly the risk in the opening: an assistant that can't *prove* it only used information the asker was allowed to see. Tianquan is that proof.

- **It unblocks AI adoption in regulated finance.** The blocker isn't capability, it's trust and auditability. Tianquan provides both, so the assistant can be deployed over sensitive client and internal data without becoming a breach vector.
- **No data leakage — structurally.** The LLM cannot leak restricted content because it never receives it. An architectural guarantee, not a prompt-level hope that survives one jailbreak.
- **Compliance-ready by construction.** Every allow/deny is written to a tamper-evident, hash-chained log. A compliance officer can query who accessed what, when — and detect if anyone edited the record. This is the artifact an auditor or regulator asks for.
- **Live revocation.** Off-board someone or pull a clearance and it takes effect on their next query — no reindex, no stale-permitted content. The filter re-fetches live ACLs every time (and we proved that's necessary).
- **Source-native semantics.** Each platform's real permission model is preserved (Confluence spaces/pages, Jira issue security, Slack channel membership, GDrive sharing), not flattened into a lossy generic ACL.
- **Formally verified.** The safety properties are model-checked, not just implemented — the kind of assurance that distinguishes a demo from something a risk committee would actually sign off on.

## Demo scenarios

1. **Allowed answer (multi-source)** — Alice gets an answer spanning 4 sources with 8 citations; 2 security docs are denied and filtered.
2. **Negative case, no metadata leak** — Bob (contractor) gets the same "could not find" message as a nonexistent topic; denial is recorded in audit but never surfaced.
3. **Live revocation** — Revoke Alice's engineer role from a Confluence page; ACL version bumps v1→v2; next query excludes it with no reindex.
4. **Audit inquiry** — Compliance officer queries the trail by user, resource, or decision; chain verification badge confirms tamper-evidence.
5. **Formal verification** — TLC output showing all invariants pass (safe) and a counterexample found (broken variant).

## CodeBuddy / WorkBuddy usage

Tianquan was built end-to-end using CodeBuddy as the primary development tool. The development log (`docs/dev-log/dev-log.md`) tracks each session with dates, tasks, and screenshots. The frontend UI was generated using Miora (Tencent Cloud AI creative studio).

## Repository

- **GitHub:** [tencent-hackathon](.) — complete source code
- **Live ADP agent:** [Tianquan on Tencent Cloud ADP](https://adp.tencentcloud.com/webim_exp/#/chat/ULzqcG) — agent name "Tianquan 天权" and welcome message confirmed visible.
- **Docs:** `docs/` — plan, architecture, current-state, ADRs, demo runbook, dev log
- **Tests:** 217 passing (`python -m pytest -q`)
- **Formal model:** `formal/` — TLA+ specification with TLC model configs
