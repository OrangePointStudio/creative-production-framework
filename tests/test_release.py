import importlib.util
import json
import subprocess
import sys
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
        result = scanner.audit(self.root)
        self.assertEqual(result["status"], "PASS")
        self.assertEqual([entry["path"] for entry in result["files"]], ["README.md", "public_allowlist.json"])

    def test_unlisted_file_is_blocked_even_if_ignored(self):
        (self.root / "hidden.bin").write_bytes(b"\x00")
        self.assertIn("not_allowlisted", [x["rule"] for x in scanner.audit(self.root)["issues"]])

    def test_secret_pattern_is_redacted(self):
        synthetic = "ghp" + "_" + "X" * 30
        findings = scanner.scan_text(synthetic.encode(), "fixture")
        self.assertTrue(findings)
        self.assertNotIn(synthetic, json.dumps(findings))

    def test_json_and_yaml_credentials_are_blocked(self):
        synthetic = "Z" * 24
        cases = [json.dumps({name: synthetic}) for name in ("api_key", "access_token", "client_secret", "password")]
        cases.extend(["api_key: " + synthetic + "\n", "password = '" + synthetic + "'\n"])
        for index, content in enumerate(cases):
            with self.subTest(format_index=index):
                (self.root / "README.md").write_text(content)
                self.git("add", "--", "README.md", "public_allowlist.json")
                result = scanner.audit(self.root)
                self.assertEqual(result["status"], "BLOCKED")
                self.assertIn("credential_assignment", [x["rule"] for x in result["issues"]])
                self.assertNotIn(synthetic, json.dumps(result))

    def test_sensitive_scan_labels_are_redacted(self):
        synthetic = "ghp" + "_" + "X" * 30
        private_term = "SyntheticPrivateClient"
        for label, terms in ((synthetic + ".md", ()), (private_term + "/brief.md", (private_term,))):
            with self.subTest(private_rules=bool(terms)):
                result = scanner.scan_text(synthetic.encode(), label, terms)
                serialized = json.dumps(result)
                self.assertTrue(result)
                self.assertNotIn(synthetic, serialized)
                self.assertNotIn(private_term, serialized)
                self.assertEqual(result[0]["file"], "[redacted-path]")

    def test_unlisted_and_missing_sensitive_filenames_are_redacted(self):
        synthetic = "ghp" + "_" + "X" * 30
        name = synthetic + ".md"
        target = self.root / name
        target.write_text("Synthetic fixture")
        result = scanner.audit(self.root)
        self.assertIn("not_allowlisted", [x["rule"] for x in result["issues"]])
        self.assertNotIn(synthetic, json.dumps(result))
        target.unlink()
        (self.root / "public_allowlist.json").write_text(json.dumps({"files": ["README.md", "public_allowlist.json", name]}))
        result = scanner.audit(self.root)
        self.assertIn("missing_allowlisted_file", [x["rule"] for x in result["issues"]])
        self.assertNotIn(synthetic, json.dumps(result))

    def test_sensitive_manifest_and_historical_paths_are_redacted(self):
        synthetic = "ghp" + "_" + "X" * 30
        name = synthetic + ".md"
        target = self.root / name
        target.write_text(synthetic)
        (self.root / "public_allowlist.json").write_text(json.dumps({"files": ["README.md", "public_allowlist.json", name]}))
        self.git("add", "--", "README.md", "public_allowlist.json", name)
        self.git("commit", "-m", "Synthetic filename fixture")
        result = scanner.audit(self.root, require_clean=True)
        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(result["files"], [])
        self.assertNotIn(synthetic, json.dumps(result))
        target.unlink()
        (self.root / "public_allowlist.json").write_text(json.dumps({"files": ["README.md", "public_allowlist.json"]}))
        self.git("add", "--", "public_allowlist.json", name)
        self.git("commit", "-m", "Remove synthetic filename fixture")
        result = scanner.audit(self.root, require_clean=True)
        self.assertIn("historical_file_not_allowlisted", [x["rule"] for x in result["issues"]])
        self.assertNotIn(synthetic, json.dumps(result))

    def test_private_vocabulary_is_redacted_from_paths(self):
        private_term = "SyntheticPrivateClient"
        name = private_term + "/brief.md"
        target = self.root / name
        target.parent.mkdir()
        target.write_text("Synthetic fixture")
        (self.root / "public_allowlist.json").write_text(json.dumps({"files": ["README.md", "public_allowlist.json", name]}))
        private = Path(self.temp.name) / "rules.json"
        private.write_text(json.dumps({"terms": [private_term.lower()]}))
        result = scanner.audit(self.root, private)
        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(result["files"], [])
        self.assertNotIn(private_term.lower(), json.dumps(result).lower())

    def test_malformed_private_rules_fail_without_echoing_input(self):
        synthetic = "SyntheticPrivateAccount"
        private = Path(self.temp.name) / (synthetic + ".json")
        cases = [
            [synthetic], {"terms": synthetic}, {"terms": [synthetic, {}]},
            {"forbidden_sha256": {synthetic: "invalid"}},
            {"forbidden_sha256": [synthetic]}, {"forbidden_sha256": [{}]},
        ]
        for rules in cases:
            private.write_text(json.dumps(rules))
            result = subprocess.run([sys.executable, str(SOURCE), "--root", str(self.root), "--private-rules", str(private)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 2)
            self.assertEqual(json.loads(result.stdout)["status"], "BLOCKED")
            self.assertEqual(result.stderr, "")
            self.assertNotIn(synthetic, result.stdout)

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

    def test_shallow_history_cannot_hide_a_deleted_secret(self):
        target = self.root / "README.md"
        target.write_text("ghp" + "_" + "X" * 30)
        self.git("add", "--", "README.md", "public_allowlist.json")
        self.git("commit", "-m", "Synthetic history fixture")
        target.write_text("Safe current content.\n")
        self.git("add", "--", "README.md")
        self.git("commit", "-m", "Replace synthetic fixture")
        full = scanner.audit(self.root, require_clean=True)
        self.assertEqual(full["status"], "BLOCKED")
        self.assertEqual(full["commits_scanned"], 2)
        shallow_root = Path(self.temp.name) / "shallow"
        subprocess.run(["git", "clone", "--depth", "1", self.root.as_uri(), str(shallow_root)], check=True, capture_output=True)
        shallow = scanner.audit(shallow_root, require_clean=True)
        self.assertEqual(shallow["status"], "BLOCKED")
        self.assertIn("shallow_history", [x["rule"] for x in shallow["issues"]])
        self.assertEqual(shallow["commits_scanned"], 1)
        self.assertEqual(scanner.audit(shallow_root, history=False, require_clean=True)["status"], "PASS")

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
