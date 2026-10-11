# flash-safety-rules

Pre-write guardrails for agent-driven hardware flashing: validate an operation
plan against 8 mandatory rules (FSR001–008) before anything touches a device.
Pure offline planning — this tool never talks to hardware.

Use it when an AI agent (or a tired human) is about to flash firmware, and you
want "never trust the flasher's OKAY" enforced mechanically instead of hoped for.

<p align="center"><img src="docs/demo.gif" alt="demo" width="720"></p>

## Problem

Agents executing hardware writes fail in a characteristic way: they trust the
flasher tool's success code. `fastboot` prints `OKAY`, the agent declares
victory, and the device is bricked because nobody read the partition back.
Real incidents share a pattern — missing backup, batch operations across
partitions, no recovery path for critical partitions, no power-state guard.
Checklists don't survive agents; machine-checkable rules do.

## How it works

A plan is a JSON document describing operations (`write`, `backup`, ...).
`flash_rules.py validate` checks each operation against the 8 rules:

```
FSR001  pre-write backup declared (or reflashable with justification)
FSR002  backup sha256 recorded before any write
FSR003  readback verification required — tool "OKAY" is not verification
FSR004  one partition per operation batch
FSR005  image sha256 must match a declared expected hash
FSR006  power-state guard (minimum battery, unstable power)
FSR007  recovery path declared before writing critical partitions
FSR008  dry-run by default: destructive ops need explicit confirm=true
```

`--sequence` rewrites any plan into the mandatory safe order:
backup → hash_backup → write → readback_verify.

## Quickstart (~5 seconds)

```bash
python flash_rules.py plan.json          # verdict + violations (exit 1 on any)
python flash_rules.py --rules            # print the 8 rules
python flash_rules.py --sequence plan.json
python flash_rules.py --image-hash img.img
```

## Why not X

| Alternative | Gap vs this tool |
|---|---|
| Flasher tool built-in checks (`fastboot`, `heimdall`) | Report per-operation success only; no cross-operation invariants (backup-before-write, recovery-before-critical) and no "don't trust OKAY" enforcement |
| Human review checklist | Not machine-checkable, drifts, doesn't run in an agent loop; this tool exits nonzero so CI/agent harnesses can gate on it |
| Vendor device-management suites | Locked to one vendor's devices/cloud; this is a portable plan-level gate, engine-agnostic |
| Full device-test frameworks (AVA/etc.) | Simulate real devices; heavy. This is the cheap upstream gate before such tests ever run |

## Minimal Fallback (PLAN B)

No JSON plan? Enforce the rules by hand with the printed checklist:

```bash
python flash_rules.py --rules > flash-checklist.txt
```

The 8 lines are the entire contract; everything else in this repo is automation.

## Design Trade-offs

- **Plan-level, not device-level**: portable and offline, but it cannot detect a
  lying bootloader or a corrupted image on the wire — FSR005/FSR003 push those
  checks to hash comparisons you must actually perform.
- **Strict lowercase sha256**: rejects uppercase hashes rather than
  normalizing; fail-loud beats fail-maybe.
- **Violations are blocking, warnings are not**: unknown actions warn; missing
  backups block. The asymmetry is deliberate.

## Limits & Second-order Effects

- Compliance theater risk: an agent can satisfy FSR003 by *declaring*
  `readback_verify: true` and then not doing it. The rule gates planning; a
  runtime witness must confirm execution (pair with an audit log).
- Over-gating pushes users to mark everything `reflashable: true` to skip
  FSR001 — treat that flag as the audit point it is.
- Rule coverage is flasher-shaped (partitions, images). For MCU/DFU flows the
  vocabulary needs a thin mapping.

## FAQ

**When NOT to use this?** If your "device" is a container or a disk image on a
hypoervisor — snapshots make every rule trivially satisfied and this tool adds
ceremony, not safety. Also not for read-only device inspection.

**Does it flash anything?** No. It is a planner/validator. Zero hardware calls,
zero network calls, stdlib only.

**Why is uppercase sha256 rejected?** Strictness is the feature: a hash that
needed "fixing" before comparison is a hash nobody verified.

**What stops a lying agent from setting all the flags?** Nothing, at plan
level. FSR008's dry-run default plus a separate execution witness is the
intended pair. See Limits.

**Can I add rules?** Yes — `RULES` is a dict, validators are one function per
concern. Keep new rules fail-closed like the existing ones.

## [Core Assumptions]

1. The flasher tool can read back written partitions (fastboot/heimdall/dd all
   can); if your tool cannot, FSR003 is unimplementable and you need a different
   tool before you need this gate.
2. sha256 is an acceptable image-identity check for this class of operations.
3. "Critical partitions" set (`bootloader/boot/recovery/modem/persistent`)
   approximates bricking risk; vendors may differ.
4. Battery percentage, when declared, is truthful. The tool cannot measure it.

Confidence: High for the rule set's shape (derived from recurring failure
patterns in public flashing guides, as of 2026-10-11); Medium that 8 rules are
the right number — treat as a baseline, not a ceiling.
