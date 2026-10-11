# Changelog

## v0.1.1 (2026-10-11)

Second-pass self-review against the 16-item alignment checklist:

- Fixed: uppercase sha256 hashes were silently accepted by the plan validator;
  now strictly rejected (fail-loud), with a dedicated unit test.
- Fixed: `test_large_plan_under_limit` originally reused a single partition,
  which could never exercise the batch rule (FSR004); ops now span 500
  partitions and assert the refusal.
- Added: error-path coverage for corrupt JSON via CLI (exit 2) and
  garbage-typed ops entries.
- README: added Limits entry on compliance theater (declaring `readback_verify`
  without executing it) and its pairing with a runtime witness.

## v0.1.0 (2026-10-11)

Initial release:

- 8 mandatory pre-write guardrails (FSR001-008) as a plan validator.
- `--sequence` planner emitting the mandatory safe order
  (backup → hash → write → readback).
- `--image-hash` helper for declaring FSR005 hashes.
- self_test: functional / error-path / extreme-edge cases, stdlib only.
