"""Create an allowlisted source-only archive outside the checkout after audit."""
import argparse
import hashlib
import json
import zipfile
from pathlib import Path
from audit_release import audit


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--private-rules")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    out = Path(args.output).resolve()
    if out == root or root in out.parents or out.exists():
        raise SystemExit("Choose a new output archive outside the repository.")
    result = audit(root, args.private_rules, require_clean=True)
    if result["status"] != "PASS":
        raise SystemExit("Publication audit blocked. Run the audit command for rule identifiers.")
    out.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out, "x", compression=zipfile.ZIP_DEFLATED) as archive:
        for entry in result["files"]:
            data = (root / entry["path"]).read_bytes()
            if hashlib.sha256(data).hexdigest() != entry["sha256"]:
                raise SystemExit("Content changed after audit. Discard this incomplete archive.")
            archive.writestr(entry["path"], data)
        archive.writestr("PUBLIC_MANIFEST.json", json.dumps(result["files"], indent=2))
    with zipfile.ZipFile(out) as archive:
        assert archive.testzip() is None
    print(json.dumps({"status": "PASS", "files": len(result["files"]),
        "sha256": hashlib.sha256(out.read_bytes()).hexdigest()}))


if __name__ == "__main__":
    main()
