# Formal Specification — VeriBrain

TLA+ specification of the access-control model for VeriBrain.

## Files

- `access_control.tla` — the TLA+ specification (M4).
- `access_control.cfg` — TLC model-checker configuration (M4).

## Invariants

| ID | Invariant |
|----|-----------|
| INV1 | `RetrievedOnlyIfAuthorized` |
| INV2 | `LLMSeesOnlyRetrievedContent` |
| INV3 | `RevokedAccessNotReusable` |
| INV4 | `EveryDecisionAudited` |
| INV5 | `NoPrivilegeEscalation` |
| INV6 | `NoUnauthorizedCitation` |
| INV7 | `NoMetadataLeakOnDeny` |

See [docs/plan.md](../docs/plan.md#4-formal-verification-story) for details.