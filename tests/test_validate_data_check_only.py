import hashlib
import importlib.util
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BASELINE = ROOT / "scripts" / "validation_baseline.json"


def fingerprint(path: Path):
    if not path.exists():
        return None
    stat = path.stat()
    return hashlib.sha256(path.read_bytes()).hexdigest(), stat.st_mtime_ns, stat.st_size


class ValidateDataCheckOnlyTests(unittest.TestCase):
    def test_check_only_does_not_create_missing_baseline_parent(self):
        spec = importlib.util.spec_from_file_location(
            "validate_data_for_test", ROOT / "scripts" / "validate_data.py"
        )
        module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as tmp:
            missing = Path(tmp) / "not-created" / "baseline.json"
            module.BASELINE_FILE = missing
            module.results.clear()
            module.check_baseline({"data_record_count": 1}, update_baseline=False)
            self.assertFalse(missing.parent.exists())
            self.assertFalse(missing.exists())

    def test_check_only_preserves_baseline_bytes_and_mtime(self):
        before = fingerprint(BASELINE)
        proc = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "validate_data.py"), "--check-only"],
            cwd=ROOT,
            text=True,
            encoding="utf-8",
            errors="replace",
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        after = fingerprint(BASELINE)
        self.assertEqual(proc.returncode, 0, proc.stdout)
        self.assertEqual(before, after)
        self.assertIn("check-only", proc.stdout)

    def test_no_update_baseline_alias_is_accepted(self):
        before = fingerprint(BASELINE)
        proc = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "validate_data.py"), "--no-update-baseline"],
            cwd=ROOT,
            text=True,
            encoding="utf-8",
            errors="replace",
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        self.assertEqual(proc.returncode, 0, proc.stdout)
        self.assertEqual(before, fingerprint(BASELINE))


if __name__ == "__main__":
    unittest.main()
