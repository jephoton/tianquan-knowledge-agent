# Formal Specification — Tianquan 天权

TLA+ specification of the permission-aware retrieval access-control model.

## Files

- `access_control.tla` — the specification (query lifecycle state machine).
- `MC_safe.tla` / `MC_safe.cfg` — model harness, `BROKEN = FALSE`. All
  invariants hold.
- `MC_broken.tla` / `MC_broken.cfg` — model harness, `BROKEN = TRUE`
  (filter-after-retrieval anti-pattern). TLC finds a counterexample.

## Model

A single query's lifecycle over a small universe (2 users, 2 resources):

```
init --Search--> searched --Decide--> decided --Retrieve--> retrieved --Answer--> answered
       (Revoke can fire in init/searched, before the policy decision)
```

- `Authorized` baseline ACL: alice→{r1}, bob→{r2}. Asker = alice.
- Search may over-fetch (any non-empty subset of resources), so r2 (which
  alice cannot read) can appear as a candidate.
- `Decide` records allow/deny per candidate from the **live** ACL and audits it.
- `Retrieve` (safe) admits only `allow` candidates to the context; (broken)
  admits all candidates regardless.

## Invariants

| ID | Invariant | Modeled |
|----|-----------|---------|
| INV1 | `RetrievedOnlyIfAuthorized` | ✅ |
| INV2 | `LLMSeesOnlyRetrievedContent` | ✅ |
| INV3 | `RevokedAccessNotReusable` | ✅ |
| INV4 | `EveryDecisionAudited` | ✅ |
| INV5 | `NoPrivilegeEscalation` | deferred (delegation is M11 stretch) |
| INV6 | `NoUnauthorizedCitation` | ✅ |
| INV7 | `NoMetadataLeakOnDeny` | ✅ |

See [docs/plan.md](../docs/plan.md#4-formal-verification-story) for details.

## Running TLC

The VS Code TLA+ extension can run these directly (right-click the `.tla`,
"Check model with TLC"). From the CLI, using the jar bundled with the
extension:

```powershell
$jar = "$env:USERPROFILE\.vscode\extensions\tlaplus.vscode-ide-*\out\tools\tla2tools.jar"

# SAFE — expect: "Model checking completed. No error has been found."
java -cp $jar tlc2.TLC -config MC_safe.cfg MC_safe.tla

# BROKEN — expect: "Invariant INV1_RetrievedOnlyIfAuthorized is violated."
java -cp $jar tlc2.TLC -config MC_broken.cfg MC_broken.tla
```

## Results (last run 2026-09-28)

- **Safe:** all 6 invariants hold. 28 distinct states, no error.
- **Broken:** INV1 violated at depth 4. Counterexample trace:
  1. Search over-fetches candidate `r2` (alice is not authorized for r2).
  2. Decide correctly returns `deny` for r2 and audits the denial.
  3. Retrieve (filter-after-retrieval) puts r2 into the context anyway.
  4. INV1/INV2/INV7 violated: alice's LLM context contains denied content.

This is the Demo 5 payoff: same spec, one flag flipped, and the model checker
exhibits the exact unsafe trace that pre-LLM filtering (ADR-0002) prevents.

> TLC writes a `states/` dir and `*_TTrace_*` files on a run; these are
> generated artifacts and are gitignored.
