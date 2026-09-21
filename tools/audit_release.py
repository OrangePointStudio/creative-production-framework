"""Fail closed on unlisted files, linked objects and common secret/identity patterns.

This scanner is an aid to human review, not a proof that arbitrary text is safe.
Private vocabulary can be supplied from a file kept outside the repository.
"""

import argparse
import hashlib
import json
import os
import re
import stat
import subprocess
import sys
from pathlib import Path

RULES = {
    "provider_credential": r"(?:gh[pousr]_[A-Za-z0-9]{24,}|github_pat_[A-Za-z0-9_]{20,}|sk-[A-Za-z0-9_-]{20,}|AKIA[0-9A-Z]{16})",
    "private_key": r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----",
    "personal_home_path": r"(?:[A-Za-z]:[\\/](?:Users|Documents and Settings)[\\/][^\s]+|/(?:Users|home)/[^\s/]+/)",
    "private_cloud_url": r"https?://(?:drive\.google\.com|docs\.google\.com|mail\.google\.com|[^/]+\.blob\.core\.windows\.net)/[^\s]+",
    "credential_url": r"https?://[^\s\"'<>]+[?&](?:token|key|sig|signature|credential|X-Amz-Credential)=[^\s]+",
    "credential_assignment": r"(?i)(?<!\w)['\"]?(?:api_key|access_token|client_secret|password)['\"]?\s*[:=]\s*(?:['\"][^'\"\r\n]{16,}['\"]|[A-Za-z0-9_./+=-]{16,}(?=$|[\s,;#}\]]))",
    "encoded_payload": r"[A-Za-z0-9+/]{160,}={0,2}",
    "long_account_number": r"(?<![\w])\d{13,19}(?![\w])",
    "git_lfs_pointer": r"(?m)^version https://git-lfs[.]github[.]com/spec/v1$",
}
EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
SAFE_EMAILS = {"maintainers@users.noreply.github.com"}
PERMITTED_EXTENSIONS = {".py", ".md", ".json", ".toml", ".yml", ".yaml", ".txt"}


def git(root, *args, optional=False):
    result = subprocess.run(["git", "-C", str(root), *args], capture_output=True)
    if result.returncode and not optional:
        raise ValueError("Required Git inspection failed.")
    return result.stdout


def _scan_text(data, label, private_terms=()):
    issues = []
    if len(data) > 512 * 1024:
        return [{"file": label, "rule": "oversized_public_text"}]
    try:
        text = data.decode("utf-8")
    except UnicodeError:
        return [{"file": label, "rule": "binary_or_invalid_utf8"}]
    if "\x00" in text:
        return [{"file": label, "rule": "binary_content"}]
    for name, expression in RULES.items():
        for match in re.finditer(expression, text):
            issues.append({"file": label, "line": text.count("\n", 0, match.start()) + 1, "rule": name})
    for match in EMAIL.finditer(text):
        value = match.group()
        if value not in SAFE_EMAILS and not value.endswith(("@example.com", "@example.invalid")):
            issues.append({"file": label, "line": text.count("\n", 0, match.start()) + 1, "rule": "email_address"})
    folded = text.casefold()
    for term in private_terms:
        if term.casefold() in folded:
            issues.append({"file": label, "rule": "private_vocabulary"})
    return issues


def safe_label(label, private_terms=()):
    """Keep locations useful without copying sensitive path text into reports."""
    if _scan_text(label.encode("utf-8"), "path", private_terms):
        return "[redacted-path]"
    return label


def scan_text(data, label, private_terms=()):
    return _scan_text(data, safe_label(label, private_terms), private_terms)


def audit(root, private_rules=None, history=True, require_clean=False):
    candidate = Path(root).absolute()
    for component in (candidate, *candidate.parents):
        info = component.lstat()
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
            raise ValueError("Linked repository path is not permitted.")
    root = candidate.resolve()
    allow = json.loads((root / "public_allowlist.json").read_text(encoding="utf-8"))
    if not isinstance(allow, dict):
        raise ValueError("Allowlist must be a JSON object.")
    names = allow.get("files", [])
    if not isinstance(names, list) or not names or any(not isinstance(n, str) for n in names) or len(names) != len(set(names)):
        raise ValueError("Allowlist must contain unique exact file names.")
    if any(Path(n).is_absolute() or "\\" in n or ":" in n or ".." in n.split("/") for n in names):
        raise ValueError("Unsafe allowlist path.")
    allowed = set(names)
    terms, forbidden_hashes = [], set()
    if private_rules:
        rules_path = Path(private_rules).resolve()
        if root == rules_path or root in rules_path.parents:
            raise ValueError("Private scan rules must remain outside the public repository.")
        rules = json.loads(rules_path.read_text(encoding="utf-8"))
        if not isinstance(rules, dict):
            raise ValueError("Private scan rules must be a JSON object.")
        terms = rules.get("terms", [])
        if not isinstance(terms, list) or any(not isinstance(t, str) or len(t) < 3 for t in terms):
            raise ValueError("Private vocabulary must be a list of strings of at least three characters.")
        hashes = rules.get("forbidden_sha256", [])
        if not isinstance(hashes, list) or any(not isinstance(h, str) or not re.fullmatch(r"[0-9a-fA-F]{64}", h) for h in hashes):
            raise ValueError("Private source hashes must be a list of SHA-256 digests.")
        forbidden_hashes = {h.lower() for h in hashes}
    issues, files, seen = [], [], set()

    def inspect(data, name):
        issues.extend(scan_text(data, name, terms))
        if hashlib.sha256(data).hexdigest() in forbidden_hashes:
            issues.append({"file": name, "rule": "private_source_hash"})
        issues.extend(scan_text(name.encode(), "path", terms))

    for here, dirs, leaves in os.walk(root, followlinks=False):
        for d in list(dirs):
            if d == ".git":
                if Path(here) != root:
                    issues.append({"file": str((Path(here) / d).relative_to(root)), "rule": "nested_repository"})
                dirs.remove(d)
            elif d == "__pycache__":
                dirs.remove(d)
            else:
                info = (Path(here) / d).lstat()
                if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
                    issues.append({"file": (Path(here) / d).relative_to(root).as_posix(), "rule": "linked_directory"})
                    dirs.remove(d)
        for leaf in leaves:
            file = Path(here) / leaf
            name = file.relative_to(root).as_posix()
            info = file.lstat()
            if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
                issues.append({"file": name, "rule": "linked_file"})
                continue
            if name not in allowed:
                issues.append({"file": name, "rule": "not_allowlisted"})
                continue
            if file.suffix not in PERMITTED_EXTENSIONS and name not in ("LICENSE", ".gitignore", ".gitattributes"):
                issues.append({"file": name, "rule": "unapproved_file_type"})
            data = file.read_bytes()
            inspect(data, name)
            seen.add(name)
            files.append({"path": name, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()})
    for name in sorted(allowed - seen):
        issues.append({"file": name, "rule": "missing_allowlisted_file"})
    if require_clean and git(root, "status", "--porcelain=v1", "--untracked-files=all").strip():
        issues.append({"rule": "worktree_not_clean"})
    for entry in git(root, "ls-files", "--stage", "-z").split(b"\0"):
        if not entry:
            continue
        header, raw_path = entry.split(b"\t", 1)
        mode, oid, stage = header.decode().split()
        name = raw_path.decode("utf-8")
        if mode not in ("100644", "100755") or stage != "0" or name not in allowed:
            issues.append({"file": name, "rule": "unapproved_index_entry"})
        if mode in ("100644", "100755"):
            inspect(git(root, "cat-file", "blob", oid), "index:" + name)
    commits = []
    if history:
        shallow = git(root, "rev-parse", "--is-shallow-repository").strip()
        if shallow == b"true":
            issues.append({"rule": "shallow_history"})
        elif shallow != b"false":
            raise ValueError("Unable to verify complete Git history.")
        commits = git(root, "rev-list", "--all").decode().splitlines()
    seen_blobs = set()
    for commit in commits:
        inspect(git(root, "cat-file", "-p", commit), "commit:" + commit)
        for entry in git(root, "ls-tree", "-r", "-z", commit).split(b"\0"):
            if not entry:
                continue
            header, raw_path = entry.split(b"\t", 1)
            mode, kind, oid = header.decode().split()
            name = raw_path.decode("utf-8")
            if mode not in ("100644", "100755") or kind != "blob":
                issues.append({"file": name, "rule": "linked_git_object"})
            if name not in allowed:
                issues.append({"file": name, "rule": "historical_file_not_allowlisted"})
            if kind == "blob" and oid not in seen_blobs:
                inspect(git(root, "cat-file", "blob", oid), "history:" + name)
                seen_blobs.add(oid)
    # This initial-release tool intentionally requires a simple, untagged history.
    if history and git(root, "tag", "--list").strip():
        issues.append({"rule": "tags_require_separate_release_review"})
    # Only a passing audit produces an archive manifest. All other locations,
    # including early allowlist/link errors, pass through the same redaction.
    issues = [{**issue, "file": safe_label(issue["file"], terms)} if "file" in issue else issue for issue in issues]
    return {"status": "PASS" if not issues else "BLOCKED", "files": [] if issues else sorted(files, key=lambda x: x["path"]),
        "commits_scanned": len(commits), "private_rules_applied": bool(private_rules), "issues": issues,
        "limits": "Heuristic scan plus exact allowlist; human review remains required."}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument("--private-rules")
    parser.add_argument("--no-history", action="store_true")
    parser.add_argument("--require-clean", action="store_true")
    args = parser.parse_args()
    try:
        result = audit(args.root, args.private_rules, not args.no_history, args.require_clean)
    except (ValueError, OSError, UnicodeError):
        result = {"status": "BLOCKED", "issues": [{"rule": "audit_input_or_git_failure"}]}
    print(json.dumps(result, indent=2))
    return 0 if result["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
