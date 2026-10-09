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

## Demo 5 — Formal verification (TLA+), live flip

**Point:** the access-control safety is model-checked, not just tested — and the
checker finds a race condition unit tests would miss.

Run from the `formal/` directory (jar bundled with the TLA+ VS Code extension).
Use the single demo harness `MC_tianquan.tla`.

```powershell
cd formal
$jar = (Get-ChildItem "$env:USERPROFILE\.vscode\extensions\tlaplus.vscode-ide-*\out\tools\tla2tools.jar" | Select-Object -First 1).FullName

# STEP 1 — run as-is (BROKEN = FALSE). Expect: "No error has been found." (34 states)
java -cp $jar tlc2.TLC -config MC_tianquan.cfg MC_tianquan.tla
```

**STEP 2 — the live edit (the demo moment):** open `MC_tianquan.tla`, find the
line `BROKEN <- FALSE` near the bottom, change it to `BROKEN <- TRUE`, save.

```powershell
# STEP 3 — re-run the SAME command. Expect: "Invariant INV1 ... is violated." + trace.
java -cp $jar tlc2.TLC -config MC_tianquan.cfg MC_tianquan.tla
```

> Git Bash alt: `JAR="C:/Users/Jethro/.vscode/extensions/tlaplus.vscode-ide-2026.9.251644/out/tools/tla2tools.jar"`
> then `java -cp "$JAR" tlc2.TLC -config MC_tianquan.cfg MC_tianquan.tla`.
> Remember to flip `BROKEN` back to `FALSE` after the demo.

**What the counterexample shows (read it aloud):**

1. `acl: r1→{alice}` — alice may read r1. Search finds it.
2. Decide → r1 = **allow** (correct at that instant).
3. **Revoke fires — alice removed from r1 — after the decision, before retrieval.**
4. The naive retrieve trusts the stale "allow" and puts r1 in the context →
   **INV1 violated: alice's context now holds a resource she can no longer read.**

**Talking point:** "The permission check itself is simple. What's hard — and
what we proved — is that *filtering correctly isn't enough*. If you trust the
permission decision from a moment ago, a concurrent revocation leaks the content.
You must re-check the live ACL at retrieval time. Unit tests check the cases you
imagined; the model checker exhaustively found the race we didn't. One flag flip,
and it hands you the exact exploit trace."

> Fallback if a live run is risky: `MC_safe.*` and `MC_broken.*` are fixed
> variants you can run without editing, and the counterexample trace above can
> be shown as a slide.

---

## Demo 6 — Tamper-evident audit log (real file edit)

**Point:** the audit trail is hash-chained and persisted to a real file on
disk. An insider editing that file to cover their tracks is detectable — we
don't trust memory, we re-hash the file itself.

**Setup:** the backend writes every decision to `audit_log.json` in the repo
root as it happens. Run a couple of queries first (Demos 1–2 populate it).

1. As **frank** (admin) or **diana** (compliance), in the **Audit Explorer**
   click **verify log file**.
   **Expected:** badge **[CHAIN VERIFIED]**, toast "log file verified — chain
   intact".
2. **The attack — do it live:** open `audit_log.json` in your editor. Find a
   `"decision": "deny"` event and change it to `"allow"` (an insider hiding
   that they were denied access). Save the file.
3. Click **verify log file** again.
   **Expected:** badge turns red **[CHAIN TAMPERED]**, toast "LOG FILE TAMPERED
   at event #N: tampered_event_at_N:hash_mismatch".

**Talking point:** "Every decision is written to disk, and each event's hash
includes the previous event's hash — a blockchain over the audit log. Watch: I'll
play a malicious admin and edit the log file directly to turn a DENY into an
ALLOW. Re-verify — and it's caught at the exact event, because the recomputed
hash no longer matches. You cannot quietly rewrite history. That's what makes
this legally defensible for a regulator."

> This re-reads and re-hashes the actual file (`/audit/verify-file`), so the
> edit is caught no matter how it was made. **Reset:** restart the backend (or
> delete `audit_log.json`) to start a fresh clean log.
>
> There is also an in-memory **verify (memory)** button for a quick check that
> doesn't involve the file.

---

## Demo 7 — Real-time data ingestion (upload connector)

**Point:** the organiser noted that real (non-mock) data would be better. This
demo shows the system ingesting a document at runtime — no code changes, no
seed file. The document is immediately searchable and permission-filtered.

1. In the **Admin tab**, scroll to **Document Upload**.
2. Fill in:
   - `resource_id`: `upload:q4-incident`
   - `title`: `Q4 Production Incident Report`
   - `content`: *(paste any text — e.g. a real incident report, meeting notes,
     or a log summary)*
   - `allowed_roles`: *(leave blank for default, or restrict e.g.
     `admin,security_team`)*
3. Click **[UPLOAD & INDEX]**.
   **Expected:** toast reads "uploaded: Q4 Production Incident Report — N
   indexed resources."
4. Switch to **Query tab**, select persona **alice**.
5. Ask: *"What happened in the Q4 production incident?"*
   **Expected:** the uploaded document appears in the citations with source
   `upload`, and the answer draws from it.
6. Switch to persona **bob** (contractor).
7. Ask the same question.
   **Expected:** if you restricted roles to `admin,security_team`, bob gets
   *"could not find accessible information"* — the upload connector honours
   the permission model just like Confluence/Jira/Slack.

**Talking point:** "This isn't mock data — I just pasted that document in
during the demo. The system ingested it, indexed it, and the permission filter
applied the same ACL checks as it does for Confluence or Jira. In production,
this connector would be replaced by real OAuth integrations to Google Drive,
Slack, Jira — same architecture, same permission boundary."

**How this maps to real integrations:**
- The `UploadConnector` implements the same `BaseConnector` interface as
  `ConfluenceConnector`, `JiraConnector`, etc.
- A real integration would swap `list_resources()` to call the Google Drive
  API, Slack API, etc., and `check_membership()` to query the source's native
  permission model.
- The permission filter, audit chain, and LLM answer agent are unchanged —
  they work against the interface, not the implementation.

---

## Reset between runs

Restart the backend (`Ctrl+C`, re-run `uvicorn ...`) to clear the audit chain
and undo any revocations. The frontend needs no restart.
