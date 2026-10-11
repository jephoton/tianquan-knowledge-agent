# Demo Runbook — Tianquan 天权

> **This file = the mechanical reference** (every scenario, exact inputs,
> expected outputs, verified against seed data). It is NOT the video script.
>
> **For the video, follow [demo-script.md](demo-script.md)**. After the introduction and
> architecture diagram, enter the UI and toggle clean mode; show the unified answer, Bob's denial and Charlie's permitted access,
> source preview/export and missing Q5 report; then revocation, audit and formal
> assurance. Finish with the outro and reflection.
>
> **Live ADP agent:** The Tianquan agent is published on Tencent Cloud ADP at
> [adp.tencentcloud.com/webim_exp/#/chat/ULzqcG](https://adp.tencentcloud.com/webim_exp/#/chat/ULzqcG).
> The backend calls it with each query's permission-filtered context. The agent
> must have **no knowledge base attached**: anything in its knowledge base
> bypasses Tianquan's permission filter, both on the public link and on backend
> calls.

## Setup (before the demo)

1. **Start the backend** (from the repo root):

   ```powershell
   uvicorn backend.api.app:app --port 8000
   ```

2. **Start the frontend** (from `frontend/`):

   ```powershell
   python -m http.server 5500
   ```

3. Open **http://127.0.0.1:5500/** in the browser. Footer should read
   `api: connected`. The page needs no internet access (Tailwind is vendored);
   the live LLM does — without it, answers fall back to the offline extractive
   summarizer.

4. **Switch to diana to show denials.** A non-privileged persona never sees
   what was denied (that would leak existence). After a query, switch to
   **diana** (compliance) → **Admin** tab: her audit explorer shows each query
   as one group — the question, then every allow/deny decision. Switching
   persona clears the query box; the example chips re-run a question in one
   click.

> **Important:** the backend holds state in memory (audit chain + ACL changes).
> If you ran Demo 3 (revocation) already, **restart the backend** for a clean
> slate before presenting, so `alice` sees the migration plan again.

The 7 seed personas (top bar): `alice` (engineer), `bob` (contractor),
`charlie` (security_team), `diana` (compliance_officer), `jdoe`
(senior_engineer), `erin` (finance_analyst), `frank` (admin).

---

## Demo 1 — Allowed answer, multi-source

**Point:** the same system unifies four sources and answers with citations,
while still denying what the asker can't see.

1. Select persona **alice**.
2. Ask: *"What is the status of the database migration and were there blockers
   raised in Slack?"*
3. **Expected:** a grounded answer citing `slack:db-migration-thread-992`,
   `confluence:db-migration-plan`, `MIG-231` and `MIG-232` (the live LLM
   usually cites four; the offline fallback cites every allowed source). Click
   an inline `[n]` marker to jump to its citation card.
4. **Switch to diana** → Admin (audit explorer): the group *alice asked "What is the
   status…"* shows **8 allow / 2 deny** — `confluence:q3-breach-report` and
   `SEC-101` matched the search but were denied (alice lacks security scope).
   The LLM never received them.

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
4. **Switch to diana** → Admin: the group *bob asked "Show me the Q3…"* shows every
   decision as DENY — visible to compliance, never surfaced to the asker.
   Or ask the audit trail: *"show denied events for bob"*.

**Talking point:** "Bob gets the same message he'd get for a topic that doesn't
exist. He can't tell 'denied' from 'not found' — no side-channel leak. But
compliance can see the denied attempt in the audit trail."

---

## Demo 2b — Charlie: allowed report, preview/export, missing report

1. Switch to **charlie** and repeat Bob's exact question:
   *“Show me the Q3 security incident report from the breach.”*
2. **Expected:** a cited answer including `confluence:q3-breach-report`.
3. Open the report's citation in the source viewer; show full content and the
   origin link, then click **download ↓**. Charlie has both read access and
   export permission. The preview and export are audited.
4. Still as Charlie ask *“Show me the Q5 report.”*
5. **Expected:** *“I could not find accessible information matching your request.”*
   with no citations — identical to Bob's inaccessible Q3 response.

---

## Demo 3 — Live permission revocation

**Point:** revocation takes effect immediately, with no re-index and no
stale-permitted content.

1. Select persona **alice**. Ask: *"database migration plan"*.
   **Expected:** citations include `confluence:db-migration-plan`.
2. Switch to **frank** (admin) → **Admin** tab → **access control**:
   - `resource_id`: `confluence:db-migration-plan`
   - `subject`: pick `engineer` (role) from the list
3. Click **REVOKE**. **Expected:** inline status *"revoke role:engineer on
   confluence:db-migration-plan — ACL v1 -> v2"*. (Optional: look up the
   resource in the **permissions inspector** and click **refresh** — alice is no longer an effective
   reader.)
4. Switch back to **alice** and ask the same question again. There is no
   auto re-run: an admin change and a user's query are separate actions.
   **Expected:** `confluence:db-migration-plan` is now **gone** from the
   citations.
5. (Optional) **GRANT** with the same fields restores it.

**Talking point:** "No reindex. The policy filter re-fetches the live ACL on
every query, so the version bump from v1 to v2 takes effect on the very next
question."

---

## Demo 4 — Audit inquiry (compliance)

**Point:** every decision — allow and deny — is in a tamper-evident trail.

1. Run a few queries as different personas (Demos 1–2 populate the trail).
2. Select persona **diana** (compliance officer) → **Admin** tab.
3. In **ask the audit trail**, try:
   - *"who retrieved the q3 breach report"* → resolves to
     `confluence:q3-breach-report`.
   - *"what did alice access in the ENG confluence space"*.
   - The handbook's example, *"Show me everything user jdoe accessed related to
     the payment-gateway Confluence space in the last 30 days"* — the seed data
     has no `payment-gateway` space, and the search **says so** and falls back
     to Confluence pages about it (`confluence:payment-runbook`).

   The line under the box shows exactly what was understood; anything it could
   not map is listed in amber rather than silently ignored.
4. Revokes and grants appear in the same history (amber **CHANGE** rows: who,
   what, ACL version). Each query group shows which allowed documents the answer **cited**
   (`citation [2]`) and which it was given but did **not cite**; the logged answer
   has a `cited:` key mapping every `[n]` to its document (hover a chip to see
   it). The map is hashed with the event, so it is evidence, not a UI guess.
5. Asking in plain English **fills the filter fields** (user, decision,
   resource ids, date range) with what it understood; edit any field to refine.
   The integrity badge is re-checked on every refresh.

**Talking point:** "Every retrieval and denial is hash-chained. Change one past
event and verification fails — the audit trail is tamper-evident."

---

## Demo 5 — Formal verification (TLA+): break the real logic, watch it get caught

**Point:** the safety is model-checked, not just tested. I don't flip a switch
labelled "broken" — I make the kind of change a real engineer would make, in
the real retrieval logic, and the model checker proves it introduces a leak and
hands me the exact exploit trace.

**The one line that matters** is `AdmitToContext(r)` in
`formal/access_control.tla` — the rule deciding whether a candidate enters the
LLM context. Correct version:

```tla
AdmitToContext(r) == ... ELSE LiveAllowed(r)    \* re-check the LIVE ACL at retrieval
```

**Setup — one time:**

```powershell
cd formal
$jar = (Get-ChildItem "$env:USERPROFILE\.vscode\extensions\tlaplus.vscode-ide-*\out\tools\tla2tools.jar" | Select-Object -First 1).FullName
```

> Git Bash alt: `JAR=$(ls "$HOME"/.vscode/extensions/tlaplus.vscode-ide-*/out/tools/tla2tools.jar | head -1)`

**STEP 1 — prove it's safe:**

```powershell
java -cp $jar tlc2.TLC -config MC_tianquan.cfg MC_tianquan.tla
# Expect: "Model checking completed. No error has been found." (34 states)
```

**STEP 2 — the live edit. Two bugs you can inject (pick one, or escalate from A
to B). Both are edits to real logic, not a flag.**

### Bug A — "I forgot to filter" (obvious, relatable)

In `access_control.tla`, change the `Retrieve` action's context line:

```tla
\* from:
context' = { r \in candidates : AdmitToContext(r) }
\* to (an engineer who forgot the filter):
context' = candidates
```

Re-run STEP 1's command. **Expect INV1 violated.** Trace: search over-fetches
`r2` (a doc the asker can't see) → Decide marks it **deny** → but Retrieve admits
*everything* → `r2` lands in the context. *"This version didn't filter at all, and the
checker caught the exact document that leaked."*

### Bug B — "the clever optimization" (subtle, impressive — the revocation race)

Revert Bug A, then change the `AdmitToContext` operator's `ELSE` line:

```tla
\* from (correct — re-check live ACL):
ELSE LiveAllowed(r)
\* to (a plausible optimization — "it was already decided, why check again?"):
ELSE decisions[r] = "allow"
```

Re-run. **Expect INV1 violated.** Trace (read it aloud):

1. `acl: r1→{alice}` — alice may read r1. Search finds it; Decide → **allow**.
2. **Revoke fires — alice removed from r1 — AFTER the decision, BEFORE retrieval.**
3. Retrieve trusts the stale "allow" → r1 enters the context though alice can no
   longer read it. **Time-of-check / time-of-use leak.**

**Talking point:** "The permission check is simple. What's hard — and what I
proved — is the *timing*. Bug A is the obvious one. Bug B is the one that scares
me: the code *does* filter, it just trusts a decision from a moment ago, and a
concurrent revocation slips through. That's a race no one thinks to unit-test.
The model checker explores every interleaving, found it, and handed me the exact
sequence. For a security control, that's the difference between 'probably safe'
and 'proven safe'. Then I revert — and it's green again."

> **Reset:** `git checkout formal/access_control.tla` restores the correct spec
> instantly after the demo.
> **Fallback:** `MC_safe.*` / `MC_broken.*` run the safe/broken variants without
> editing, and the traces above can be shown as a slide if a live run is risky.

---

## Demo 6 — Tamper-evident audit log (real file edit)

**Point:** the audit trail is hash-chained and persisted to a real file on
disk. An insider editing that file to cover their tracks is detectable — the
check doesn't trust memory, it re-hashes the file itself on every refresh.

**Setup:** the backend appends every decision to `audit_log.jsonl` in the repo
root as it happens (one JSON event per line; earlier lines are never
rewritten). Run a couple of queries first (Demos 1–2 populate it).

1. As **frank** (admin) or **diana** (compliance), open the **Audit Explorer**.
   **Expected:** badge **[VERIFIED]** — integrity is re-checked automatically
   on every refresh (filter change, new query, refresh button, or returning to
   the browser window).
2. **The attack — do it live:** open `audit_log.jsonl` in your editor. Find a
   `"decision": "deny"` event and change it to `"allow"` (an insider hiding
   that they were denied access). Save the file.
3. Switch back to the browser (or click **refresh** / change any filter).
   **Expected:** badge turns red **[TAMPERED · event #N]** with the failing event identified in the badge. It stays red whatever the
   filters **and** after new queries — the log is append-only, so the edit is
   never written over. The question, answer text and citation map are hashed
   too, so editing any of them is caught the same way; deleting the newest
   lines is caught as a truncated log.

**Talking point:** "Every decision is written to disk, and each event's hash
includes the previous event's hash — a blockchain over the audit log. Watch: I'll
play a malicious admin and edit the log file directly to turn a DENY into an
ALLOW. Re-verify — and it's caught at the exact event, because the recomputed
hash no longer matches. You cannot quietly rewrite history. That's what makes
this legally defensible for a regulator."

> This re-reads and re-hashes the actual file (`/audit/verify-file`), so the
> edit is caught no matter how it was made. **Reset:** restart the backend (or
> delete `audit_log.jsonl`) to start a fresh clean log.


---

## Reset between runs

Restart the backend (`Ctrl+C`, re-run `uvicorn ...`) to clear the audit chain
and undo any revocations. The frontend needs no restart.
