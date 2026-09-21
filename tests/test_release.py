import importlib.util
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[1] / "tools/audit_release.py"
SPEC = importlib.util.spec_from_file_location("release_audit", SOURCE)
scanner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(scanner)


class ReleaseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "repo"
        self.root.mkdir()
        self.git("init", "-b", "main")
        self.git("config", "user.name", "Project Maintainers")
        self.git("config", "user.email", "maintainers@users.noreply.github.com")
        self.git("config", "commit.gpgsign", "false")
        (self.root / "public_allowlist.json").write_text(json.dumps({"files": ["README.md", "public_allowlist.json"]}))
        (self.root / "README.md").write_text("Synthetic public fixture.\n")

    def git(self, *args):
        return subprocess.run(["git", "-C", str(self.root), *args], check=True, capture_output=True)

    def test_neutral_repository_passes(self):
        self.assertEqual(scanner.audit(self.root)["status"], "PASS")

    def test_unlisted_file_is_blocked_even_if_ignored(self):
        (self.root / "hidden.bin").write_bytes(b"\x00")
        self.assertIn("not_allowlisted", [x["rule"] for x in scanner.audit(self.root)["issues"]])

    def test_secret_pattern_is_redacted(self):
        synthetic = "ghp" + "_" + "X" * 30
        findings = scanner.scan_text(synthetic.encode(), "fixture")
        self.assertTrue(findings)
        self.assertNotIn(synthetic, json.dumps(findings))

    def test_private_rules_are_external_and_block_vocabulary(self):
        private = Path(self.temp.name) / "rules.json"
        private.write_text(json.dumps({"terms": ["Synthetic public fixture"], "forbidden_sha256": []}))
        self.assertEqual(scanner.audit(self.root, private)["status"], "BLOCKED")
        with self.assertRaises(ValueError):
            scanner.audit(self.root, self.root / "private.json")

    def test_deleted_secret_in_history_is_blocked(self):
        target = self.root / "README.md"
        target.write_text("ghp" + "_" + "X" * 30)
        self.git("add", "--", "README.md", "public_allowlist.json")
        self.git("commit", "-m", "Synthetic history fixture")
        target.write_text("Safe current content.\n")
        self.git("add", "--", "README.md")
        self.git("commit", "-m", "Replace synthetic fixture")
        self.assertIn("provider_credential", [x["rule"] for x in scanner.audit(self.root)["issues"]])

    def test_staged_secret_is_blocked_when_worktree_differs(self):
        target = self.root / "README.md"
        target.write_text("ghp" + "_" + "X" * 30)
        self.git("add", "--", "README.md")
        target.write_text("Safe working tree.\n")
        self.assertIn("provider_credential", [x["rule"] for x in scanner.audit(self.root)["issues"]])

    def test_binary_disguised_as_text_is_blocked(self):
        (self.root / "README.md").write_bytes(b"a\x00b")
        self.assertIn("binary_content", [x["rule"] for x in scanner.audit(self.root)["issues"]])

    def test_missing_file_is_blocked(self):
        (self.root / "README.md").unlink()
        self.assertIn("missing_allowlisted_file", [x["rule"] for x in scanner.audit(self.root)["issues"]])

    def test_unreadable_git_history_blocks_release(self):
        (self.root / ".git/refs/heads/broken").write_text("1" * 40 + "\n")
        with self.assertRaises(ValueError):
            scanner.audit(self.root)


if __name__ == "__main__":
    unittest.main()
