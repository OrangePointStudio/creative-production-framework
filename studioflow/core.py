"""Standard-library-only reference implementation. No network or provider calls."""

import csv
import hashlib
import io
import json
import re
import shutil
import stat
import sys
import zipfile
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path

VERSION = "0.1.0"
ENGINE_ROOT = Path(__file__).resolve().parents[1]
GATES = ("technical", "creative", "rights", "client")
ID_PATTERN = re.compile(r"[a-z0-9][a-z0-9-]{0,63}\Z")


class WorkflowError(ValueError):
    """A safe, actionable failure without provider payloads or credential values."""


def digest(data):
    return hashlib.sha256(data).hexdigest()


def dump(value):
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True) + "\n").encode()


def read_json(path):
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            raise ValueError("Expected an object")
        return value
    except (ValueError, OSError) as exc:
        raise WorkflowError("Required JSON record is missing or invalid.") from exc


def write_new(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        stream.write(data)


def has_link(path):
    """Reject symlinks and Windows reparse points in existing path components."""
    for part in (path, *path.parents):
        if part.exists() or part.is_symlink():
            info = part.lstat()
            if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
                return True
    return False


def private_path(value):
    path = Path(value).absolute()
    if has_link(path):
        raise WorkflowError("Private workspaces cannot use linked path components.")
    path = path.resolve()
    if path == ENGINE_ROOT or ENGINE_ROOT in path.parents:
        raise WorkflowError("Use a private workspace outside the engine repository.")
    if any((parent / ".git").exists() for parent in (path, *path.parents)):
        raise WorkflowError("Private production workspaces must be outside Git worktrees.")
    return path


def workspace(value):
    root = private_path(value)
    marker = read_json(root / "workspace.json")
    if marker.get("schema_version") != 1:
        raise WorkflowError("Unsupported workspace schema. Do not upgrade in place.")
    return root


def identifier(value):
    if not isinstance(value, str) or not ID_PATTERN.fullmatch(value):
        raise WorkflowError("Use a short lowercase identifier with digits or hyphens.")
    return value


def inside(root, relative):
    if not isinstance(relative, str) or not relative or "\\" in relative:
        raise WorkflowError("Record paths must use nonempty relative POSIX paths.")
    path = Path(relative)
    if path.is_absolute() or ":" in relative or any(p in (".", "..") for p in relative.split("/")):
        raise WorkflowError("Unsafe record path.")
    target = root / path
    if has_link(target) or root not in target.resolve().parents:
        raise WorkflowError("Record path escapes its private workspace.")
    return target


def initialize(value, lane="local"):
    root = private_path(value)
    if lane not in ("cloud", "hybrid", "local"):
        raise WorkflowError("Unknown production lane.")
    if root.exists():
        raise WorkflowError("Workspace already exists. Existing files are never replaced.")
    root.mkdir(parents=True)
    for name in ("sources", "work/frozen", "outputs", "records", "approvals", "selections"):
        (root / name).mkdir(parents=True)
    write_new(root / "workspace.json", dump({"schema_version": 1, "engine_version": VERSION,
        "lane": lane, "fictional_example": True, "network_enabled": False}))
    write_new(root / "brief.json", dump({"schema_version": 1, "fictional_example": True,
        "product_id": "sample-object", "message": "SYNTHETIC DEMO", "claims": [],
        "format": {"width": 512, "height": 512}, "demo_colour": "#607d8b"}))
    write_new(root / "records/costs.csv", b"provider,unit,quantity,currency,paid_amount,phase\n")
    return {"status": "initialized", "lane": lane, "schema_version": 1}


def svg_bytes(brief):
    if brief.get("fictional_example") is not True:
        raise WorkflowError("The demo renderer accepts fictional examples only.")
    colour = brief.get("demo_colour")
    if not isinstance(colour, str) or not re.fullmatch(r"#[0-9a-fA-F]{6}", colour):
        raise WorkflowError("Invalid synthetic demo colour.")
    # Deliberately neutral geometry. No customer marks, labels or product template.
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="512" height="512" viewBox="0 0 512 512">'
        '<rect width="512" height="512" fill="#f4f4f4"/>'
        f'<rect x="136" y="116" width="240" height="240" rx="12" fill="{colour}"/>'
        '<text x="256" y="415" text-anchor="middle" font-family="sans-serif" '
        'font-size="20" fill="#303030">SYNTHETIC DEMO</text></svg>\n').encode()


def run_demo(value, run_id, replay_from=None):
    root = workspace(value)
    run_id = identifier(run_id)
    targets = [root / f"outputs/{run_id}", root / f"records/{run_id}.json",
        root / f"work/frozen/{run_id}.json", root / f"approvals/{run_id}.json",
        root / f"selections/{run_id}.json"]
    if any(p.exists() for p in targets):
        raise WorkflowError("Run identifier already exists. Choose a new revision.")
    if replay_from:
        previous = verify(value, identifier(replay_from))
        frozen = root / f"work/frozen/{replay_from}.json"
        brief = read_json(frozen)
        expected = previous["outputs"][0]["sha256"]
    else:
        brief = read_json(root / "brief.json")
        expected = None
    image = svg_bytes(brief)
    if expected and digest(image) != expected:
        raise WorkflowError("Frozen-source replay differs. Preserve both versions for review.")
    frozen_bytes = dump(brief)
    output = {"path": f"outputs/{run_id}/demo.svg", "sha256": digest(image),
        "bytes": len(image), "kind": "synthetic_demo"}
    receipt = {"schema_version": 1, "run_id": run_id, "engine_version": VERSION,
        "renderer": "synthetic-svg-v1", "lane": read_json(root / "workspace.json")["lane"],
        "created_utc": datetime.now(timezone.utc).isoformat(), "outputs": [output],
        "frozen_source": {"path": f"work/frozen/{run_id}.json", "sha256": digest(frozen_bytes)},
        "replay_from": replay_from, "provider_calls": 0, "generation_cost": None,
        "scope": "deterministic synthetic demonstration; not generative-model performance"}
    write_new(targets[0] / "demo.svg", image)
    write_new(targets[1], dump(receipt))
    write_new(targets[2], frozen_bytes)
    selection = {"schema_version": 1, "run_id": run_id, "paths": [output["path"]]}
    write_new(targets[4], dump(selection))
    write_new(targets[3], dump({"schema_version": 1, "selection_sha256": selection_hash([output]),
        "gates": {gate: {"status": "pending", "reviewer_role": None, "recorded_at": None}
                  for gate in GATES}}))
    return {"status": "rendered", "run_id": run_id, "output_sha256": digest(image),
        "replay_match": True if expected else None, "human_acceptance": "pending"}


def verify(value, run_id):
    root = workspace(value)
    record = read_json(root / f"records/{identifier(run_id)}.json")
    if record.get("schema_version") != 1 or record.get("run_id") != run_id:
        raise WorkflowError("Run receipt schema or identity mismatch.")
    outputs = record.get("outputs")
    if not isinstance(outputs, list) or not outputs:
        raise WorkflowError("Run receipt has no outputs.")
    for item in [*outputs, record.get("frozen_source", {})]:
        if not isinstance(item, dict):
            raise WorkflowError("Invalid run receipt item.")
        path = inside(root, item.get("path"))
        if not path.is_file() or digest(path.read_bytes()) != item.get("sha256"):
            raise WorkflowError("Run content changed or is missing. Approval is no longer valid.")
    return record


def selection_hash(outputs):
    return digest(dump(sorted(({"path": x["path"], "sha256": x["sha256"]} for x in outputs),
                             key=lambda x: x["path"])))


def export_selection(value, run_id, destination, delivery=False):
    root = workspace(value)
    record = verify(value, run_id)
    chosen = read_json(root / f"selections/{run_id}.json")
    paths = chosen.get("paths")
    if chosen.get("schema_version") != 1 or chosen.get("run_id") != run_id:
        raise WorkflowError("Invalid selection record.")
    if not isinstance(paths, list) or not paths or any(not isinstance(p, str) for p in paths) or len(paths) != len(set(paths)):
        raise WorkflowError("Selection must contain unique explicit output paths.")
    permitted = {x["path"]: x for x in record["outputs"]}
    if any(p not in permitted or not p.startswith(f"outputs/{run_id}/") for p in paths):
        raise WorkflowError("Only explicitly selected outputs from this run can be exported.")
    selected = [permitted[p] for p in paths]
    fingerprint = selection_hash(selected)
    if delivery:
        approval = read_json(root / f"approvals/{run_id}.json")
        if approval.get("selection_sha256") != fingerprint:
            raise WorkflowError("Approval does not match the exact selected assets.")
        gates = approval.get("gates")
        if not isinstance(gates, dict):
            raise WorkflowError("Approval gates must be an object.")
        for gate in GATES:
            item = gates.get(gate, {})
            if not isinstance(item, dict):
                raise WorkflowError("Invalid approval gate.")
            if item.get("status") != "approved" or not item.get("reviewer_role") or not item.get("recorded_at"):
                raise WorkflowError("Delivery requires all four recorded approval gates.")
    output = private_path(destination)
    if output.exists() or output.suffix.lower() != ".zip":
        raise WorkflowError("Choose a new ZIP path outside Git worktrees.")
    output.parent.mkdir(parents=True, exist_ok=True)
    metadata = {"schema_version": 1, "audience": "delivery" if delivery else "review",
        "selection_sha256": fingerprint, "files": selected,
        "publication": "Export does not publish media or grant third-party rights."}
    with zipfile.ZipFile(output, "x", compression=zipfile.ZIP_DEFLATED) as archive:
        for item in selected:
            data = inside(root, item["path"]).read_bytes()
            if digest(data) != item["sha256"]:
                raise WorkflowError("Output changed during export. Discard the incomplete ZIP.")
            archive.writestr(item["path"], data)
        archive.writestr("MANIFEST.json", dump(metadata))
    with zipfile.ZipFile(output) as archive:
        if archive.testzip() is not None:
            raise WorkflowError("Export integrity verification failed.")
    return {"status": "exported", "audience": metadata["audience"], "files": len(selected),
        "sha256": digest(output.read_bytes()), "selection_sha256": fingerprint}


def summarize_costs(value):
    root = workspace(value)
    try:
        rows = list(csv.DictReader((root / "records/costs.csv").read_text(encoding="utf-8").splitlines()))
        quantities, amounts, unknown = {}, {}, 0
        for row in rows:
            if row["phase"] not in ("setup", "production", "revision"):
                raise WorkflowError("Unknown cost phase.")
            number = Decimal(row["quantity"])
            if not number.is_finite() or number < 0:
                raise WorkflowError("Invalid cost quantity.")
            key = row["provider"] + ":" + row["unit"]
            quantities[key] = quantities.get(key, Decimal(0)) + number
            if not row["paid_amount"] or not row["currency"]:
                unknown += 1
                continue
            money = Decimal(row["paid_amount"])
            if not money.is_finite() or money < 0 or not re.fullmatch(r"[A-Z]{3}", row["currency"]):
                raise WorkflowError("Invalid paid allocation or currency.")
            amounts[row["currency"]] = amounts.get(row["currency"], Decimal(0)) + money
    except (KeyError, InvalidOperation, OSError) as exc:
        raise WorkflowError("Invalid cost ledger.") from exc
    return {"quantities_by_provider_and_unit": {k: str(v) for k, v in quantities.items()},
        "recorded_allocations_by_currency": {k: str(v) for k, v in amounts.items()},
        "unknown_allocation_rows": unknown, "ledger_complete": bool(rows) and unknown == 0,
        "whole_project_total": None, "note": "The ledger does not prove that every project cost was recorded."}


def doctor():
    return {"engine_version": VERSION, "python_supported": sys.version_info >= (3, 11),
        "optional_tools": {name: bool(shutil.which(name)) for name in ("blender", "ffmpeg", "git")},
        "network_calls": False, "provider_adapters": "not included in the reference skeleton"}
