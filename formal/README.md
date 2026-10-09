# Formal Specification — Tianquan 天权

TLA+ specification of the permission-aware retrieval access-control model.

## Files

- `access_control.tla` — the specification (query lifecycle state machine).
- **`MC_tianquan.tla` / `MC_tianquan.cfg` — the LIVE DEMO harness.** One file;
  flip the `BROKEN` flag to go from "proven safe" to "counterexample".
- `MC_safe.tla` / `MC_broken.tla` — fixed-variant backups (same content, pinned
  to FALSE/TRUE) for a non-interactive run.

## Model

A single query's lifecycle over a small universe (2 users, 2 resources):

```
init --Search--> searched --Decide--> decided --Retrieve--> retrieved --Answer--> answered
       (Revoke can fire in init / searched / decided — i.e. BEFORE retrieval)
```

- `Authorized` baseline ACL: alice→{r1}, bob→{r2}. Asker = alice.
- Search may over-fetch (any non-empty subset), so r2 (which alice cannot read)
  can appear as a candidate.
- `Decide` records allow/deny per candidate from the live ACL and audits it.
- `Revoke` may fire at any point up to and including the `decided` phase — so
  the model explores the **time-of-check / time-of-use race**: a resource
  authorized at Decide time can be revoked before Retrieve.
- `Retrieve`:
  - **safe** (`BROKEN=FALSE`): admits a candidate only if the asker is
    authorized per the **live ACL at retrieval time** (re-check). This mirrors
    the real permission filter re-fetching live ACLs, and it defeats the race.
  - **naive** (`BROKEN=TRUE`): trusts the decide-time `decisions` snapshot and
    never re-checks → leaks under revoke-after-decide.

## Invariants

| ID | Invariant | Modeled |
|----|-----------|---------|
| INV1 | `RetrievedOnlyIfAuthorized` | ✅ |
| INV2 | `LLMSeesOnlyRetrievedContent` | ✅ |
| INV3 | `RevokedAccessNotReusable` | ✅ |
| INV4 | `EveryDecisionAudited` | ✅ |
| INV5 | `NoPrivilegeEscalation` | out of scope (action agent removed) |
| INV6 | `NoUnauthorizedCitation` | ✅ |
| INV7 | `NoMetadataLeakOnDeny` | ✅ |

## Live demo — flip one flag

The VS Code TLA+ extension can run these directly (right-click the `.tla`,
"Check model with TLC"). From the CLI, using the jar bundled with the extension:

```powershell
$jar = (Get-ChildItem "$env:USERPROFILE\.vscode\extensions\tlaplus.vscode-ide-*\out\tools\tla2tools.jar" | Select-Object -First 1).FullName

# 1. Run as-is (BROKEN=FALSE) — expect: "No error has been found." (34 states)
java -cp $jar tlc2.TLC -config MC_tianquan.cfg MC_tianquan.tla

# 2. LIVE: edit MC_tianquan.tla, change `BROKEN <- FALSE` to `BROKEN <- TRUE`, save.
# 3. Re-run the same command — expect: "Invariant INV1 ... is violated." + trace.
```

## The counterexample (the payoff)

When `BROKEN=TRUE`, TLC prints the exact unsafe interleaving — the revocation
race:

1. `acl: r1→{alice}` — alice may read r1. Search finds it.
2. `Decide` → r1 = **allow** (correct at that instant).
3. **`Revoke` fires — alice removed from r1 (`r1→{}`) — still in `decided`,
   before retrieval.**
4. Naive `Retrieve` trusts the stale "allow" snapshot → **r1 enters the context
   though alice is no longer authorized.** INV1 violated.

The lesson, proven not just tested: filtering correctly is not enough — you
must re-check the live ACL **at retrieval time**, because permissions can change
between the decision and the read. Unit tests check the cases you imagined; the
model checker exhaustively found the one you didn't.

Two bugs are demonstrable from this one spec:
- **"forgot to filter"** — change safe `Retrieve` to admit all candidates →
  obvious leak (the relatable bug).
- **the revocation race** — the `BROKEN` flag above → subtle TOCTOU leak (the
  impressive bug).

> TLC writes a `states/` dir and `*_TTrace_*` files on a run; these are
> generated artifacts and are gitignored.
