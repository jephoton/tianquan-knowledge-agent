# Roadmap — Tianquan 天权

<!-- Generated current roadmap, reconciled on 2026-10-11. Original plan retained in history/original-roadmap.md. -->

This file records scope and milestone status. [Current state](current-state.md) is authoritative for what is implemented and verified; [architecture](architecture.md) describes the actual system. The [original roadmap](history/original-roadmap.md) retains earlier estimates and decisions for history.

## Goal and scope

Build Aspire's FinTech Internal Brain: cited answers across Confluence, Jira, Slack and Drive, with permission checks before LLM context, live revocation and an inspectable audit trail. The differentiator is a TLA+ model of access-control safety, including revocation ordering, backed by Python implementation tests.

The implemented demo uses synthetic source data and seeded personas. It demonstrates the design without claiming real enterprise connector integration, SSO, durable storage or a proof of the full application. The LLM cannot receive denied source content through the intended retrieval path; the known implementation limits are recorded in [current state](current-state.md#known-boundaries-and-follow-ups).

## Milestones

| Milestone | Current result |
|---|---|
| M0 Bootstrap | Complete: repo and handoff layer |
| M1 Data model and mock sources | Complete: four mock platforms, 20 resources, seven personas |
| M2 Policy engine | Complete: source rules, sensitivity, action permissions and ACL versions |
| M3 Permission-aware retrieval | Complete: cross-source search, live-ACL filter, bounded context |
| M4 TLA+ | Complete: six active safety invariants; safe/broken harnesses |
| M5 Audit | Complete: hash chain, append-only JSONL, file verification and search |
| M6 Answer agent | Complete: ADP adapter, fresh conversations, offline fallback, citations |
| M7 Revocation | Complete: grant/revoke and audited ACL changes; next-query effect |
| M8 Frontend/API | Complete: static Miora-derived dashboard; query, preview/export, audit and inspector |
| M9 Negative cases | Complete: canonical denial/no-match message; missing Q5 regression |
| M10 Integration/polish | Complete: diagrams, clean mode, refresh buttons, toast removal |
| M11 Grounding | Complete: lexical checks; all-rejected fallback remains a documented limitation |
| M12 Freshness | Complete: source timestamps and citation age labels; content remains indexed |
| M13 Injection detection | Complete: suspicious-query audit flags, not an authorization mechanism |
| M14 Review | Implementation review/fixes complete; known gaps retained in current state |
| M15 Submission | In progress: user reports video complete; final blurb/description and hosting remain |
| Hosting | Planned only: [Vercel frontend + cloud backend plan](superpowers/plans/2026-10-11-cloud-demo-deployment.md) |

## Formal assurance

TLC checks INV1–INV4, INV6 and INV7 in the configured two-user/two-resource model. INV5 (delegation) is deferred because the action agent is out of scope. INV8 (grounding) is an implementation heuristic, not a TLA+ invariant. Python tests check corresponding scenarios; there is no mechanically verified refinement from the model to Python. See [formal README](../formal/README.md).

## Demo and worked examples

The recorded outline is [demo-script.md](demo-script.md); exact inputs and expected behavior are in [demo-runbook.md](demo-runbook.md). The final sequence includes Bob/Charlie on the same Q3 query, Charlie's source viewer/export and missing Q5, engineer-role revocation on `confluence:db-migration-plan` (ACL v1 → v2), audit inspection and TLA+ assurance. Clean mode is shown on first UI entry after the architecture diagram. The connector showcase was removed.

## Submission checklist

This is a delivery checklist, not evidence that files were uploaded. The user's latest status is that only the two text fields and deployment remain. Do not treat older dev-log capture reminders as new outstanding work.

| Item | Status / location |
|---|---|
| Title | Tianquan 天权 |
| Short blurb (<10 words) | Draft: “Permission-safe AI retrieval backed by formal verification.” (7 words) |
| Project description | Revised draft: [project-description.md](project-description.md), covering target users/scenarios, pain points, architecture/prompts and defined impact |
| CodeBuddy usage proof | Historical evidence inventory: [development log](dev-log/dev-log.md); final upload not inspected |
| Cover | User asset exists locally; final upload not inspected |
| Demo video | Completed, user-reported; reflection at the end |
| App link | Full application not deployed; direct ADP chat is a separate experience |
| Repository | [jephoton/tianquan-knowledge-agent](https://github.com/jephoton/tianquan-knowledge-agent) |
| Architecture | [PNG](architecture.png) and [SVG](architecture.svg) |
| Worked examples | [Runbook](demo-runbook.md), including allowed, denied, revocation, audit and formal cases |

The earlier internal target was 12 October and the recorded event deadline was 16 October 2026. Treat those as planning notes and confirm the submission portal's deadline before submitting.

## Deferred scope

Real source connectors, verified SSO/OIDC, shared durable storage, concurrency hardening, externally anchored audit history, semantic grounding, action delegation, PII redaction and implementation-level proof remain future work. Resource preview/export is already implemented; destination-aware answer export is a separate future feature.

## Working conventions

Use atomic Conventional Commits, update only relevant handoff files after material changes, and verify the affected behavior. Check GitHub authentication before pushing. Preserve user assets and authored narration; store no credentials or secret-bearing evidence in docs. Deployment work must follow the separately authorized handoff plan.
