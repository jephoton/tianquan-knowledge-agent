# ADR-0003: Mock connectors instead of real platform integrations

**Date:** 2026-09-27  
**Status:** Accepted

## Context

The Aspire challenge references Confluence, Jira, Slack, and Google Drive. Real API integration requires:

- OAuth credentials for each platform.
- Rate-limit handling, pagination, webhook setup.
- Significant setup time and a test workspace.

## Decision

Use **mock connectors** for V1, with realistic data and permission semantics.

## Rationale

- The demo's value is in the **permission-aware retrieval and formal verification**, not in the connector plumbing.
- Mock connectors allow full control over edge cases (revocation, restricted pages, private channels).
- Saves 2-3 days of OAuth/API integration work.
- Real connectors can be added as a stretch goal if time permits.

## Consequences

- Each mock connector must faithfully represent its source-specific permission model.
- Seed data must be rich and varied to demonstrate all demo scenarios.
- The architecture must treat connectors as swappable, so real connectors can replace mocks without changing the policy/retrieval/audit layers.