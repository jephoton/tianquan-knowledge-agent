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

## Live demo — edit the real logic, not a flag

The demo injects a bug the way an engineer actually would — editing the real
retrieval rule — and TLC proves it leaks. (The `BROKEN` constant still exists so
the `MC_safe`/`MC_broken` harnesses run automatically, but the *demo* edits real
logic so judges watch a plausible change become provably unsafe.)

```powershell
$jar = (Get-ChildItem "$env:USERPROFILE\.vscode\extensions\tlaplus.vscode-ide-*\out\tools\tla2tools.jar" | Select-Object -First 1).FullName

# 1. Prove safe — expect: "No error has been found." (34 states)
java -cp $jar tlc2.TLC -config MC_tianquan.cfg MC_tianquan.tla
```

Then make ONE of these edits in `access_control.tla` and re-run the same command:

**Bug A — "forgot to filter" (obvious).** In `Retrieve`, change
`context' = { r \in candidates : AdmitToContext(r) }` to `context' = candidates`.
→ an over-fetched *denied* resource (r2) reaches the context. INV1 violated.

**Bug B — "clever optimization" / the revocation race (subtle).** In
`AdmitToContext`, change the `ELSE LiveAllowed(r)` line to
`ELSE decisions[r] = "allow"`. → a resource authorized at Decide time but revoked
before Retrieve is served from the stale decision. INV1 violated:

1. `acl: r1→{alice}` — alice may read r1. Search finds it; Decide → **allow**.
2. **Revoke fires — alice removed from r1 — after the decision, before retrieval.**
3. Retrieve trusts the stale "allow" → r1 enters the context though alice can no
   longer read it. Time-of-check/time-of-use leak.

Reset with `git checkout formal/access_control.tla`.

The lesson, proven not just tested: filtering correctly is not enough — you must
re-check the live ACL **at retrieval time**, because permissions can change
between the decision and the read. Tests check the cases you imagined; the model
checker exhaustively found the one you didn't.

> TLC writes a `states/` dir and `*_TTrace_*` files on a run; these are
> generated artifacts and are gitignored.
