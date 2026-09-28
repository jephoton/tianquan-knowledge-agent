---
inclusion: always
---

# Persistent Handoff Layer & Commit Discipline

Every project must maintain a persistent handoff layer so work can be picked up
seamlessly by other people, workflows, models, and agents. Treat these docs as
first-class deliverables, not afterthoughts.

> To apply this rule to ALL projects (not just this one), copy this file to
> `~/.kiro/steering/handoff-layer.md`. Kiro cannot write outside the workspace,
> so it lives here as workspace steering by default.

## Required structure

Every project must have a `docs/` folder acting as the handoff layer:

```
docs/
  plan.md          # Source of truth: problem, scope, roadmap, milestones
  architecture.md  # System design, trust boundaries, module map, data models
  current-state.md # What exists now, what's next, blockers (the handoff snapshot)
  decisions/       # Architecture Decision Records (ADRs), one file per decision
```

Optional but encouraged:

```
docs/
  dev-log/         # Chronological log of significant work sessions
  roadmap.md       # If the roadmap is large enough to live outside plan.md
```

If a project already has a handoff layer, read it first to learn the project's
conventions and follow them. Do not impose this template over an existing one —
adapt to what's there.

## Roles of each document

- **plan.md** — The source of truth. When plan.md and any other artifact
  disagree, plan.md wins until explicitly updated. Contains problem statement,
  thesis, scope (in/stretch/deferred), roadmap, and milestones.
- **architecture.md** — How the system is built: diagrams, trust boundaries,
  module map, data models, request lifecycle, technology choices.
- **current-state.md** — The handoff snapshot. What milestone we're on, what
  exists, what's next, and any blockers. This is the first thing another agent
  reads to know where to continue.
- **decisions/** — ADRs. One markdown file per significant decision, numbered
  (e.g. `0001-...md`), recording Context, Decision, Rationale, Consequences.

## Working rules

1. **Read before acting.** At the start of any session, read `current-state.md`
   and `plan.md` to understand where the project is and what comes next.
2. **Update after tasks.** After completing any meaningful unit of work, update
   the handoff layer — especially `current-state.md` (what now exists, what's
   next, blockers) and the roadmap/milestone status in `plan.md`.
3. **Keep the "Last updated" date current** on any doc you touch.
4. **Record decisions as ADRs** when you make a non-trivial architectural or
   scope choice, so the reasoning survives the handoff.
5. **Log significant sessions** in `dev-log/` if the project uses one.

## Commit discipline

Make frequent, atomic commits with [Conventional Commits](https://www.conventionalcommits.org/)
messages. One logical change per commit.

- `feat:` — new functionality
- `fix:` — bug fix
- `docs:` — documentation / handoff-layer updates
- `refactor:` — restructuring without behavior change
- `test:` — adding or changing tests
- `chore:` — scaffolding, tooling, config
- Project-specific scopes are welcome (e.g. `feat(m2): ...`, `formal: ...`).

Rules:

- Commit code and its tests together; keep unrelated changes in separate commits.
- Commit handoff-layer updates as their own `docs:` commit (or alongside the
  work they document when tightly coupled).
- Stage specific files rather than `git add .` to avoid sweeping in unrelated
  changes. Flag any file that may contain secrets before committing.
- Do not create commits unless the user has asked for commits to be made as part
  of the working agreement, or explicitly requests one.
