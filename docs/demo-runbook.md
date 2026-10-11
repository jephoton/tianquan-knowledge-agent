# Demo Runbook — Tianquan 天权

> **This file = the mechanical reference** (every scenario, exact inputs,
> expected outputs, verified against seed data). It is NOT the video script.
>
> **For the video, follow [demo-script.md](demo-script.md)** — one ~4-minute
> narrative using four beats:
>   1. same question, two people (Demos 1 + 2)
>   2. live revocation (Demo 3)
>   3. tamper-evident audit log, edited live (Demo 6)
>   4. formal proof — break the real logic, TLC catches it (Demo 5)
>
> **Repo depth (NOT in the video — mention in one line, keep for judges who dig
> in):** Demo 4 (plain-English audit inquiry), the permissions inspector, and the
> M11–M13 guards (hallucination, freshness, prompt-injection). These are
> strengths to reference verbally, not screen time.

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

4. **Two windows make the denials visible.** A non-privileged persona never
   sees what was denied (that would leak existence). Open a second window as
   **diana** (compliance) on the **Admin** tab: her audit explorer shows each
   query as one group — the question, then every allow/deny decision.

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
4. **In diana's window** (audit explorer): the group *alice asked "What is the
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
4. **In diana's window:** the group *bob asked "Show me the Q3…"* shows every
   decision as DENY — visible to compliance, never surfaced to the asker.
   Or ask the audit trail: *"show denied events for bob"*.

**Talking point:** "Bob gets the same message he'd get for a topic that doesn't
exist. He can't tell 'denied' from 'not found' — no side-channel leak. But
compliance can see the denied attempt in the audit trail."

---

## Demo 3 — Live permission revocation

**Point:** revocation takes effect immediately, with no re-index and no
stale-permitted content.

1. Select persona **alice**. Ask: *"database migration plan"*.
   **Expected:** citations include `confluence:db-migration-plan`.
2. Switch to **frank** (admin) → **Admin** tab → **access control**:
   - `resource_id`: `confluence:db-migration-plan`
   - `subject`: pick `engineer` (role) from the list
3. Click **REVOKE**. **Expected:** toast *"revoke role:engineer on
   confluence:db-migration-plan — ACL v1 -> v2"*. (Optional: look up the
   resource in the **permissions inspector** — alice is no longer an effective
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
4. Each query group shows which allowed documents the answer **cited**
   (`citation [2]`) and which it was given but did **not cite**; the logged answer
   has a `cited:` key mapping every `[n]` to its document (hover a chip to see
   it). The map is hashed with the event, so it is evidence, not a UI guess.
5. The structured filters (user, decision, resource substring, date range) and
   **verify integrity** (badge **[VERIFIED]**) work alongside it.

**Talking point:** "Every retrieval and denial is hash-chained. Change one past
event and verification fails — the audit trail is tamper-evident."

---

## Demo 5 — Formal verification (TLA+): break the real logic, watch it get caught

**Point:** the safety is model-checked, not just tested. We don't flip a switch
labelled "broken" — we make the kind of change a real engineer would make, in
the real retrieval logic, and the model checker proves it introduces a leak and
hands us the exact exploit trace.

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

> Git Bash alt: `JAR="C:/Users/Jethro/.vscode/extensions/tlaplus.vscode-ide-2026.9.251644/out/tools/tla2tools.jar"`

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
*everything* → `r2` lands in the context. *"We didn't filter at all, and the
checker caught the exact document that leaked."*

### Bug B — "the clever optimization" (subtle, impressive — the revocation race)

Revert Bug A, then change the `AdmitToContext` operator's `ELSE` line:

```tla
\* from (correct — re-check live ACL):
ELSE LiveAllowed(r)
\* to (a plausible optimization — "we already decided, why check again?"):
ELSE decisions[r] = "allow"
```

Re-run. **Expect INV1 violated.** Trace (read it aloud):

1. `acl: r1→{alice}` — alice may read r1. Search finds it; Decide → **allow**.
2. **Revoke fires — alice removed from r1 — AFTER the decision, BEFORE retrieval.**
3. Retrieve trusts the stale "allow" → r1 enters the context though alice can no
   longer read it. **Time-of-check / time-of-use leak.**

**Talking point:** "The permission check is simple. What's hard — and what we
proved — is the *timing*. Bug A is the obvious one. Bug B is the one that scares
me: the code *does* filter, it just trusts a decision from a moment ago, and a
concurrent revocation slips through. That's a race no one thinks to unit-test.
The model checker explores every interleaving, found it, and handed us the exact
sequence. For a security control, that's the difference between 'probably safe'
and 'proven safe'. Then I revert — and it's green again."

> **Reset:** `git checkout formal/access_control.tla` restores the correct spec
> instantly after the demo.
> **Fallback:** `MC_safe.*` / `MC_broken.*` run the safe/broken variants without
> editing, and the traces above can be shown as a slide if a live run is risky.

---

## Demo 6 — Tamper-evident audit log (real file edit)

**Point:** the audit trail is hash-chained and persisted to a real file on
disk. An insider editing that file to cover their tracks is detectable — we
don't trust memory, we re-hash the file itself.

**Setup:** the backend writes every decision to `audit_log.json` in the repo
root as it happens. Run a couple of queries first (Demos 1–2 populate it).

1. As **frank** (admin) or **diana** (compliance), in the **Audit Explorer**
   click **verify integrity**.
   **Expected:** badge **[VERIFIED]**, toast "log file verified — chain
   intact".
2. **The attack — do it live:** open `audit_log.json` in your editor. Find a
   `"decision": "deny"` event and change it to `"allow"` (an insider hiding
   that they were denied access). Save the file.
3. Click **verify integrity** again.
   **Expected:** badge turns red **[TAMPERED]**, toast "LOG FILE TAMPERED
   at event #N: tampered_event_at_N:hash_mismatch". The question and answer
   text are hashed too, so editing what someone asked is caught the same way.

**Talking point:** "Every decision is written to disk, and each event's hash
includes the previous event's hash — a blockchain over the audit log. Watch: I'll
play a malicious admin and edit the log file directly to turn a DENY into an
ALLOW. Re-verify — and it's caught at the exact event, because the recomputed
hash no longer matches. You cannot quietly rewrite history. That's what makes
this legally defensible for a regulator."

> This re-reads and re-hashes the actual file (`/audit/verify-file`), so the
> edit is caught no matter how it was made. **Reset:** restart the backend (or
> delete `audit_log.json`) to start a fresh clean log.


---

## Source preview and download (export-capable personas)

**Point:** reading a raw source is treated as exporting it.

1. As **charlie** (security_team) ask *"What happened in the payment outage and
   how was it fixed?"*, then click a citation card or an inline `[n]` marker.
2. **Expected:** the source preview shows the full content and its origin link;
   **download ↓** saves it. alice and bob (no `export`) see citation cards but
   no preview.
3. In the audit explorer the view appears as *charlie opened a source preview*.
   A denied or nonexistent resource returns the same 404 and is audited too.

---

## Reset between runs

Restart the backend (`Ctrl+C`, re-run `uvicorn ...`) to clear the audit chain
and undo any revocations. The frontend needs no restart.
