# Formal verification — how Tianquan proves its permission design is safe

<!-- Generated plain-language rewrite, 2026-10-12. Commands and results verified by running TLC. -->

**In one sentence:** this folder contains a precise description of how Tianquan
handles a question, and a tool that checks **every possible order of events**
to make sure no document ever reaches the AI unless the person asking is
allowed to see it *right now*.

---

## 1. Formal verification in plain words

Normal testing is like test-driving a car on a few roads. If it never breaks
down, that's good evidence — but you only learn about the roads you drove.

Formal verification works more like checking a map of **every** road. You
write down exactly how the system behaves as a small set of states and steps
(the *model*), write down the promises it must always keep (the *rules*), and
a tool called a **model checker** walks through every reachable state and
every possible order of steps. If any order breaks a rule, it shows you the
exact sequence of events that did it. If none does, the rule holds for every
order the model allows.

Tianquan's model is written in **TLA+**, a language for describing systems
step by step, and checked with **TLC**, its model checker.

**Why bother?** The hardest bugs in security systems are *timing* bugs: two
things happen at nearly the same moment, in an unlucky order. Testing rarely
hits the unlucky order. A model checker tries all of them.

## 2. What the model describes

The model follows the life of **one question** through Tianquan, the same
steps the real app takes:

```
 ask ──► search ──► permission check ──► admit documents ──► answer
                                          into the AI's view     (with citations)

 …and at any moment before documents are admitted,
    an admin can REVOKE someone's access.
```

| Step | What happens | In the real app |
|---|---|---|
| **Search** | Finds candidate documents. It may find documents the person *can't* see — search is just a suggestion. | `backend/retrieval/candidate_search.py` deliberately over-fetches |
| **Permission check** | Records allow/deny for each candidate, and logs every decision. | The policy engine; every decision goes to the audit trail |
| **Revoke** (any time) | An admin removes someone's access. | The **Revoke** button in the Admin tab |
| **Admit to AI's view** | Chooses which documents the AI is allowed to read. **This is the safety-critical step.** | `backend/retrieval/permission_filter.py` re-reads the *current* permissions |
| **Answer** | The AI answers and cites documents. | Citations are checked against what the AI was given |

To keep checking exhaustive, the model is deliberately small: 2 people (alice
and bob) and 2 documents (r1, which alice may read, and r2, which only bob
may read), with alice asking. That is enough to contain every kind of
situation that matters — a document she can see, one she can't, and one she
*could* see until it was revoked.

## 3. The promises we check

TLC checks these six rules in every reachable state:

| Rule | In plain words | What it protects in Tianquan |
|---|---|---|
| **Retrieved only if authorized** | A document in the AI's view is one the asker is allowed to see **right now**. | No answer is built from a document you can't access |
| **The AI sees only permitted content** | The AI's input never contains a forbidden document. | "The LLM cannot leak what it never receives" |
| **Revoked access can't be reused** | Once access is revoked, that document never enters the AI's view afterwards. | Off-boarding or pulling a clearance takes effect on the very next question |
| **Every decision is logged** | Every allow and every deny is recorded. | The audit trail is complete — compliance sees denials too |
| **No unauthorized citations** | The answer can only cite documents that were in the AI's view and still permitted. | Citations never point to something you can't open |
| **Denials don't leak** | A denied document never appears in the AI's view or the citations. | A contractor can't learn that a restricted report exists |

(In the files these are `INV1`–`INV4`, `INV6` and `INV7`. Two more rules from
the original plan aren't in the model: `INV5`, about an AI "action agent"
that was dropped from the project, and `INV8`, the sentence-by-sentence
grounding check, which is tested in Python instead.)

## 4. The bug it catches: trusting a stale permission

The most important thing the model shows is **why Tianquan re-checks
permissions at the moment documents are admitted**, instead of reusing the
answer it got a moment earlier.

Picture the "obvious optimization" a developer might make: *"We already
checked the permissions during the permission-check step — why check again?"*
TLC proves that version is unsafe and prints the exact sequence that breaks
it. Running the broken variant gives this 5-step counterexample:

| # | What happens | Alice may read r1? | Recorded decision for r1 | In the AI's view |
|---|---|---|---|---|
| 1 | Start | ✅ yes | — | nothing |
| 2 | Search finds r1 | ✅ yes | — | nothing |
| 3 | Permission check: **allow** | ✅ yes | allow | nothing |
| 4 | **Admin revokes alice's access to r1** | ❌ **no** | allow *(now stale)* | nothing |
| 5 | Documents admitted using the old "allow" | ❌ no | allow | **r1 — leaked** ❌ |

The problem is the **order**: a permission check, then a revocation, then
documents admitted on the strength of the out-of-date check. This is a classic
*time-of-check vs time-of-use* bug.

The correct design — the one Tianquan uses — re-checks the **current**
permission at the moment of admission, so at step 5 r1 is refused. TLC
explores every ordering of search, check, revoke and admit, and finds **no
sequence** in which a document gets into the AI's view on a permission that
has gone stale.

### How this shows up in the real app

- **Live revocation.** When an admin revokes access, the person's very next
  question already excludes the document — no re-indexing — because the
  permission filter reads current permissions for every candidate document,
  every time.
- **Search can over-fetch safely.** Search is allowed to suggest restricted
  documents, because nothing reaches the AI without passing the live check.
  The model includes this deliberately: r2 can show up in alice's search
  results and is still never admitted.
- **Denials stay invisible.** A denied document never reaches the AI or the
  citations, which is why Bob gets the same "could not find" message whether
  a restricted report exists or not.
- **Complete audit trail.** Every candidate decision is logged, which is what
  lets compliance see the denials in the audit explorer.

## 5. What this does — and doesn't — prove

**It does show** that Tianquan's access-control *design* keeps all six
promises in every ordering of events the model allows, and that the
"reuse the earlier check" shortcut is genuinely unsafe.

**It doesn't** mechanically prove the Python code itself. The model is a
simplified description of the design (2 people, 2 documents, one question at
a time). The Python implementation is tested separately against the same
promises — 294 automated tests — and its known limits are listed in
[current state](../docs/current-state.md#known-boundaries-and-follow-ups).
That's the normal, practical way formal methods are used: verify the design
where the subtle bugs live, then test the code against it.

---

## Run it yourself

You need Java 17+ and the TLA+ tools (installed with the VS Code **TLA+**
extension). From this `formal/` folder:

```powershell
$jar = (Get-ChildItem "$env:USERPROFILE\.vscode\extensions\tlaplus.vscode-ide-*\out\tools\tla2tools.jar" | Select-Object -First 1).FullName

# The correct design — expect "Model checking completed. No error has been found."
java -cp $jar tlc2.TLC -config MC_safe.cfg MC_safe.tla

# The "reuse the earlier check" shortcut — expect "Invariant INV1_RetrievedOnlyIfAuthorized is violated"
# plus the 5-step sequence shown above.
java -cp $jar tlc2.TLC -config MC_broken.cfg MC_broken.tla
```

Git Bash: `JAR=$(ls "$HOME"/.vscode/extensions/tlaplus.vscode-ide-*/out/tools/tla2tools.jar | head -1)`,
then `java -cp "$JAR" tlc2.TLC -config MC_safe.cfg MC_safe.tla`.

On the current model the safe check explores **34 distinct states** and finds
no error. The broken check fails on step 5 of the sequence above.

### Live demo: break it yourself

`MC_tianquan.tla` / `MC_tianquan.cfg` is the demo harness. Run it once
(`... -config MC_tianquan.cfg MC_tianquan.tla`) → no error. Then make **one**
edit in `access_control.tla` and run it again:

- **The race (recommended).** In `AdmitToContext`, change
  `ELSE LiveAllowed(r)` to `ELSE decisions[r] = "allow"` — "reuse the earlier
  decision". → the stale-permission leak above.
- **Forgot to filter.** In `Retrieve`, change
  `context' = { r \in candidates : AdmitToContext(r) }` to
  `context' = candidates`. → a document alice was never allowed (r2) reaches
  the AI.

Undo the edit afterwards and re-run to see it pass again.

## Files

| File | What it is |
|---|---|
| `access_control.tla` | The model: the steps of a question and the six rules |
| `MC_safe.tla` / `.cfg` | Runs the correct design |
| `MC_broken.tla` / `.cfg` | Runs the "reuse the earlier check" shortcut, to show the leak |
| `MC_tianquan.tla` / `.cfg` | Demo harness for editing the rule live |
| `run_tlc.sh` | Helper script to run TLC from Git Bash |

TLC writes a `states/` folder and `*_TTrace_*` files when it runs; they're
generated output and are git-ignored.
