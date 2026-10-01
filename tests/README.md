# Tests — Tianquan 天权

Integration and property tests for Tianquan (天权).

## Test categories

- **Permission positive cases** — authorized users retrieve expected resources.
- **Permission negative cases** — unauthorized users are denied, no metadata leaked.
- **Revocation cases** — revoked permissions not served after change.
- **Audit integrity** — hash chain valid, tamper detected on modification.
- **Citation validation** — every citation corresponds to an allowed resource.
- **Formal property mirrors** — Python property tests mirroring TLA+ invariants.