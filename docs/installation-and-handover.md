# Installation and handover

## Reference installation

Clone the public repository into an engine directory. Install Python 3.11 or later. Run `python -m studioflow doctor`, then the tests and the README demo using a private directory outside Git. No package installation or credentials are needed. Optional Blender and FFmpeg discovery reports availability, not verified compatibility.

Acceptance evidence is: successful initialization, generated SVG, verified hashes, matching replay, review ZIP integrity, and delivery blocked until actual approvals are recorded. Keep these receipts in the private installation record.

Choose a parent directory controlled by the operator. New private directories use `0700` and new files, including delivery ZIPs, use `0600` on POSIX. Existing directories and files are not silently re-permissioned. On Windows, configure and verify NTFS ACLs before storing customer data; POSIX mode bits do not establish Windows confidentiality. Keep workspace paths free of links and nested Git worktrees, and prevent untrusted processes from modifying them during operations.

## Production integration checklist

Record the target OS, Python, DCC, renderer, GPU/driver, compositor and encoder versions. Confirm storage and network policy. Integrate one provider at a time using the architecture contract. Keep credentials in a credential manager outside Git. Set an approved budget and disable unexpected fallback or top-up behaviour where supported.

Use one representative customer SKU only after source and rights intake. Establish a product fidelity baseline, one ad placement, a measured revision and a backup restore. Sign off real customer integration separately from this synthetic smoke test. Do not describe a generated installation guide as an installed production service.

## Client package

Provide English navigation, final approved assets, permitted editable sources, a provenance manifest, a reproduction guide, software/dependency versions, acceptance status and support responsibilities. Include only files approved for that audience. Do not include internal costs, provider accounts, personal paths, raw agent conversations or unrelated archives by default.

The CLI manifest exports only each selected asset's path, SHA-256 and byte count. Additional fields in private output records are not copied into review or delivery manifests. Any richer client metadata requires a separate explicit audience review.

Separate delivery approval from publication. Verify the uploaded package by downloading it and comparing SHA-256. A successful upload response alone is not evidence that the client can retrieve intact files.

For support, name the responsible role, contact channel in the private contract, supported versions, included revisions and response target. Test a rollback on a copy. Retain original sources according to the private retention agreement. Removing the public engine should not remove the private customer workspace.
