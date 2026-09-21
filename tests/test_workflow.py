import contextlib
import io
import json
import os
import stat
import tempfile
import unittest
import zipfile
from pathlib import Path

from studioflow import cli, core


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.root = self.base / "project"
        core.initialize(self.root)

    def run_first(self):
        return core.run_demo(self.root, "first")

    def test_replay_uses_frozen_input(self):
        first = self.run_first()
        brief = core.read_json(self.root / "brief.json")
        brief["demo_colour"] = "#123456"
        (self.root / "brief.json").write_bytes(core.dump(brief))
        replay = core.run_demo(self.root, "replay", "first")
        self.assertEqual(first["output_sha256"], replay["output_sha256"])
        self.assertNotEqual(first["output_sha256"], core.run_demo(self.root, "revision")["output_sha256"])

    def test_tampered_output_is_rejected(self):
        self.run_first()
        (self.root / "outputs/first/demo.svg").write_text("changed")
        with self.assertRaises(core.WorkflowError):
            core.verify(self.root, "first")

    def test_tampered_frozen_input_is_rejected(self):
        self.run_first()
        (self.root / "work/frozen/first.json").write_text("{}")
        with self.assertRaises(core.WorkflowError):
            core.run_demo(self.root, "replay", "first")

    def test_no_overwrite(self):
        self.run_first()
        with self.assertRaises(core.WorkflowError):
            self.run_first()
        with self.assertRaises(core.WorkflowError):
            core.initialize(self.root)

    def test_git_workspace_is_rejected(self):
        repo = self.base / "repo"
        (repo / ".git").mkdir(parents=True)
        with self.assertRaises(core.WorkflowError):
            core.initialize(repo / "private")
        with self.assertRaises(core.WorkflowError):
            core.initialize(core.ENGINE_ROOT / "private")

    def test_traversal_is_rejected(self):
        for path in ("../outside", "/absolute", "C:/absolute", "outputs/../../outside", "outputs\\file"):
            with self.subTest(path=path), self.assertRaises(core.WorkflowError):
                core.inside(self.root, path)

    def test_bad_record_shapes_fail_safely(self):
        self.run_first()
        path = self.root / "selections/first.json"
        for value in ([], {"schema_version": 1, "run_id": "first", "paths": [{}]}):
            path.write_bytes(core.dump(value))
            with self.assertRaises(core.WorkflowError):
                core.export_selection(self.root, "first", self.base / "review.zip")

    def test_review_export_contains_no_sources_or_private_ledger(self):
        self.run_first()
        (self.root / "sources/private.txt").write_text("PRIVATE FIXTURE")
        output = self.base / "review.zip"
        core.export_selection(self.root, "first", output)
        with zipfile.ZipFile(output) as archive:
            self.assertEqual(set(archive.namelist()), {"outputs/first/demo.svg", "MANIFEST.json"})
            self.assertIsNone(archive.testzip())
            self.assertEqual(json.loads(archive.read("MANIFEST.json"))["audience"], "review")
        with self.assertRaises(core.WorkflowError):
            core.export_selection(self.root, "first", output)

    def test_delivery_requires_all_gates_bound_to_hash(self):
        self.run_first()
        destination = self.base / "delivery.zip"
        with self.assertRaises(core.WorkflowError):
            core.export_selection(self.root, "first", destination, True)
        self.assertFalse(destination.exists())
        path = self.root / "approvals/first.json"
        approval = core.read_json(path)
        for gate in core.GATES:
            approval["gates"][gate] = {"status": "approved", "reviewer_role": "test reviewer", "recorded_at": "synthetic-test"}
        expected = approval["selection_sha256"]
        approval["selection_sha256"] = "wrong"
        path.write_bytes(core.dump(approval))
        with self.assertRaises(core.WorkflowError):
            core.export_selection(self.root, "first", destination, True)
        approval["selection_sha256"] = expected
        path.write_bytes(core.dump(approval))
        self.assertEqual(core.export_selection(self.root, "first", destination, True)["audience"], "delivery")

    def test_source_cannot_be_added_to_selection(self):
        self.run_first()
        path = self.root / "selections/first.json"
        value = core.read_json(path)
        value["paths"] = ["brief.json"]
        path.write_bytes(core.dump(value))
        with self.assertRaises(core.WorkflowError):
            core.export_selection(self.root, "first", self.base / "review.zip")

    def test_unknown_cost_is_not_zero_and_units_stay_separate(self):
        (self.root / "records/costs.csv").write_text(
            "provider,unit,quantity,currency,paid_amount,phase\n"
            "a,credits,4,,,setup\nb,credits,2,USD,1.50,production\n"
            "a,seconds,10,EUR,2.20,revision\n")
        result = core.summarize_costs(self.root)
        self.assertEqual(result["unknown_allocation_rows"], 1)
        self.assertEqual(result["recorded_allocations_by_currency"], {"USD": "1.50", "EUR": "2.20"})
        self.assertEqual(len(result["quantities_by_provider_and_unit"]), 3)
        self.assertIsNone(result["whole_project_total"])

    def test_no_network_for_any_demo_lane(self):
        for lane in ("cloud", "hybrid", "local"):
            root = self.base / lane
            core.initialize(root, lane)
            core.run_demo(root, "first")
            self.assertEqual(core.verify(root, "first")["provider_calls"], 0)

    def test_real_brief_is_not_rendered_as_demo(self):
        brief = core.read_json(self.root / "brief.json")
        brief["fictional_example"] = False
        (self.root / "brief.json").write_bytes(core.dump(brief))
        with self.assertRaises(core.WorkflowError):
            self.run_first()

    def test_symlink_is_rejected_when_supported(self):
        link = self.base / "linked"
        try:
            link.symlink_to(self.root, target_is_directory=True)
        except OSError:
            self.skipTest("Creating links requires additional OS privileges")
        with self.assertRaises(core.WorkflowError):
            core.workspace(link)

    def make_link(self, link, target, directory=False):
        try:
            link.symlink_to(target, target_is_directory=directory)
        except OSError:
            self.skipTest("Creating links requires additional OS privileges")

    def test_linked_frozen_directory_is_rejected_before_any_run_write(self):
        external = self.base / "external-repository"
        (external / ".git").mkdir(parents=True)
        (self.root / "work/frozen").rmdir()
        self.make_link(self.root / "work/frozen", external, directory=True)
        with self.assertRaises(core.WorkflowError):
            self.run_first()
        self.assertFalse((external / "first.json").exists())
        self.assertFalse((self.root / "outputs/first").exists())
        self.assertFalse((self.root / "records/first.json").exists())

    def test_linked_brief_is_rejected_before_reading_or_rendering(self):
        external = self.base / "external-brief.json"
        (self.root / "brief.json").rename(external)
        self.make_link(self.root / "brief.json", external)
        with self.assertRaises(core.WorkflowError):
            self.run_first()
        self.assertFalse((self.root / "outputs/first").exists())

    def test_all_control_records_reject_symlink_reads(self):
        self.run_first()
        for name, operation in (
                ("workspace.json", lambda: core.workspace(self.root)),
                ("records/first.json", lambda: core.verify(self.root, "first")),
                ("work/frozen/first.json", lambda: core.run_demo(self.root, "replay", "first")),
                ("selections/first.json", lambda: core.export_selection(self.root, "first", self.base / "review.zip")),
                ("approvals/first.json", lambda: core.export_selection(self.root, "first", self.base / "delivery.zip", True)),
                ("records/costs.csv", lambda: core.summarize_costs(self.root))):
            with self.subTest(record=name):
                original = self.root / name
                external = self.base / "external-record"
                original.rename(external)
                self.make_link(original, external)
                try:
                    with self.assertRaises(core.WorkflowError):
                        operation()
                finally:
                    original.unlink()
                    external.rename(original)
        self.assertFalse((self.base / "review.zip").exists())
        self.assertFalse((self.base / "delivery.zip").exists())

    def test_nested_git_directory_blocks_writes_and_reads(self):
        marker = self.root / "outputs/.git"
        marker.mkdir()
        with self.assertRaises(core.WorkflowError):
            self.run_first()
        self.assertFalse((self.root / "outputs/first").exists())
        marker.rmdir()
        self.run_first()
        marker.mkdir()
        with self.assertRaises(core.WorkflowError):
            core.verify(self.root, "first")
        with self.assertRaises(core.WorkflowError):
            core.export_selection(self.root, "first", self.base / "review.zip")
        self.assertFalse((self.base / "review.zip").exists())

    def test_export_manifest_omits_private_receipt_metadata_after_approval(self):
        self.run_first()
        approval_path = self.root / "approvals/first.json"
        approval = core.read_json(approval_path)
        for gate in core.GATES:
            approval["gates"][gate] = {"status": "approved", "reviewer_role": "test reviewer",
                                        "recorded_at": "synthetic-test"}
        approval_path.write_bytes(core.dump(approval))
        receipt_path = self.root / "records/first.json"
        receipt = core.read_json(receipt_path)
        receipt["outputs"][0]["private_metadata"] = {"note": "SYNTHETIC_PRIVATE_MARKER"}
        receipt["outputs"][0]["kind"] = "SYNTHETIC_PRIVATE_MARKER"
        receipt_path.write_bytes(core.dump(receipt))
        for delivery in (False, True):
            with self.subTest(delivery=delivery):
                destination = self.base / ("delivery.zip" if delivery else "review.zip")
                core.export_selection(self.root, "first", destination, delivery)
                with zipfile.ZipFile(destination) as archive:
                    metadata = archive.read("MANIFEST.json")
                    self.assertNotIn(b"SYNTHETIC_PRIVATE_MARKER", metadata)
                    manifest = json.loads(metadata)
                    self.assertEqual(set(manifest["files"][0]), {"path", "sha256", "bytes"})
                    self.assertEqual(manifest["selection_sha256"], approval["selection_sha256"])

    @unittest.skipUnless(os.name == "posix", "POSIX mode bits do not establish Windows ACLs")
    def test_created_private_paths_restrict_permissions_under_umask_022(self):
        parent = self.base / "new-parent"
        root = parent / "project"
        destination = self.base / "new-export-parent/nested/review.zip"
        old_umask = os.umask(0o022)
        try:
            core.initialize(root)
            core.run_demo(root, "first")
            core.export_selection(root, "first", destination)
        finally:
            os.umask(old_umask)
        for path in [parent, *parent.rglob("*"), destination.parent.parent,
                     destination.parent, destination]:
            with self.subTest(path=path.relative_to(self.base)):
                self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o700 if path.is_dir() else 0o600)

    def assert_cli_blocked(self, arguments):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            result = cli.main(arguments)
        self.assertEqual(result, 2)
        failure = json.loads(output.getvalue())
        self.assertEqual(failure["status"], "blocked")
        self.assertNotIn(str(self.base), output.getvalue())

    def test_malformed_workspace_lane_is_a_safe_cli_failure(self):
        path = self.root / "workspace.json"
        marker = core.read_json(path)
        for value in (None, {}, "unsupported"):
            with self.subTest(lane=value):
                marker["lane"] = value
                path.write_bytes(core.dump(marker))
                self.assert_cli_blocked(["demo", str(self.root), "--run", "first"])
        del marker["lane"]
        path.write_bytes(core.dump(marker))
        self.assert_cli_blocked(["demo", str(self.root), "--run", "first"])
        self.assertFalse((self.root / "outputs/first").exists())

    def test_malformed_receipts_are_safe_cli_failures(self):
        self.run_first()
        path = self.root / "records/first.json"
        original = path.read_bytes()
        mutations = (
            lambda receipt: receipt.update(schema_version=True),
            lambda receipt: receipt.update(frozen_source=[]),
            lambda receipt: receipt.update(outputs=[{}]),
            lambda receipt: receipt["outputs"][0].update(path="outputs/first/\x00"),
            lambda receipt: receipt["outputs"][0].update(path="outputs/first/\ud800"),
            lambda receipt: receipt["outputs"][0].update(sha256=[]),
            lambda receipt: receipt["outputs"][0].update(bytes="invalid"),
            lambda receipt: receipt["outputs"].append(dict(receipt["outputs"][0])),
        )
        for mutation in mutations:
            receipt = json.loads(original)
            mutation(receipt)
            path.write_bytes(core.dump(receipt))
            self.assert_cli_blocked(["verify", str(self.root), "--run", "first"])

    def test_malformed_cost_rows_are_safe_cli_failures(self):
        path = self.root / "records/costs.csv"
        header = "provider,unit,quantity,currency,paid_amount,phase\n"
        for row in ("a,credits,1\n", "a,credits,1e999999999,USD,1,production\n"):
            path.write_text(header + row)
            self.assert_cli_blocked(["costs", str(self.root)])

    def test_malformed_approval_values_are_safe_cli_failures(self):
        self.run_first()
        path = self.root / "approvals/first.json"
        approval = core.read_json(path)
        for gate in core.GATES:
            approval["gates"][gate] = {"status": "approved", "reviewer_role": "test reviewer",
                                        "recorded_at": "synthetic-test"}
        for value in ([], 1, "   "):
            approval["gates"]["client"]["reviewer_role"] = value
            path.write_bytes(core.dump(approval))
            self.assert_cli_blocked(["export", str(self.root), "--run", "first",
                                     "--output", str(self.base / "delivery.zip"), "--delivery"])
        self.assertFalse((self.base / "delivery.zip").exists())


if __name__ == "__main__":
    unittest.main()
