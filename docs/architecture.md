# Architecture

The public engine and a private workspace are separate filesystem roots. The engine has no customer configuration. One private workspace belongs to one project and is never a Git worktree.

```text
private workspace/
  workspace.json          version and lane
  brief.json              current working brief
  sources/                originals and provenance
  work/frozen/            immutable run inputs
  outputs/                versioned renders
  records/                private run receipts and cost ledger
  approvals/              evidence for four independent gates
  selections/             explicit output paths for export
```

The CLI implements only a synthetic renderer. Production adapters are a contract to build and validate, not installed functionality.

| Lane | Product authority | Environment and finishing |
| --- | --- | --- |
| Cloud | Approved references; every generated label and form must be checked | Named online image/video provider plus deliberate finishing |
| Hybrid | Controlled local product master and label texture | Local render, online environment, local composite |
| Local | Controlled DCC master or explicitly selected local model | Local rendering, compositing and encoding |

Cloud coordination of a local renderer does not make the whole operation offline. Record that distinction. The engine must never route a failed local job to a paid cloud provider automatically.

## Adapter contract

An adapter accepts a validated private brief, explicit source file hashes, ordered reference list, selected provider/model version, format, seed if available, budget and output directory. It returns an immutable receipt with output hashes, actual dimensions/fps, elapsed time, native versus transformed format, retry cause and measured billing units. Store provider task identifiers privately.

Separate product fidelity from atmosphere generation. Do not infer normal/depth conditioning support from an ordinary reference-image input. Record colour management and whether normals are world, camera or tangent space. Preserve linear EXR data for depth, normals and masks; do not bake a display transform into those data passes.

Serialize GPU-heavy tasks per device. One owner writes the shared product master. Failed outputs still incur measured cost and retain their rejection reason. Reuse a master without charging its setup repeatedly.
