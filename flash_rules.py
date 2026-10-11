#!/usr/bin/env python3
"""flash-safety-rules -- pre-write guardrails for agent-driven hardware flashing.

A rules engine that validates a flashing operation plan against 8 mandatory
safety rules (FSR001-008). Defensive tooling: it gates plans, it never talks
to hardware. Core principle: NEVER trust the flasher's "OKAY" -- require a
readback hash comparison (FSR003).

as of 2026-10-11
"""
import argparse, hashlib, json, os, sys

RULES = {
    "FSR001": "pre-write backup of target partition is declared (or reflashable=true with justification)",
    "FSR002": "backup hash (sha256) recorded before any write",
    "FSR003": "readback verification required -- never trust the flasher tool's OKAY",
    "FSR004": "one partition per operation batch (no batch flashing)",
    "FSR005": "image sha256 must match a declared expected hash before write",
    "FSR006": "power-state guard: writes refused below declared minimum battery / on unstable power",
    "FSR007": "recovery path declared before writing a critical partition (bootloader/boot)",
    "FSR008": "dry-run by default: destructive ops need explicit confirm=true",
}

CRITICAL = {"bootloader", "boot", "recovery", "modem", "persistent"}

def _hash_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()

def validate_plan(plan):
    """plan: dict {device, power:{battery_pct}, ops:[{action,partition,image,
    expected_sha256,backup,backup_sha256,readback_verify,reflashable,
    recovery_path,confirm}]}. Returns (violations, warnings)."""
    violations, warnings = [], []
    if not isinstance(plan, dict):
        return [("FSR008", "plan is not an object (corrupt input)")], ["nothing validated"]
    ops = plan.get("ops")
    if not isinstance(ops, list) or not ops:
        return [], ["empty plan: nothing to do (fail-safe)"]
    power = plan.get("power") or {}
    battery = power.get("battery_pct")
    min_power = plan.get("power", {}).get("min_battery_pct", 30)
    if isinstance(battery, (int, float)) and battery < min_power:
        for i, op in enumerate(ops):
            violations.append(("FSR006", "op%d: battery %s%% below minimum %s%%"
                               % (i, battery, min_power)))
    if len(ops) > 1:
        dict_ops = [op for op in ops if isinstance(op, dict)]
        parts = {str(op.get("partition")) for op in dict_ops}
        if len(parts) > 1:
            violations.append(("FSR004", "batch of %d ops across %d partitions: split into one partition per batch"
                               % (len(ops), len(parts))))
    for i, op in enumerate(ops):
        if not isinstance(op, dict):
            violations.append(("FSR008", "op%d: not an object" % i)); continue
        part = str(op.get("partition", ""))
        action = str(op.get("action", "write"))
        if action == "write":
            # FSR001 backup
            if not op.get("backup") and not op.get("reflashable"):
                violations.append(("FSR001", "op%d (%s): no backup declared and not marked reflashable" % (i, part)))
            elif op.get("backup") and not op.get("backup_sha256"):
                violations.append(("FSR002", "op%d (%s): backup declared but no backup_sha256 recorded" % (i, part)))
            # FSR002
            if op.get("backup_sha256") and not re_valid_hash(op.get("backup_sha256")):
                violations.append(("FSR002", "op%d (%s): backup_sha256 is not a valid sha256" % (i, part)))
            # FSR003 readback
            if not op.get("readback_verify"):
                violations.append(("FSR003", "op%d (%s): readback_verify not set -- tool 'OKAY' is not verification" % (i, part)))
            # FSR005 expected hash
            if not re_valid_hash(op.get("expected_sha256")):
                violations.append(("FSR005", "op%d (%s): expected_sha256 missing/invalid -- image identity unproven" % (i, part)))
            # FSR008 confirm
            if not op.get("confirm"):
                violations.append(("FSR008", "op%d (%s): destructive write without confirm=true (dry-run default)" % (i, part)))
            # FSR007 recovery
            if part in CRITICAL and not op.get("recovery_path"):
                violations.append(("FSR007", "op%d (%s): critical partition without declared recovery_path" % (i, part)))
        elif action not in ("read", "backup", "verify"):
            warnings.append("op%d: unknown action %r ignored" % (i, action))
    return violations, warnings

def re_valid_hash(v):
    # strict: 64 lowercase hex chars only — uppercase is rejected, not normalized
    return isinstance(v, str) and len(v) == 64 and all(c in "0123456789abcdef" for c in v)

def safe_sequence(plan):
    """Reorder a plan into the mandatory safe order: backup -> verify-backup ->
    write -> readback-verify. Pure planning output; nothing executes."""
    seq = []
    for op in plan.get("ops", []) if isinstance(plan, dict) else []:
        part = op.get("partition", "?")
        if op.get("backup"):
            seq.append({"step": "backup", "partition": part})
            seq.append({"step": "hash_backup", "partition": part})
        seq.append({"step": "write", "partition": part,
                    "guard": "expected_sha256 match (FSR005)"})
        seq.append({"step": "readback_verify", "partition": part,
                    "guard": "sha256(readback)==expected_sha256; never trust tool OKAY (FSR003)"})
        if part in CRITICAL:
            seq.append({"step": "keep_recovery_ready", "partition": part})
    return seq

def main():
    ap = argparse.ArgumentParser(prog="flash_rules",
                                 description="Validate agent hardware-flash plans against FSR001-008 guardrails.")
    ap.add_argument("plan", nargs="?", help="path to plan JSON, or '-' for stdin (optional with --rules/--image-hash)")
    ap.add_argument("--rules", action="store_true", help="print the 8 rules and exit")
    ap.add_argument("--sequence", action="store_true", help="emit the mandatory safe sequence instead of verdict")
    ap.add_argument("--image-hash", metavar="FILE", help="compute sha256 of a local image file")
    a = ap.parse_args()
    if a.rules:
        for k in sorted(RULES):
            print("%s: %s" % (k, RULES[k]))
        return 0
    if a.image_hash:
        if not os.path.isfile(a.image_hash):
            print("no such file: %s" % a.image_hash); return 2
        print(_hash_file(a.image_hash)); return 0
    try:
        raw = open(a.plan, encoding="utf-8").read() if a.plan != "-" else sys.stdin.read()
        plan = json.loads(raw)
    except Exception as e:
        print("corrupt plan: %s" % e); return 2
    if a.sequence:
        print(json.dumps(safe_sequence(plan), indent=1)); return 0
    violations, warnings = validate_plan(plan)
    for w in warnings:
        print("WARN:", w)
    if not violations:
        print("PLAN CLEAN: all applicable FSR rules satisfied")
        return 0
    for rid, msg in violations:
        print("VIOLATION %s: %s" % (rid, msg))
    print("FAILED: %d violation(s). Plan must not run." % len(violations))
    return 1

if __name__ == "__main__":
    sys.exit(main())
