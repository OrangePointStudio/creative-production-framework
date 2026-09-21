# Creative Production Framework

An MIT-licensed, English-language reference skeleton for a repeatable creative production service. Keep the reusable engine in Git and every real project in a separate private workspace.

This repository contains original generic documentation and a deterministic synthetic SVG demo. It contains no customer work, production media, private prompts, provider accounts or credentials. It is not a finished image-generation service: cloud adapters, DCC automation and customer deployment are integration work.

## Start locally

Use Python 3.11 or later and Git. No Python packages, API keys or paid calls are required for the reference demo. Run these commands from the repository directory. Choose a new private directory outside every Git worktree.

```powershell
python -m studioflow doctor
python -m studioflow init C:/CreativePrivate/demo --lane local
python -m studioflow demo C:/CreativePrivate/demo --run first
python -m studioflow verify C:/CreativePrivate/demo --run first
python -m studioflow replay C:/CreativePrivate/demo --run first --new-run replay
python -m studioflow export C:/CreativePrivate/demo --run first --output C:/CreativePrivate/review.zip
python -m studioflow costs C:/CreativePrivate/demo
```

On macOS/Linux, substitute `python3` and a writable private path such as `/tmp/creative-private/demo`. Existing workspaces, run IDs and ZIP files are never overwritten. The demo produces a neutral square, not a customer product. It renders 512 by 512 regardless of any production format plans.

## What is implemented

| Capability | Reference implementation |
| --- | --- |
| Private workspace | Rejects locations inside Git and linked path components |
| Traceability | Frozen input, SHA-256 receipt, explicit run and selection records |
| Replay | Identical synthetic output from verified frozen input |
| Acceptance | Technical, creative, rights and client gates bound to selected asset hashes |
| Export | Selected outputs and manifest only; separate review and delivery modes |
| Cost ledger | Provider units and currencies remain separate; missing cost is never zero |
| Publication checks | Exact file allowlist, text and history scan, private deny rules, clean release archive |

The `cloud`, `hybrid` and `local` lane values record intent. The included renderer remains offline in all three lanes. No external model is silently substituted. Human approval records are editable local evidence, not cryptographic identity signatures.

## Use the guides

1. [Architecture and adapter contract](docs/architecture.md)
2. [Operator workflow](docs/operator-guide.md)
3. [Quality and acceptance](docs/quality-gates.md)
4. [Reproduction and revision](docs/reproducibility.md)
5. [Cost accounting](docs/cost-model.md)
6. [Installation and handover](docs/installation-and-handover.md)
7. [Privacy and publication](docs/privacy-and-publishing.md)
8. [Controlled commercial pilot](docs/commercial-pilot.md)

## Verify before release

```powershell
python -m unittest discover -s tests -v
python tools/audit_release.py
```

Commit only reviewed, explicitly named files. Then run the audit with `--require-clean`. For a real release, also supply `--private-rules` pointing to a private JSON file outside the repository; see the privacy guide. CI runs only synthetic tests and never connects to creative providers.

The MIT license covers the software and generic documentation here. It grants no rights to a customer's media, trademarks, likenesses, provider output or third-party tools. See [LICENSE](LICENSE) and [SECURITY.md](SECURITY.md).
