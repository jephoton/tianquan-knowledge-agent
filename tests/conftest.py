"""Shared pytest configuration.

Forces the deterministic StubLLMClient for the whole test suite. Without this,
tests inherit the developer's `.env` ADP key and every `/query` attempts a live
ADP call (slow, and — on TLS-inspected networks — it fails then falls back),
which made the suite slow and order-sensitive. Using the stub makes tests fast,
deterministic, and isolated from network state.

`state.py` calls `load_dotenv()` at import time with the default
override=False, so an env var that is already present (even empty) is NOT
overwritten by `.env`. Setting an empty value here therefore wins, and
`_build_llm()` treats empty as "no key" → StubLLMClient.

The ADP adapter itself is still covered directly by test_adp_client.py, which
constructs ADPClient explicitly and mocks the HTTP layer.
"""

import os

# Must run before any test imports backend.api.state. Empty = falsy = stub.
os.environ["ADP_APP_KEY"] = ""
