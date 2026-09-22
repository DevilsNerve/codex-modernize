"""Behavioral regression tests for filesystem, rendering, and batch helpers."""
import copy
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("modernize", ROOT / "plugins/codex-modernize/scripts/modernize.py")
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class WorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="modernize test ")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.source = self.root / "legacy/billing"
        self.source.mkdir(parents=True)
        (self.source / "source.txt").write_text("original\n")
        self.ws = m.Workspace(self.root, "billing")

    def test_paths_are_read_only(self):
        self.assertEqual(self.ws.as_dict()["source"], str(self.source))
        self.assertFalse((self.root / "analysis").exists())
        self.assertFalse((self.root / "modernized").exists())

    def test_reject_system_traversal_and_shell_input(self):
        for name in ("../escape", "/tmp", "x;touch x", "$(id)", "a\nb", "CON"):
            with self.subTest(name=name), self.assertRaises(m.ValidationError):
                m.Workspace(self.root, name)

    def test_linked_source_supported_and_never_overwritten(self):
        (self.root / "legacy/linked").symlink_to(self.source, target_is_directory=True)
        ws = m.Workspace(self.root, "linked")
        result = m.copy_source(ws)
        target = Path(result["copy"]) / "source.txt"
        target.write_text("changed")
        self.assertEqual((self.source / "source.txt").read_text(), "original\n")

    def test_output_symlink_rejected_even_inside_workspace(self):
        (self.root / "analysis").symlink_to(self.source, target_is_directory=True)
        with self.assertRaises(m.ValidationError):
            m.Workspace(self.root, "billing")

    def test_source_cannot_contain_outputs(self):
        (self.root / "legacy/whole").symlink_to(self.root, target_is_directory=True)
        with self.assertRaises(m.ValidationError):
            m.Workspace(self.root, "whole")

    def test_copy_excludes_git_and_preserves_internal_link_content(self):
        (self.source / ".git").mkdir()
        (self.source / ".git/config").write_text("private VCS state")
        (self.source / "alias.txt").symlink_to("source.txt")
        m.copy_source(self.ws)
        self.assertFalse((self.ws.uplift / ".git").exists())
        self.assertFalse((self.ws.uplift / "alias.txt").is_symlink())
        self.assertEqual((self.ws.uplift / "alias.txt").read_text(), "original\n")

    def test_copy_refuses_existing_destination(self):
        m.copy_source(self.ws)
        (self.ws.uplift / "work.txt").write_text("user work")
        with self.assertRaises(m.ValidationError):
            m.copy_source(self.ws)
        self.assertEqual((self.ws.uplift / "work.txt").read_text(), "user work")

    def test_copy_rejects_escaping_link_before_writing(self):
        external = self.root / "outside.txt"
        external.write_text("outside")
        (self.source / "escape").symlink_to(external)
        with self.assertRaises(m.ValidationError):
            m.copy_source(self.ws)
        self.assertFalse(self.ws.uplift.exists())

    def test_copy_rejects_link_cycle(self):
        (self.source / "loop").symlink_to(self.source, target_is_directory=True)
        with self.assertRaises(m.ValidationError):
            m.copy_source(self.ws)

    def fixture(self):
        return json.loads((ROOT / "tests/fixtures/topology.json").read_text())

    def test_renderer_escapes_script_breakout_and_is_offline(self):
        data = self.fixture()
        payload = '</script><script>globalThis.INJECTED=true</script>'
        data["system"] = payload
        self.ws.analysis.mkdir(parents=True)
        (self.ws.analysis / "topology.json").write_text(json.dumps(data))
        result = m.render_topology(self.ws)
        output = Path(result["output"]).read_text()
        self.assertNotIn(payload, output)
        self.assertIn(r"\u003c/script\u003e", output)
        self.assertNotIn('<script src=', output)
        self.assertIn("default-src 'none'", output)
        self.assertEqual(result["nodes"], 6)

    def test_renderer_rejects_broken_references_without_output(self):
        data = self.fixture()
        data["edges"][0]["target"] = "missing"
        self.ws.analysis.mkdir(parents=True)
        (self.ws.analysis / "topology.json").write_text(json.dumps(data))
        with self.assertRaises(m.ValidationError):
            m.render_topology(self.ws)
        self.assertFalse((self.ws.analysis / "TOPOLOGY.html").exists())

    def test_topology_duplicate_ids_invalid_loc_and_flow_refs(self):
        for change in ("duplicate", "loc", "flow"):
            data = self.fixture()
            node = data["root"]["children"][0]["children"][0]
            if change == "duplicate": node["id"] = "sys"
            if change == "loc": node["loc"] = float("nan")
            if change == "flow": data["flows"][0]["steps"][0]["nodes"] = ["absent"]
            with self.subTest(change=change), self.assertRaises(m.ValidationError):
                m.validate_topology(data)

    def test_output_file_symlink_rejected(self):
        self.ws.analysis.mkdir(parents=True)
        (self.ws.analysis / "TOPOLOGY.html").symlink_to(self.source / "source.txt")
        with self.assertRaises(m.ValidationError):
            m.render_topology(self.ws)
        self.assertEqual((self.source / "source.txt").read_text(), "original\n")

    def plan(self):
        return {"units": [{"name":"Core", "path":"src/Core", "deps":["Pilot"]},
                          {"name":"Api", "path":"src/Api", "deps":["Core"]}],
                "completed":["Pilot"], "results":[], "lastBatch":[]}

    def result(self, name, built=True):
        return {"unit":name, "built":built, "buildRan":True, "buildCommand":"actual build"}

    def test_batch_respects_dependencies_and_completion(self):
        plan = self.plan()
        first = m.plan_batch(self.ws, plan)
        self.assertEqual([u["name"] for u in first["nextBatch"]], ["Core"])
        plan["results"] = [self.result("Core")]
        plan["lastBatch"] = ["Core"]
        self.assertEqual([u["name"] for u in m.plan_batch(self.ws, plan)["nextBatch"]], ["Api"])
        plan["results"].append(self.result("Api"))
        self.assertTrue(m.plan_batch(self.ws, plan)["complete"])

    def test_failed_dependencies_block_consumers_and_trip_circuit(self):
        plan = self.plan()
        plan["results"] = [self.result("Core", False)]
        plan["lastBatch"] = ["Core"]
        result = m.plan_batch(self.ws, plan)
        self.assertTrue(result["circuitOpen"])
        self.assertEqual(result["nextBatch"], [])
        self.assertEqual([u["name"] for u in result["blockedUnits"]], ["Api"])
        self.assertFalse(result["complete"])

    def test_two_thirds_boundary_is_allowed(self):
        plan = {"units":[{"name":n,"path":n,"deps":[]} for n in "ABCD"],
                "results":[self.result("A"),self.result("B"),self.result("C",False)],
                "lastBatch":["A","B","C"]}
        result = m.plan_batch(self.ws, plan)
        self.assertFalse(result["circuitOpen"])
        self.assertEqual([u["name"] for u in result["nextBatch"]], ["D"])

    def test_retry_after_verified_playbook_fix_preserves_failure_evidence(self):
        plan = {"units":[{"name":n,"path":n,"deps":[]} for n in "ABCD"],
                "results":[self.result("A"),self.result("B",False),self.result("C",False)],
                "lastBatch":["A","B","C"], "retryUnits":["B","C"]}
        self.assertEqual(m.plan_batch(self.ws, plan)["nextBatch"], [])
        plan["results"][1] = self.result("B")
        plan["lastBatch"] = ["B"]
        plan["retryUnits"] = ["C"]
        result = m.plan_batch(self.ws, plan)
        self.assertEqual([u["name"] for u in result["nextBatch"]], ["C","D"])
        self.assertEqual([u["name"] for u in result["failedUnits"]], ["C"])

    def test_unknown_dependency_and_cycles_rejected(self):
        for kind in ("unknown", "cycle"):
            plan = self.plan()
            plan["units"][0]["deps"] = ["Typo" if kind == "unknown" else "Api"]
            with self.subTest(kind=kind), self.assertRaises(m.ValidationError):
                m.plan_batch(self.ws, plan)

    def test_overlapping_and_aliased_unit_paths_rejected(self):
        for path in ("src/Core", "src/core/child", "src/./Core/child", "src/Core.", "../outside", ".", "C:\\root", "CON", "src/$(id)"):
            plan = self.plan()
            plan["units"][1]["path"] = path
            with self.subTest(path=path), self.assertRaises(m.ValidationError):
                m.plan_batch(self.ws, plan)

    def test_unit_directory_symlink_rejected(self):
        (self.ws.uplift / "src").mkdir(parents=True)
        (self.ws.uplift / "src/Core").symlink_to(self.source, target_is_directory=True)
        with self.assertRaises(m.ValidationError):
            m.plan_batch(self.ws, self.plan())

    def test_cannot_claim_build_without_execution_or_dependency(self):
        for result in ({"unit":"Core","built":True,"buildRan":False}, self.result("Api")):
            plan = self.plan(); plan["results"] = [result]
            with self.assertRaises(m.ValidationError):
                m.plan_batch(self.ws, plan)

    def test_duplicate_results_rejected(self):
        plan = self.plan(); plan["results"] = [self.result("Core"),self.result("Core", False)]
        with self.assertRaises(m.ValidationError):
            m.plan_batch(self.ws, plan)

    def test_status_read_only_and_missing_source_supported(self):
        before = sorted(str(p.relative_to(self.root)) for p in self.root.rglob("*"))
        result = m.status(m.Workspace(self.root, "unknown"))
        self.assertEqual(result["nextSkill"], "$codex-modernize:modernize-preflight unknown")
        after = sorted(str(p.relative_to(self.root)) for p in self.root.rglob("*"))
        self.assertEqual(before, after)

    def test_status_detects_stale_viewer(self):
        self.ws.analysis.mkdir(parents=True)
        for name in ("topology.json", "TOPOLOGY.html"):
            (self.ws.analysis / name).write_text("fixture")
        os.utime(self.ws.analysis / "TOPOLOGY.html", (1,1))
        result = m.status(self.ws)
        self.assertIn({"artifact":"TOPOLOGY.html", "newerInput":"topology.json"}, result["stale"])
        self.assertEqual(result["nextSkill"], "$codex-modernize:modernize-map billing")

    def git(self, *args):
        return subprocess.run(["git", "-C", str(self.root), *args], capture_output=True, text=True, check=True)

    def init_git(self):
        self.git("init", "-q")
        self.git("config", "user.email", "test@example.invalid")
        self.git("config", "user.name", "Test")

    def test_quarantine_ignore_is_idempotent_and_status_does_not_expose_values(self):
        self.init_git()
        first = m.quarantine(self.ws)
        ignore = self.root / "analysis/.gitignore"
        initial = ignore.read_text()
        m.quarantine(self.ws)
        self.assertEqual(ignore.read_text(), initial)
        Path(first["inventory"]).write_text("fake-private-test-value")
        report = m.status(self.ws)
        self.assertNotIn("fake-private-test-value", json.dumps(report))
        self.assertTrue(report["secrets"][0]["ignored"])

    def test_quarantine_refuses_tracked_or_historical_files(self):
        self.init_git()
        self.ws.analysis.mkdir(parents=True)
        secret = self.ws.analysis / "SECRETS.local.md"
        secret.write_text("fake value")
        self.git("add", ".")
        self.git("commit", "-qm", "fixture")
        with self.assertRaises(m.ValidationError):
            m.quarantine(self.ws)
        self.git("rm", str(secret))
        self.git("commit", "-qm", "removed")
        with self.assertRaises(m.ValidationError):
            m.quarantine(self.ws)

    def test_non_git_quarantine_separates_workspaces(self):
        user = self.root / "user"; user.mkdir()
        other = self.root / "other"; other.mkdir()
        with patch.object(m.Path, "home", return_value=user):
            one = m.quarantine(self.ws)
            two = m.quarantine(m.Workspace(other, "billing"))
        self.assertNotEqual(one["inventory"], two["inventory"])
        self.assertFalse(one["rawAllowed"])
        self.assertFalse(self.ws.analysis.exists())

    def test_cli_handles_space_paths_and_errors(self):
        script = ROOT / "plugins/codex-modernize/scripts/modernize.py"
        run = subprocess.run([os.sys.executable, str(script), "paths", "--workspace", str(self.root),
                              "--system", "billing"], capture_output=True, text=True)
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertEqual(json.loads(run.stdout)["workspace"], str(self.root))
        bad = subprocess.run([os.sys.executable, str(script), "paths", "--workspace", str(self.root),
                              "--system", "../escape"], capture_output=True, text=True)
        self.assertEqual(bad.returncode, 2)
        self.assertTrue(bad.stderr.startswith("ERROR:"))


if __name__ == "__main__":
    unittest.main()
