import importlib.util
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class UrlHelperTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.builder = load_module("shika_build_site", ROOT / "build_site.py")
        cls.validator = load_module("shika_ui_validator", ROOT / "scripts" / "validate_ui_contract.py")

    def test_internal_url_is_document_relative_at_each_depth(self):
        self.assertEqual(self.builder.internal_url(0, "clinic/1.html"), "clinic/1.html")
        self.assertEqual(self.builder.internal_url(1, "/clinic/1.html"), "../clinic/1.html")
        self.assertEqual(self.builder.internal_url(2, "clinic/1.html"), "../../clinic/1.html")
        for depth in range(4):
            self.assertFalse(self.builder.internal_url(depth, "data/search/14.json").startswith("/"))

    def test_mount_resolution_accepts_relative_and_rejects_escape(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            dist = Path(tmp)
            (dist / "clinic").mkdir()
            (dist / "clinic" / "1.html").write_text("ok", encoding="utf-8")
            for mount in ("/", "/shika/"):
                self.assertTrue(
                    self.validator.resolves_under_mount(
                        dist, "pref/kanagawa/city.html", "../../clinic/1.html", mount
                    )
                )
            self.assertFalse(
                self.validator.resolves_under_mount(
                    dist, "pref/kanagawa/city.html", "/clinic/1.html", "/shika/"
                )
            )

    def test_nearby_threshold_fails_closed_until_interactive_flow_is_reviewed(self):
        with self.assertRaisesRegex(RuntimeError, "実装・再レビュー"):
            self.builder.build_nearby_page(100, 80, True)


if __name__ == "__main__":
    unittest.main()
