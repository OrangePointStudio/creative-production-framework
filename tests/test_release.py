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

    @staticmethod
    def commit_fixture(author_email, *, committer_email=None, author_name="Synthetic Author",
            committer_name="Synthetic Committer", message="Synthetic commit", extra_headers=""):
        committer_email = committer_email or "maintainers@users.noreply.github.com"
        return ("tree " + "0" * 40 + "\n" +
            f"author {author_name} <{author_email}> 1700000000 +0000\n" +
            f"committer {committer_name} <{committer_email}> 1700000000 +0000\n" +
            extra_headers + "\n" + message + "\n").encode()

    def test_neutral_repository_passes(self):
        result = scanner.audit(self.root)
        self.assertEqual(result["status"], "PASS")
        self.assertEqual([entry["path"] for entry in result["files"]], ["README.md", "public_allowlist.json"])

    def test_public_github_aliases_pass_only_in_commit_identity_headers(self):
        domain = "@users.noreply.github.com"
        for username in ("synthetic-public", "12345+synthetic-public"):
            email = username + domain
            data = self.commit_fixture(email, committer_email=email)
            self.assertEqual(scanner.scan_commit(data, "commit:fixture"), [])
            self.assertIn("email_address", [x["rule"] for x in scanner.scan_text(data, "blob")])
        self.git("config", "user.email", "12345+synthetic-public" + domain)
        self.git("add", "--", "README.md", "public_allowlist.json")
        self.git("commit", "-m", "Synthetic public identity fixture")
        self.assertEqual(scanner.audit(self.root, require_clean=True)["status"], "PASS")

    def test_github_service_exception_requires_exact_committer_header(self):
        service = "noreply" + "@github.com"
        neutral = "maintainers@users.noreply.github.com"
        data = self.commit_fixture(neutral, committer_email=service, committer_name="GitHub")
        self.assertEqual(scanner.scan_commit(data, "commit:fixture"), [])
        cases = [
            self.commit_fixture(service, author_name="GitHub"),
            self.commit_fixture(neutral, committer_email=service),
            self.commit_fixture(neutral, message=service),
        ]
        for data in cases:
            self.assertIn("email_address", [x["rule"] for x in scanner.scan_commit(data, "commit:fixture")])
        self.assertIn("email_address", [x["rule"] for x in scanner.scan_text(service.encode(), "blob")])

    def test_commit_exception_does_not_cover_messages_names_or_other_headers(self):
        email = "synthetic-public" + "@users.noreply.github.com"
        cases = [
            self.commit_fixture(email, message=email),
            self.commit_fixture(email, message=f"author Synthetic <{email}> 1700000000 +0000"),
            self.commit_fixture(email, author_name=email),
            self.commit_fixture(email, extra_headers="x-contact " + email + "\n"),
            self.commit_fixture(email, extra_headers=f"gpgsig synthetic\n author Synthetic <{email}> 1700000000 +0000\n"),
        ]
        for index, data in enumerate(cases):
            with self.subTest(location_index=index):
                findings = scanner.scan_commit(data, "commit:fixture")
                self.assertEqual([x["rule"] for x in findings], ["email_address"])
                self.assertNotIn(email, json.dumps(findings))
        path_result = scanner.scan_text(b"\x00", email + ".md")
        self.assertEqual(path_result[0]["file"], "[redacted-path]")

    def test_commit_exception_rejects_private_emails_and_malformed_aliases(self):
        domain = "@users.noreply.github.com"
        addresses = [
            "operator" + "@private.invalid", "bad_name" + domain,
            "-leading" + domain, "trailing-" + domain, "double--dash" + domain,
            "x" * 40 + domain, "non-numeric+synthetic" + domain,
            "synthetic" + domain + ".spoof.invalid", "synthetic" + "@github.com",
        ]
        for index, email in enumerate(addresses):
            with self.subTest(alias_index=index):
                findings = scanner.scan_commit(self.commit_fixture(email), "commit:fixture")
                self.assertIn("email_address", [x["rule"] for x in findings])
                self.assertNotIn(email, json.dumps(findings))
        email = "synthetic-public" + domain
        data = self.commit_fixture(email).replace(b"1700000000 +0000", b"invalid-time")
        self.assertIn("email_address", [x["rule"] for x in scanner.scan_commit(data, "commit:fixture")])

    def test_commit_exception_preserves_secret_and_private_vocabulary_checks(self):
        username = "sk-" + "X" * 24
        email = username + "@users.noreply.github.com"
        findings = scanner.scan_commit(self.commit_fixture(email), "commit:fixture")
        self.assertIn("provider_credential", [x["rule"] for x in findings])
        self.assertNotIn(username, json.dumps(findings))
        email = "synthetic-private-client" + "@users.noreply.github.com"
        for term in ("synthetic-private-client", "synthetic author"):
            findings = scanner.scan_commit(self.commit_fixture(email), "commit:fixture", (term,))
            self.assertIn("private_vocabulary", [x["rule"] for x in findings])
            self.assertNotIn(email, json.dumps(findings))
        self.git("config", "user.email", email)
        self.git("add", "--", "README.md", "public_allowlist.json")
        self.git("commit", "-m", "Synthetic public identity fixture")
        private = Path(self.temp.name) / "rules.json"
        private.write_text(json.dumps({"terms": ["synthetic-private-client"]}))
        result = scanner.audit(self.root, private, require_clean=True)
        self.assertEqual(result["status"], "BLOCKED")
        self.assertIn("private_vocabulary", [x["rule"] for x in result["issues"]])

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
