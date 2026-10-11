# ALIGNMENT.md — flash-safety-rules (16-item self-check)

| # | Rule | Result | Evidence |
|---|------|--------|----------|
| 1 | Ethics/legal boundary for sensitive domains | PASS | Defensive planning tool; zero hardware/network calls; FAQ "When NOT to use"; README Limits |
| 2 | Real code + CLI runs | PASS | `python flash_rules.py --rules`; validate/sequence/image-hash subcommands |
| 3 | self_test with 3 test classes | PASS | `python self_test.py` → 18 tests, all pass (functional 4 / violations 8 / edge 6) |
| 4 | Numbers measured or marked | PASS | Only claimed number = test count, reproducible; no perf claims |
| 5 | Fact claims dated | PASS | README "as of 2026-10-11" |
| 6 | No keys/secrets/real names | PASS | grep sk-/ghp_/personal emails → 0; LICENSE "zhengming contributors" |
| 7 | No >50-word copied source text | PASS | All text original; failure patterns paraphrased |
| 8 | why-not-X comparison ≥3 | PASS | README table: flasher built-ins / human checklist / vendor suites / device-test frameworks |
| 9 | Minimal fallback (PLAN B) | PASS | `--rules` prints the 8-line checklist as the full contract |
| 10 | Design trade-offs explicit | PASS | README Design Trade-offs (3 items) |
| 11 | Limits & second-order effects | PASS | Compliance theater, reflashable-gaming, vocabulary mismatch |
| 12 | Core assumptions ≥3 | PASS | README lists 4 |
| 13 | Confidence rating with basis | PASS | High/Medium split with reasoning |
| 14 | FAQ incl. When-NOT-to-use | PASS | 5 FAQs, first is When NOT |
| 15 | Fail-closed semantics | PASS | Violations exit 1; corrupt input exit 2; empty plan = fail-safe warning |
| 16 | Second-order effects section (rule 16) | PASS | Covered in Limits |

## Round-2 iteration record (v0.1.0 → v0.1.1)

- Correctness: uppercase-hash acceptance bug fixed + regression test; batch-rule test made actually reach FSR004.
- Robustness: corrupt-JSON and garbage-ops CLI paths covered.
- Honesty: compliance-theater second-order effect documented.

Repro: `python self_test.py` (exit 0), `python flash_rules.py plan.json`.
