# Security and privacy

Do not put secrets or customer data in issues, pull requests, screenshots or test fixtures. Use the repository's private vulnerability reporting feature if available. Otherwise ask the maintainers for a private reporting channel without including sensitive details in the public request.

The release scanner is a heuristic aid. It cannot prove the absence of every form of personal data, encoded secret or sensitive business information. Its exact allowlist, history inspection and optional private vocabulary must be combined with human review. Customer media is intentionally outside its supported public file types.

If a credential was exposed, revoke it with its provider first. Removing a file or rewriting history cannot remove copies already obtained by others. Preserve restricted incident evidence; do not reproduce the secret in a public issue. Review Git history, releases, Actions logs and artifacts as separate publication surfaces.

No provider credentials are needed by this reference implementation. Future adapters must use an external credential store, restricted scopes, deliberate network access, scrubbed logs and an explicit cost budget. A Git ignore rule alone is not a security boundary.
