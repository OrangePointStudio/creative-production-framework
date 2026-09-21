import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from studioflow import core


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


if __name__ == "__main__":
    unittest.main()
