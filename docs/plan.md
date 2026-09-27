# Plan — VeriBrain

> **Status:** Source of truth. When this document and any other artifact disagree, this document wins until explicitly updated.
>
> **Last updated:** 2026-09-27

---

## 1. Problem

Aspire's Track 4 challenge asks teams to build an **Internal Brain** — an AI-augmented knowledge system that unifies context across Confluence, Jira, Slack, and Google Drive, answers natural-language questions grounded in that unified context, and does so under the uncompromising constraint that **every piece of information it exposes respects the original platform's access controls**, with full auditability.

The hard part is not RAG. The hard part is:

- Permission-aware retrieval before the LLM sees anything.
- Source-specific permission semantics (Confluence space/page, Jira project-role-issue, Slack channel-membership, GDrive file-folder-user).
- Live permission revocation without serving stale-permitted content.
- No metadata side-channel leakage on denial.
- Tamper-evident, queryable audit trail.
- LLM safety in a permissioned world (no confabulation of restricted content).

## 2. Thesis

> Enterprise AI assistants fail not because they cannot answer questions, but because they cannot prove they answered using only information the user was allowed to see.

VeriBrain is a permission-aware internal brain where every retrieval, denial, answer, and audit event is checked against a formally specified access-control model.

The core constraint:

> **The LLM cannot leak what it never receives.**

## 3. Scope

### V1 (decision deadline target)

Formally specified, permission-aware enterprise RAG:

- Multi-source retrieval from mock Confluence, Jira, Slack, GDrive.
- Pre-LLM permission filtering.
- Source-specific permission models mapped to a common authorization decision.
- Live permission revocation handling.
- No-metadata-leak denial behavior.
- Grounded answers with citations.
- Tamper-evident hash-chained audit trail.
- Queryable audit explorer.
- TLA+ formal specification with model-checked safety invariants.
- Visible policy decision UI (ALLOW/DENY with reason, permission source, ACL version).
- Built on at least one of CodeBuddy or WorkBuddy (hackathon requirement).

### Stretch (time permitting)

- Delegated action agent with bounded permissions (`effective_agent_permissions ⊆ delegating_user_permissions`).
- Dafny executable verification of `isAllowed`.
- Real platform connectors instead of mocks.
- Interactive demo: "Export this answer to Finance" through delegated permission checks.
- LLM hallucination detection layer (compare generated answer against retrieved context).

### Explicitly deferred

- Distributed consensus.
- Information-flow control.
- Custom policy DSL.
- Capability security.

## 4. Formal verification story

### Tool: TLA+

TLA+ is the primary formal artifact because the critical properties are temporal/state-machine properties involving revocation and audit sequencing.

### Model entities

```
Users
Roles
Resources
Permissions
Source ACLs
Queries
Retrievals
Answers
AuditEvents
Revocations
```

### Invariants to model-check

| ID | Invariant | Meaning |
|----|-----------|---------|
| INV1 | `RetrievedOnlyIfAuthorized` | No retrieved resource may be outside the asker's effective permission set. |
| INV2 | `LLMSeesOnlyRetrievedContent` | The model never receives unauthorized content. |
| INV3 | `RevokedAccessNotReusable` | After permission revocation, future queries cannot use the old permission. |
| INV4 | `EveryDecisionAudited` | Every allow/deny decision creates an audit event. |
| INV5 | `NoPrivilegeEscalation` | If agents exist, their effective permissions ⊆ delegating user's permissions. |
| INV6 | `NoUnauthorizedCitation` | Every citation in the answer must correspond to an authorized retrieved resource. |
| INV7 | `NoMetadataLeakOnDeny` | Denied content is not exposed through answer text or source titles. |

### Optional: Dafny

A small verified `isAllowed(user, resource, action)` function proving that returned permissions are a subset of the user's actual permissions. Only if time permits and the team is already comfortable with Dafny.

## 5. Demo scenarios

### Demo 1: Allowed answer (multi-source)

- **User:** Alice, Backend Engineer
- **Query:** "What's the status of the database migration project and were there blockers raised in Slack last week?"
- **Show:** ALLOW Jira:MIG-231, ALLOW Slack:#db-migration, ALLOW Confluence:/engineering/db-migration-plan, DENY Slack:#leadership-private. Answer includes only allowed citations.

### Demo 2: Negative case with no metadata leak

- **User:** Bob, External Contractor
- **Query:** "Show me the security incident report from the Q3 breach."
- **User sees:** "I could not find accessible information matching your request."
- **Policy panel:** DENY — user lacks security-team scope. Metadata hidden from requester.
- **Admin audit view:** Denied attempt recorded.

### Demo 3: Live permission revocation

- Before: Alice can access #payment-incident-private.
- Action: Revoke Alice from that channel.
- Same query now excludes those messages.
- **Show:** Previous ACL version 17 → Current ACL version 18. DENY due to revoked channel membership.

### Demo 4: Audit inquiry

- **User:** Compliance officer
- **Query:** "Show everything user jdoe accessed related to payment-gateway in the last 30 days."
- **Show:** Retrieved documents, denied documents, answers, timestamps, policy decisions, audit hash verification status.

### Demo 5: Formal verification

- Show TLA+ TLC output: all invariants OK.
- Show a broken variant (filter after retrieval) where TLC finds a counterexample.
- Makes formal methods understandable to judges in 60 seconds.

## 6. Tech stack

| Layer        | Technology            |
|--------------|----------------------|
| Backend      | Python / FastAPI      |
| Frontend     | React + TypeScript (UI generated via Miora) |
| Formal model | TLA+ / TLC            |
| Audit log    | Hash-chained JSON     |
| LLM          | Tencent Cloud LLM via WorkBuddy / ADP |
| UI design    | Miora (Tencent Cloud AI creative studio) |
| Dev tool     | CodeBuddy (required for proof of usage) |

## 7. Repo structure

```
frontend/
backend/
    api/
    connectors/
    auth/
    policy/
    retrieval/
    agents/
    audit/
formal/
tests/
docs/
    plan.md
    architecture.md
    current-state.md
    decisions/
```

## 8. Roadmap & milestones

**Target deadline:** 12 October 2026 (buffer before the real submission deadline on 16 Oct). No hard per-milestone dates — progress is tracked by checkpoint completion, not calendar dates.

Each milestone is a checkpoint: code committed, tests passing, `current-state.md` updated, commit pushed.

| Milestone | Exit criteria |
|-----------|---------------|
| **M0 — Project bootstrap** ✅ | Git repo initialized. Handoff docs created. Repo structure scaffolded. Initial commit pushed. |
| **M1 — Data model & mock sources** | Mock connectors for Confluence, Jira, Slack, GDrive with realistic permission semantics. Document/ticket/message/file data model defined. Seed data with varied ACLs. |
| **M2 — Policy engine** | Authorization decision function: given (user, resource, action) → allow/deny + reason. Source-specific permission mapping. ACL versioning. Unit tests for positive and negative cases. |
| **M3 — Permission-aware retrieval pipeline** | Candidate search → policy filter → context assembler. LLM never sees denied content. Integration tests proving LLM context contains only authorized documents. |
| **M4 — TLA+ formal specification** | `formal/access_control.tla` with all 7 invariants. TLC model-checks all invariants pass. At least one counterexample found in a deliberately broken variant. |
| **M5 — Audit trail** | Hash-chained event log. Audit event schema. Tamper detection. Audit query API. Tests for chain integrity and tamper detection. |
| **M6 — LLM answer agent** | Orchestrator + answer agent. Grounded answers with citations. Query → retrieval → answer → audit end-to-end. |
| **M7 — Live revocation handling** | Permission change API. Revocation reflected in subsequent queries. No stale-permitted content served. Demo 3 working. |
| **M8 — Frontend UI** | Miora-generated UI. Query console, policy inspector panel (ALLOW/DENY cards), audit explorer, demo persona switcher. All 4 demo scenarios visible in UI. |
| **M9 — No-metadata-leak & negative cases** | Demo 2 working. Denial does not reveal existence. Audit logs denied attempts. |
| **M10 — End-to-end integration & polish** | All 5 demos working end-to-end. Architecture diagram. Trust-boundary diagram. CodeBuddy/WorkBuddy usage proof captured. |
| **M11 — Stretch: delegated action agent** | Bounded delegation. `effective_agent_permissions ⊆ delegating_user_permissions`. "Export to Finance" action through permission checks. |
| **M12 — Stretch: Dafny verification** | Verified `isAllowed` function. Subset proof. |
| **M13 — Submission preparation** | All submission deliverables completed (see below). |
| **SUBMIT** | Submit before 16 Oct deadline. |

### M13 — Submission deliverables

All items below must be completed before considering the project submission-ready:

| # | Deliverable | Required | Details |
|---|------------|----------|---------|
| 1 | Project title | ✅ | "VeriBrain" |
| 2 | Short blurb | ✅ | Under 10 words: "Auditable AI answers that never overstep access rights." |
| 3 | Project description | ✅ | Overview, real-world scenario insights, comprehensive solution design (business + technical architecture), how prompts drive AI generation, business value. |
| 4 | CodeBuddy / WorkBuddy conversation history | ✅ | Min 3 screenshots/screen recordings of chat logs from CodeBuddy or WorkBuddy during development. **Track continuously from M0** — see dev log below. |
| 5 | Cover image | ✅ | 16:9 image, recommended 380×216px. Generate via Miora. |
| 6 | Demo video | Optional | 5–8 min: project overview, core agent features, build approach reflection with CodeBuddy/WorkBuddy tips. |
| 7 | Project link | Optional | Live URL or demo link. Bonus points. |
| 8 | GitHub repository | ✅ | Complete source code. |
| 9 | Architecture diagram | ✅ | System architecture + trust-boundary diagram. |
| 10 | Worked examples | ✅ | Each of the 5 demo scenarios with a worked example in the submission. |

### Development log (ongoing — track from M0)

The CodeBuddy/WorkBuddy conversation proof is a **required deliverable** that must be captured during development, not reconstructed at the end. The handbook requires a minimum of 3 screenshots or screen recordings of chat logs.

Track this in [`docs/dev-log.md`](dev-log.md). Each entry should record:

- Date
- Tool used (CodeBuddy / WorkBuddy / Miora)
- What was being worked on (milestone + task)
- Brief summary of what the conversation accomplished
- Screenshot/screen recording captured? (Y/N)

**Rule:** Take a screenshot at the end of any significant CodeBuddy/WorkBuddy session. Don't wait until M13 — by then the conversation history will be lost.

## 9. Git workflow

- Commit frequently with small, logical changes.
- Commit messages follow [Conventional Commits](https://www.conventionalcommits.org/):
  - `feat: add permission filter to retrieval pipeline`
  - `fix: handle revoked ACL in context assembler`
  - `docs: update plan with M3 completion`
  - `refactor: extract authorization decision from policy engine`
  - `test: add negative-case tests for contractor role`
  - `chore: scaffold backend module structure`
  - `formal: add TLA+ invariant RetrievedOnlyIfAuthorized`
- Update `docs/current-state.md` at each milestone.

## 10. Success criteria

For the hackathon, the project succeeds if a judge can see, within the demo:

1. The same question yields different safe answers for different users.
2. A denied request does not leak that restricted content exists.
3. A revoked permission takes effect immediately.
4. Every decision is visible in a tamper-evident audit trail.
5. The access-control model is formally specified and model-checked, not just implemented.

## 11. Key risks & mitigations

| Risk | Mitigation |
|------|-----------|
| Scope creep into action agent too early | Delegated actions are M11 stretch, not V1 core. |
| Mock connectors feel unrealistic | Seed with rich, varied ACLs across all four platforms. |
| TLA+ model too abstract to impress judges | Show counterexample in broken variant — make it tangible. |
| LLM confabulates restricted content | Pre-filter + citation grounding + optional hallucination check. |
| Running out of time | Milestones are ordered by demo priority. M1-M8 deliver the core demo. |