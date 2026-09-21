# Security and privacy

Do not put secrets or customer data in issues, pull requests, screenshots or test fixtures. Use the repository's private vulnerability reporting feature if available. Otherwise ask the maintainers for a private reporting channel without including sensitive details in the public request.

The release scanner is a heuristic aid. It cannot prove the absence of every form of personal data, encoded secret or sensitive business information. Its exact allowlist, history inspection and optional private vocabulary must be combined with human review. Customer media is intentionally outside its supported public file types.

If a credential was exposed, revoke it with its provider first. Removing a file or rewriting history cannot remove copies already obtained by others. Preserve restricted incident evidence; do not reproduce the secret in a public issue. Review Git history, releases, Actions logs and artifacts as separate publication surfaces.

No provider credentials are needed by this reference implementation. Future adapters must use an external credential store, restricted scopes, deliberate network access, scrubbed logs and an explicit cost budget. A Git ignore rule alone is not a security boundary.

Private workspace checks reject linked paths and Git worktrees before file operations. Use a trusted, access-controlled parent directory: path checks are not a sandbox against a process that can replace paths concurrently. Newly created private directories and files use owner-only POSIX permissions; existing permissions, Windows ACLs and backup access remain operator responsibilities.

Delivery manifests contain only selected asset paths, hashes and byte counts. Keep adapter prompts, account identifiers, provider responses and internal costs in private records. Local approval JSON is editable evidence, not authenticated authorization.

History-enabled release checks require a complete clone. Pattern detection covers common credential assignments, including quoted JSON keys and unquoted YAML values, but does not validate every secret format. Sensitive path labels are masked and blocked audits omit the file manifest. Keep private vocabulary rules current and review diagnostics before sharing them.

Commit author and committer headers may use GitHub's public no-reply aliases or its service no-reply address. This narrow metadata exception does not apply to file contents, filenames or commit messages. Private vocabulary and all other detectors still inspect the original headers; a no-reply alias is not an identity signature or proof of authorization.
