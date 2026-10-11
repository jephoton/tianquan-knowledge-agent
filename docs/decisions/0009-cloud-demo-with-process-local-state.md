# ADR-0009: Cloud demo with process-local state

<!-- Generated from the user's deployment choice on 2026-10-11. -->

**Status:** Accepted architecture direction; implementation pending.

## Context

The demo is recorded and the full app needs a shareable URL. An all-serverless deployment would need shared persistence for ACL mutations, uploads and the audit chain. Browser localStorage cannot supply authoritative backend permissions or a shared audit history. The user chose the simpler hosted-backend approach and requested a plan only for another agent to execute.

## Decision

Serve the static frontend on Vercel and run the existing Python backend on one long-running cloud instance with one Uvicorn worker. Propose Render as the concrete host in the [deployment plan](../superpowers/plans/2026-10-11-cloud-demo-deployment.md); account/tier selection is pending. No database or shared-storage migration in this step. The user's laptop can be off.

## Rationale

The current state container and connectors already share mutations across requests in one process. Hosting that process preserves the demo behavior with limited changes to API configuration and CORS. Durable storage would add migration and recovery work that the hackathon demo does not currently require.

## Consequences

- All visitors share one synthetic demo state; concurrent requests still have implementation limits.
- Restart/redeploy resets seeded ACLs/uploads and truncates the audit log, regardless of disk persistence. Audit evidence must be saved before reset.
- Free hosting may sleep and reset on wake. The chosen tier must match the user's availability expectations; no paid resources are authorized by this planning task.
- Multiple workers/instances are incompatible with current state/file ownership. Shared persistent storage and synchronization are prerequisites for future scaling, not part of this deployment.
- Keep the ADP key exclusively on the backend. Restrict configured browser origins, retaining the existing demo persona behavior.
- Authentication, real connectors, missing-ACL behavior and grounding gaps remain documented prototype boundaries.
