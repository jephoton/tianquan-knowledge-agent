# Formal Specification — Tianquan 天权

TLA+ specification of the permission-aware retrieval access-control model.

<!-- Generated scope/command reconciliation, 2026-10-11. -->

TLC exhaustively explores the configured finite model, not all executions of
the Python app. No verified refinement or implementation-level proof exists.

## Files

- `access_control.tla` — the specification (query lifecycle state machine).
- **`MC_tianquan.tla` / `MC_tianquan.cfg` — the demo harness.** Show these
  alongside the specification and prepared TLC output. The optional live demo
  edits `AdmitToContext` in the spec; fixed safe/broken backups also exist.
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

The optional demo edits the abstract retrieval rule, and TLC finds a
counterexample within the configured model. This does not edit Python code. (The `BROKEN` constant still exists so
the `MC_safe`/`MC_broken` harnesses run automatically, but the *demo* edits real
logic so judges watch a plausible change become provably unsafe.)

From the `formal/` directory, with Java 17+ on PATH and the VS Code TLA+
extension installed:

```powershell
$jar = (Get-ChildItem "$env:USERPROFILE\.vscode\extensions\tlaplus.vscode-ide-*\out\tools\tla2tools.jar" | Select-Object -First 1).FullName

# 1. Check safe — expect: "No error has been found."
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

Undo only the deliberate spec edit in the editor, then rerun TLC. Avoid
restoring the whole file if it contains unrelated changes.

The model demonstrates why a live permission check is needed at context
admission rather than trusting an earlier decision. Python uses a live ACL
filter and separate context assembly; concurrency and missing-ACL gaps are
recorded in [current state](../docs/current-state.md#known-boundaries-and-follow-ups).
The six modeled invariants exclude INV5 (deferred) and INV8 (Python-only
lexical grounding).

> TLC writes a `states/` dir and `*_TTrace_*` files on a run; these are
> generated artifacts and are gitignored.

## Fixed harnesses (no spec edits)

From `formal/`, with `$jar` set as above:

```powershell
java -cp $jar tlc2.TLC -config MC_safe.cfg MC_safe.tla
java -cp $jar tlc2.TLC -config MC_broken.cfg MC_broken.tla
```

The safe configuration should complete with no error. The broken configuration intentionally reports an invariant violation; that result is expected and is not a passing safe-model check. State counts depend on the exact harness/model revision and should be taken from the current run.
