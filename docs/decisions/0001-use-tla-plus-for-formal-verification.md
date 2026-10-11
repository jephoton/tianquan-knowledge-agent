# ADR-0001: Use TLA+ as the primary formal verification tool

**Date:** 2026-09-27  
**Status:** Accepted

## Context

The project requires formal verification of access-control safety properties, including:

- Unauthorized users never access protected resources.
- Revoked permissions cannot be used after revocation.
- Every authorization decision produces an audit event.
- Delegation cannot escalate privilege (stretch).

These are temporal/state-machine properties involving state transitions (revocation, ACL version changes, audit sequencing).

The candidate tools are:

1. **TLA+ / TLC** — description language for concurrent and distributed systems, model-checker.
2. **Dafny** — program verifier with Hoare-logic-style pre/postconditions.
3. **Alloy** — declarative modeling language with analyzer.

## Decision

Use **TLA+ / TLC** as the primary formal artifact.

## Rationale

- The critical properties are **temporal** (state before revocation vs. after revocation, audit ordering). TLA+ is designed for exactly this.
- TLC model-checks the six active invariants (INV1–INV4, INV6, INV7) and find counterexamples in broken variants, which is demonstrable to judges.
- TLA+ specifications are compact for this problem size.
- Dafny is better for proving implementation-level function correctness, which is deferred beyond the hackathon demo.

## Consequences

- The TLA+ spec is an abstract model, not executable production code.
- Property tests in Python will mirror the same invariants at the implementation level.
- Dafny/implementation-level verification remains deferred; M12 was repurposed for source freshness indicators.
- The finite model is not a proof of the whole Python application. INV5 is out of scope and INV8 is a Python-only heuristic.