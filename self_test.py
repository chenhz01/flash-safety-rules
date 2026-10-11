#!/usr/bin/env python3
"""self_test for flash-safety-rules: functional / error paths / extreme edges."""
import json, os, subprocess, sys, tempfile, unittest

HERE = os.path.dirname(os.path.abspath(__file__))
MOD = os.path.join(HERE, "flash_rules.py")
sys.path.insert(0, HERE)
import flash_rules as fr

def run_cli(payload, extra=None):
    if payload is None:
        p = subprocess.run([sys.executable, MOD] + (extra or []), capture_output=True, text=True, encoding="utf-8", errors="replace")
    else:
        p = subprocess.run([sys.executable, MOD, "-", ] + (extra or []), input=json.dumps(payload),
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
    return p.returncode, (p.stdout or "") + (p.stderr or "")

def good_op(**over):
    op = {"action": "write", "partition": "userdata",
          "image": "img.img", "expected_sha256": "ab" * 32,
          "backup": "bak.img", "backup_sha256": "cd" * 32,
          "readback_verify": True, "confirm": True}
    op.update(over)
    return op

class Functional(unittest.TestCase):
    def test_clean_plan_passes(self):
        rc, out = run_cli({"device": "d1", "power": {"battery_pct": 80}, "ops": [good_op()]})
        self.assertEqual(rc, 0, out)
        self.assertIn("PLAN CLEAN", out)
    def test_rules_listing(self):
        rc, out = run_cli(None, ["--rules"])
        self.assertEqual(rc, 0)
        for rid in ("FSR001", "FSR003", "FSR008"):
            self.assertIn(rid, out)
    def test_image_hash_real_file(self):
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b"hello image"); path = f.name
        try:
            rc, out = run_cli(None, ["--image-hash", path])
            self.assertEqual(rc, 0)
            import hashlib
            self.assertIn(hashlib.sha256(b"hello image").hexdigest(), out)
        finally:
            os.remove(path)
    def test_safe_sequence_orders_backup_first(self):
        seq = fr.safe_sequence({"ops": [good_op()]})
        self.assertEqual(seq[0]["step"], "backup")
        self.assertIn("readback_verify", [s["step"] for s in seq])

class Violations(unittest.TestCase):
    def test_missing_backup(self):
        v, _ = fr.validate_plan({"ops": [good_op(backup=None, backup_sha256=None)]})
        self.assertTrue(any(r == "FSR001" for r, _ in v))
    def test_backup_without_hash(self):
        v, _ = fr.validate_plan({"ops": [good_op(backup_sha256=None)]})
        self.assertTrue(any(r == "FSR002" for r, _ in v))
    def test_trust_okay_rejected(self):
        v, _ = fr.validate_plan({"ops": [good_op(readback_verify=False)]})
        self.assertTrue(any(r == "FSR003" for r, _ in v))
    def test_batch_across_partitions(self):
        v, _ = fr.validate_plan({"ops": [good_op(), good_op(partition="boot", recovery_path="sdcard")]})
        self.assertTrue(any(r == "FSR004" for r, _ in v))
    def test_critical_without_recovery(self):
        v, _ = fr.validate_plan({"ops": [good_op(partition="bootloader")]})
        self.assertTrue(any(r == "FSR007" for r, _ in v))
    def test_no_confirm_is_dry_run_violation(self):
        v, _ = fr.validate_plan({"ops": [good_op(confirm=False)]})
        self.assertTrue(any(r == "FSR008" for r, _ in v))
    def test_low_battery(self):
        v, _ = fr.validate_plan({"power": {"battery_pct": 10, "min_battery_pct": 30}, "ops": [good_op()]})
        self.assertTrue(any(r == "FSR006" for r, _ in v))
    def test_cli_exit_nonzero_on_violation(self):
        rc, out = run_cli({"ops": [good_op(readback_verify=False)]})
        self.assertEqual(rc, 1)
        self.assertIn("FSR003", out)

class Edge(unittest.TestCase):
    def test_empty_plan_warns_fail_safe(self):
        v, w = fr.validate_plan({"ops": []})
        self.assertEqual(v, [])
        self.assertTrue(any("empty plan" in x for x in w))
    def test_corrupt_json(self):
        rc, out = run_cli(None) if False else (None, None)
        p = subprocess.run([sys.executable, MOD, "-"], input="{not json",
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
        self.assertEqual(p.returncode, 2)
        self.assertIn("corrupt plan", p.stdout + p.stderr)
    def test_plan_not_object(self):
        v, _ = fr.validate_plan([1, 2, 3])
        self.assertTrue(any(r == "FSR008" for r, _ in v))
    def test_garbage_ops_items(self):
        v, w = fr.validate_plan({"ops": ["junk", 42, None]})
        self.assertTrue(len(v) >= 2)
    def test_large_plan_under_limit(self):
        ops = [good_op()] * 1  # same partition, so no FSR004
        ops = [good_op(partition="p%d" % i, recovery_path="r") for i in range(500)]
        v, _ = fr.validate_plan({"ops": ops})
        self.assertTrue(any(r == "FSR004" for r, _ in v))  # must refuse batch
    def test_invalid_hash_shapes(self):
        self.assertFalse(fr.re_valid_hash("xyz"))
        self.assertFalse(fr.re_valid_hash("AB" * 32))  # uppercase rejected (strict hex lower)
        self.assertTrue(fr.re_valid_hash("ab" * 32))
    def test_unknown_action_warns_only(self):
        v, w = fr.validate_plan({"ops": [{"action": "teleport", "partition": "x"}]})
        self.assertEqual(v, [])
        self.assertTrue(any("teleport" in x for x in w))

if __name__ == "__main__":
    unittest.main(verbosity=1)
