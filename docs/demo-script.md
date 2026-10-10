# Demo Script — Tianquan 天权 (≈4 minutes)

> The *narration* for the live demo — what to say and show, in order, to land
> the story. For the mechanical click-by-click steps and exact inputs, see
> [demo-runbook.md](demo-runbook.md). Rehearse this until the arc is muscle
> memory; the arc is what wins, not the feature count.

**One-line pitch:** *Auditable AI answers that never overstep access rights.*

---

## 0. The hook (20s, no screen — just say it)

> "An AI assistant over all your company's knowledge is incredible — until a
> contractor asks it for your biggest client's default risk, and it helpfully
> answers from a document they were never allowed to see. In most industries
> that's a bug. In regulated finance it's a reportable breach. The AI wasn't
> hacked — the access control was just never there. That's the problem
> Tianquan solves."

Transition: *"The core idea is one sentence —"* → show the tagline.

> **"The LLM cannot leak what it never receives."** We filter by permission
> *before* the model sees anything.

---

## 1. The same question, two people (Demo 1 + 2) — 60s

**As Alice (engineer):** ask *"What's the status of the database migration and
were there blockers raised in Slack?"*

> "Alice gets a real answer, drawn from four systems — Jira, Slack, Confluence,
> Drive — with citations. But look at the policy inspector: two documents that
> *matched* her question were **denied** — the confidential Q3 breach report
> and a security ticket. The model never received them. It can't leak what it
> never got."

**Switch to Bob (contractor):** ask *"Show me the Q3 security incident report
from the breach."*

> "Same system, different person. Bob gets: *'I could not find accessible
> information.'* Now — the key part — that's the **exact same message** he'd get
> for a topic that doesn't exist. He can't tell 'denied' from 'not found.' No
> confirmation the document exists. No side channel. The denial is in the audit
> log for compliance, but nothing leaks to Bob."

Transition: *"Permissions aren't static, though —"*

---

## 2. Live revocation (Demo 3) — 30s

> "Say we off-board someone or pull a clearance." As **admin**, revoke a role/
> user from a resource Alice was citing. Show the ACL version bump (v1 → v2).
> Re-ask Alice's question.

> "No reindex, no restart — the next query already reflects it. The filter
> re-fetches the live permission every time. And that 'every time' turns out to
> matter more than you'd think — hold that thought."

---

## 3. The audit log is tamper-evident — for real (Demo 6) — 45s

> As compliance (**diana**/**frank**), click **verify log file** → green,
> intact.

> "Every decision is written to a real file on disk, hash-chained — each entry
> commits to the hash of the one before it. Watch me play a malicious admin."

**Open `audit_log.json` in the editor, change a `deny` to `allow`, save.** Click
**verify log file** again → red, **tampered at event #N**.

> "I edited the log directly to hide that someone was denied. Re-verify — caught
> at the exact event, because the recomputed hash no longer matches. You cannot
> quietly rewrite history. *This* is the artifact a regulator asks for."

---

## 4. The payoff: we didn't test it, we proved it (Demo 5) — 60s

> "Everything so far, you could demo. Here's what you can't fake." Open the
> terminal, run TLC on the spec → **no error, all invariants hold.**

> "This model-checks every possible ordering of the pipeline. Now watch me make
> the mistake a real engineer would make." In `access_control.tla`, edit the
> real retrieval rule — change `ELSE LiveAllowed(r)` (re-check the live
> permission) to `ELSE decisions[r] = "allow"` ("we already decided, why check
> again?"). Save, re-run.

> **"Invariant violated."** Read the trace aloud: "A document is authorized when
> the policy runs. Then — before it's retrieved — the user is revoked. This
> 'optimized' code trusts the earlier decision and serves it anyway. That's a
> race condition. I didn't flip a switch labelled 'broken' — I made a change
> that looks like a reasonable optimization, and the model checker proved it
> leaks, with the exact sequence as evidence. Tests check the cases you
> imagined; this checks the ones you didn't. For a security control that's the
> difference between 'probably safe' and 'proven safe.'" Then `git checkout` the
> file — green again.

---

## 5. Close (15s)

> "Tianquan: an internal AI brain that answers from four systems, respects every
> source's native permissions, proves it with formal methods, and logs it so a
> regulator can verify it. The LLM cannot leak what it never receives — and we
> can prove it never receives it. That's what makes AI deployable in finance."

---

## Timing / fallbacks

- Total ≈ 4 min. If cut to 2: do sections 1, 3, 4 (skip revocation + close short).
- **TLA+ fallback:** if the live flip is risky on the day, pre-record the two
  runs or screenshot the counterexample trace — still lands.
- **Reset between runs:** restart the backend (clears audit log + ACL changes);
  flip `BROKEN` back to `FALSE` in `MC_tianquan.tla`.
- Have the backend (`uvicorn ... :8000`) and frontend (`:5500`, use
  `127.0.0.1`) already running before you start.
