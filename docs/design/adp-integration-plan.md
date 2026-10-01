# ADP Integration Plan

> Implementing Tencent Cloud Agent Development Platform (ADP) as the live LLM
> backend for Tianquan (天权). Per `docs/ADP_Hackathon_Guide_EN.pdf`, ADP is the
> recommended way to build agents on Tencent Cloud for this hackathon.

## What's already done

The adapter code is written and tested:

- `backend/agents/adp_client.py` — `ADPClient` implementing `LLMClient` protocol
- `backend/api/state.py` — auto-selects `ADPClient` if `ADP_APP_KEY` env var is set, else `StubLLMClient`
- `backend/api/app.py` — `/health` endpoint reports `adp` or `stub`
- `tests/test_adp_client.py` — 5 tests (protocol, key check, SSE parsing, empty fallback, payload)
- `requirements.txt` — `requests==2.32.5` added

The adapter sends Tianquan's permission-filtered context as part of the
question to the ADP agent, which streams an SSE response. The client
accumulates text chunks and returns the final answer.

## What's left to do

### Step 1: Register on ADP (manual, ~10 min)

1. Visit the Tencent Cloud ADP international edition landing page.
2. Register an individual account (email + password + date of birth).
3. Skip company info / card binding (individual accounts don't need it).
4. Open "App Dev" and create a new agent.

Reference: ADP guide §3 (pages 4-5).

### Step 2: Build the Tianquan agent on ADP (manual, ~15 min)

1. **Create a new application** — choose "Start Free Trial" for a blank agent.
2. **Configure the agent:**
   - Name: "Tianquan 天权"
   - Welcome message: "Tianquan (天权) ready. Ask about your enterprise knowledge."
   - Model: DeepSeek (included in free allowance)
3. **Upload the seed knowledge base** (optional — Tianquan sends its own
   filtered context with each query, but uploading seed docs gives the ADP
   agent background for the "no access" case where context is empty):
   - `backend/seed/` — the 20 mock resources as plain text
   - This is a "nice to have" — the primary knowledge path is Tianquan's
     own permission-filtered context, not the ADP knowledge base
4. **Test the agent in the debug panel** — verify it can answer a simple
   question from the uploaded knowledge.
5. **Publish the application** — publishing creates the AppKey.

Reference: ADP guide §5 (page 7).

### Step 3: Copy the AppKey (manual, ~2 min)

1. Open the "Publish" tab, then "Service status".
2. Scroll to the API management section.
3. Click "Copy" in the Actions column to get the full AppKey.
4. Store it securely — the full value is not shown again.

Reference: ADP guide §5 (page 7).

### Step 4: Configure the environment (manual, ~1 min)

Set the AppKey as an environment variable:

```powershell
# Windows PowerShell
$env:ADP_APP_KEY = "your-copied-appkey"
uvicorn backend.api.app:app --reload
```

```bash
# Linux/Mac
export ADP_APP_KEY="your-copied-appkey"
uvicorn backend.api.app:app --reload
```

Verify the connection:
- `GET /health` should return `{"status": "ok", "llm": "adp"}`
- Submit a query — the answer should now come from the ADP agent instead of the stub

### Step 5: Verify the ADP Chat API response format (code, ~10 min)

The current `ADPClient.generate()` accumulates SSE events by parsing `data:`
lines and extracting text from `data`/`content`/`payload.text` fields. This is
a best-guess implementation since the guide says "refer to the ADP Chat API
documentation" for the full event schema.

After getting a real AppKey, make a test call and verify:
- The SSE event format matches our parser
- The text extraction captures the full answer
- Multi-turn conversations work (ConversationId reuse)

If the format differs, update `adp_client.py` lines 88-110 to match the real
event schema. The rest of the system is unaffected because the adapter
interface (`generate(prompt) -> str`) doesn't change.

### Step 6: Verify permission safety with live LLM (code, ~5 min)

Run the existing demo scenarios with the live ADP agent to confirm:
- Bob (contractor) still gets no-access for security content (INV1/INV2)
- Revocation still works with live LLM (INV3)
- Grounding checker still strips hallucinated sentences (INV8)
- No-metadata-leak still holds (INV7)

The permission pipeline runs BEFORE the LLM, so the LLM choice doesn't
affect authorization. But verify that the ADP agent doesn't inject external
knowledge that contradicts the grounding checker.

### Step 7: Record the demo (manual, ~5 min)

The guide says to keep proof of using the tools. After the live call works:
- Screenshot the ADP console showing the published agent
- Screenshot the `/health` response showing `"llm": "adp"`
- Capture a query + response from the Tianquan UI showing the ADP-powered answer
- Note the AppKey prefix shown in the console (masked, safe to screenshot)

### Step 8: Experience URL for judges (manual, ~2 min)

The ADP console provides a shareable Experience URL. This lets judges chat
with the agent directly. Add this URL to:
- The presentation slides
- The README
- The demo video description

Reference: ADP guide §6.1 (page 8).

## Risk: ADP response format unknown

The ADP Chat API returns SSE events, but the exact event schema (field names,
event types, end-of-stream signal) is not fully specified in the guide. The
guide says "refer to the ADP Chat API documentation" for the full set of
fields and events.

**Mitigation:** The adapter handles three common JSON shapes (`data`,
`content`, `payload.text`). After the first real call, we'll know the exact
format and can adjust. The adapter is a single file (~110 lines) and the
interface (`generate(prompt) -> str`) is stable.

## Risk: Grounding checker may over-strip with live LLM

The `GroundingChecker` (INV8) strips sentences from the answer that aren't
grounded in the provided context. The stub LLM produces text in a specific
style that the grounding checker was tuned for. A live LLM may phrase things
differently, causing the grounding checker to strip too aggressively.

**Mitigation:** The grounding checker falls back to a citation-only summary
if all sentences are stripped (orchestrator lines 138-140). Verify with real
queries and adjust the grounding checker's similarity threshold if needed.

## What does NOT change

- The permission pipeline (search -> filter -> assemble) is unchanged
- The audit trail is unchanged
- The answer agent's citation validation (INV6) is unchanged
- The no-metadata-leak guarantee (INV7) is unchanged
- The prompt structure is unchanged (system preamble + question + context)
- All existing tests pass unchanged (they use StubLLMClient)
- The frontend is unchanged

The LLM is behind a trust boundary (ADR-0005). Switching from stub to ADP
changes the response text quality but not the permission safety guarantees.