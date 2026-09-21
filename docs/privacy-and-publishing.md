# Privacy and publication

Build a public skeleton in a fresh repository. Do not sanitize an old customer repository by deleting its current files; history can retain the originals. No customer source files, media, fonts, accounts, raw prompts, invoices or screenshots belong here.

`public_allowlist.json` enumerates every allowed file. The scanner checks the working tree, index and reachable commits, rejects links/submodules, unexpected binaries, large encoded payloads, common credentials, personal home paths and private cloud URLs. It reports rule names and locations, masks detected sensitive path labels and omits the file manifest when blocked. Detection remains heuristic, so review diagnostics before sharing them. Tags require separate review. Ignored files other than Python bytecode caches are still inspected in the working tree.

History-enabled audits reject shallow clones. Fetch the complete repository history before release checks; `--no-history` is only a diagnostic option and cannot establish release history clearance. CI explicitly fetches the full history.

Before a release, create private rules outside the repository:

```json
{
  "terms": ["PRIVATE_PROJECT_SENTINEL"],
  "forbidden_sha256": []
}
```

Replace the synthetic sentinel privately with customer names, identifying project terms, account identifiers and other forbidden vocabulary. Add hashes of sensitive source files to `forbidden_sha256`. Never commit this rules file or print its contents in CI.

```powershell
python tools/audit_release.py --private-rules C:/CreativePrivate/release-rules.json
python tools/audit_release.py --private-rules C:/CreativePrivate/release-rules.json --require-clean
python tools/build_public_archive.py --private-rules C:/CreativePrivate/release-rules.json --output C:/CreativePrivate/framework-release.zip
```

Review source and commit metadata manually as well. Stage only exact reviewed paths. Verify the remote tree and a fresh clone against the intended commit. Check the actual repository visibility. Keep security evidence and private deny rules outside public artifacts.

CI uses read-only repository permission, pinned actions, synthetic temporary data and no provider secrets. Do not upload customer files as Actions artifacts or use pull-request workflows with privileged credentials. GitHub platform activity can identify the authenticated publisher even when commit metadata is neutral; a source scan cannot anonymize a hosting account.

Protect the default branch in GitHub settings: require a pull request, require the `test (ubuntu-latest)` and `test (windows-latest)` checks on an up-to-date branch, and block force pushes and deletion. Apply the protections to administrators as well. These hosting settings must be verified separately; a committed workflow does not activate branch protection. Review secret scanning and push protection in the repository's security settings. A CI failure after a public push cannot undo disclosure.

This guard reduces accidental disclosure. It is not a complete DLP service and does not establish a mathematical absence of sensitive data. Public release requires deliberate review every time.
