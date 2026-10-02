# Demo Runbook — Tianquan 天权

> Step-by-step script for the 5 demo scenarios. All queries and outcomes below
> are verified against the seed data. Run through this once before presenting.

> **Live ADP agent:** The Tianquan agent is published on Tencent Cloud ADP at
> [adp.tencentcloud.com/webim_exp/#/chat/ULzqcG](https://adp.tencentcloud.com/webim_exp/#/chat/ULzqcG).
> Agent name "Tianquan 天权" and welcome message are confirmed visible. Use this
> for the hackathon submission deliverable; the local UI below is for the
> permission-aware demo scenarios.

## Setup (before the demo)

1. **Start the backend** (from the repo root):

   ```powershell
   uvicorn backend.api.app:app --port 8000
   ```

2. **Start the frontend** (from `frontend/`):

   ```powershell
   python -m http.server 5500
   ```

3. Open **http://localhost:5500/** in the browser. Footer should read
   `api: connected`.

> **Important:** the backend holds state in memory (audit chain + ACL changes).
> If you ran Demo 3 (revocation) already, **restart the backend** for a clean
> slate before presenting, so `alice` sees the migration plan again.

The 5 seed personas (top bar): `alice` (engineer), `bob` (contractor),
`charlie` (security_team), `diana` (compliance_officer), plus `jdoe`, `erin`,
`frank`.

---

## Demo 1 — Allowed answer, multi-source

**Point:** the same system unifies four sources and answers with citations,
while still denying what the asker can't see.

1. Select persona **alice**.
2. Ask: *"What is the status of the database migration and were there blockers
   raised in Slack?"*
3. **Expected:** a grounded answer with **8 citations** spanning Confluence,
   Jira, Slack, and GDrive — including `confluence:db-migration-plan`,
   `MIG-231`, `MIG-232`, `slack:db-migration-thread-992`.
4. **Policy inspector:** 8 ALLOW, **2 DENY** — note `confluence:q3-breach-report`
   and `SEC-101` are denied even though they matched the search (alice lacks
   security scope). The LLM never received them.

**Talking point:** "The answer draws from four systems, but two matching
documents were filtered out before the model saw them."

---

## Demo 2 — Negative case, no metadata leak

**Point:** a denied request reveals nothing — not even that the content exists.

1. Select persona **bob** (external contractor).
2. Ask: *"Show me the Q3 security incident report from the breach."*
3. **Expected:** the answer is exactly
   *"I could not find accessible information matching your request."*
   with **no citations**.
4. **Policy inspector:** shows the DENYs (e.g. `confluence:q3-breach-report` →
   `confluence_named_page_no_access:SEC`) — visible to *you* as the operator,
   but never surfaced to the asker.
5. **Audit explorer:** filter `user_id = bob` → the denied attempt is recorded.

**Talking point:** "Bob gets the same message he'd get for a topic that doesn't
exist. He can't tell 'denied' from 'not found' — no side-channel leak. But
compliance can see the denied attempt in the audit trail."

---

## Demo 3 — Live permission revocation

**Point:** revocation takes effect immediately, with no re-index and no
stale-permitted content.

1. Select persona **alice**. Ask: *"database migration plan"*.
   **Expected:** citations include `confluence:db-migration-plan`.
2. In **Revocation Controls**, set:
   - `resource_id`: `confluence:db-migration-plan`
   - `subject`: `engineer`
   - `subject_kind`: `role`
3. Click **REVOKE**.
4. **Expected:** a toast reads **"ACL v1 → v2"**, and the query auto-re-runs.
   `confluence:db-migration-plan` is now **gone** from the citations.
5. (Optional) Click **GRANT** with the same fields to restore it.

**Talking point:** "No reindex. The policy filter re-fetches the live ACL on
every query, so the version bump from v1 to v2 takes effect on the very next
question."

---

## Demo 4 — Audit inquiry (compliance)

**Point:** every decision — allow and deny — is in a tamper-evident trail.

1. Run a few queries as different personas (Demos 1–2 populate the trail).
2. Select persona **diana** (compliance officer) for framing.
3. In the **Audit Explorer**:
   - Filter `resource = payment` (substring) to see all payment-related access.
   - Filter `decision = deny` to see every denial.
4. Click **verify chain** → badge shows **[CHAIN VERIFIED]** with the block
   count.

**Talking point:** "Every retrieval and denial is hash-chained. Change one past
event and verification fails — the audit trail is tamper-evident."

---

## Demo 5 — Formal verification (TLA+)

**Point:** the access-control safety is model-checked, not just implemented.

Run from the `formal/` directory (jar bundled with the TLA+ VS Code extension).

**Option A — PowerShell (recommended):**

```powershell
cd formal
$jar = "C:\Users\Jethro\.vscode\extensions\tlaplus.vscode-ide-2026.9.251644\out\tools\tla2tools.jar"

# SAFE model — all invariants hold.
java -cp $jar tlc2.TLC -config MC_safe.cfg MC_safe.tla

# BROKEN model (filter-after-retrieval) — TLC finds a counterexample.
java -cp $jar tlc2.TLC -config MC_broken.cfg MC_broken.tla
```

**Option B — Git Bash / MINGW64:**

```bash
cd formal
JAR="C:/Users/Jethro/.vscode/extensions/tlaplus.vscode-ide-2026.9.251644/out/tools/tla2tools.jar"

# SAFE model — all invariants hold.
java -cp "$JAR" tlc2.TLC -config MC_safe.cfg MC_safe.tla

# BROKEN model (filter-after-retrieval) — TLC finds a counterexample.
java -cp "$JAR" tlc2.TLC -config MC_broken.cfg MC_broken.tla
```

> **Note:** In Git Bash, `$env:USERPROFILE` is PowerShell syntax and won't
> work. `$USERPROFILE` may also be empty depending on your shell config. The
> simplest fix is to hardcode the path with forward slashes as shown above.
> If the extension version changes, find the jar with:
> `ls "$HOME/.vscode/extensions/tlaplus.vscode-ide-"*/out/tools/tla2tools.jar`

- **Safe:** *"Model checking completed. No error has been found."*
- **Broken:** *"Invariant INV1_RetrievedOnlyIfAuthorized is violated."* with a
  4-step trace: search over-fetches `r2` → policy denies it → but retrieval
  (done before filtering, in the broken variant) puts it in the context anyway.

**Talking point:** "This is the whole thesis in 60 seconds. Flip one flag to put
retrieval before the policy check, and the model checker immediately finds the
leak that pre-LLM filtering prevents."

---

## Reset between runs

Restart the backend (`Ctrl+C`, re-run `uvicorn ...`) to clear the audit chain
and undo any revocations. The frontend needs no restart.
