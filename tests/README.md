# Tests — Tianquan 天权

<!-- Generated verification reference; updated after a fresh run on 2026-10-11. -->

**Baseline: 294 passed**, one dependency deprecation warning. Tests cover policy grants/denials, revocation, no-match/denial parity, Q-number matching, API privilege gates, preview/export auditing, audit tamper detection, citations, lexical grounding, query flags and the ADP adapter.

## Run

From the repository root, isolate the audit file so tests do not disturb a running demo:

```powershell
$previousAuditPath = $env:TIANQUAN_AUDIT_LOG
$env:TIANQUAN_AUDIT_LOG = Join-Path $env:TEMP ('tianquan-tests-' + [guid]::NewGuid().ToString() + '.jsonl')
try {
    uv run --with-requirements requirements.txt python -m pytest -q
} finally {
    $env:TIANQUAN_AUDIT_LOG = $previousAuditPath
}
```

With dependencies already installed, use `python -m pytest -q` inside the same isolation block. `tests/conftest.py` forces the stub; ADP tests mock HTTP. These tests do not verify live cloud availability, real source integrations, all concurrent Python interleavings or semantic truth of every generated sentence. TLA+ checks are separate: [formal instructions](../formal/README.md).
