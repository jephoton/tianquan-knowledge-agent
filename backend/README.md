# Backend — VeriBrain

Python / FastAPI backend for the permission-aware enterprise knowledge agent.

## Structure

```
api/          # FastAPI routes
connectors/   # Mock Confluence/Jira/Slack/GDrive connectors
auth/         # Identity, roles, sessions
policy/       # Policy engine, permission mapping, delegation, freshness
retrieval/    # Indexer, candidate search, permission filter, context assembler
agents/       # Orchestrator, answer agent, optional action agent
audit/        # Event schema, hash chain, audit query
```

## Setup

> Will be added once scaffolding is complete.