import copy
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
import zipfile
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("release_verify", ROOT / "scripts/verify.py")
verify = importlib.util.module_from_spec(spec)
spec.loader.exec_module(verify)


class VerificationEvidenceTests(unittest.TestCase):
    def test_links_are_checked_in_specialized_skills(self):
        with tempfile.TemporaryDirectory(prefix="story-suite-links-") as directory:
            root = Path(directory)
            skills = root / "skills"
            core = skills / "story-codex"
            review = skills / "story-codex-review"
            core.mkdir(parents=True)
            review.mkdir()
            (core / "SKILL.md").write_text("# Core\n", encoding="utf-8")
            (review / "SKILL.md").write_text(
                "[shared](../story-codex/SKILL.md)\n[history](references/history.md)\n", encoding="utf-8")
            with patch.object(verify, "ROOT", root), patch.object(verify, "SKILLS", skills):
                result = verify.check_markdown_links()
            self.assertEqual(result["status"], "failed")
            self.assertEqual(result["links_checked"], 2)
            self.assertEqual(result["missing"], [{"source": "skills/story-codex-review/SKILL.md",
                                                 "target": "references/history.md", "exists": False}])

    def test_archive_validation_covers_specialized_skill_bytes(self):
        with tempfile.TemporaryDirectory(prefix="story-suite-archive-") as directory:
            archive = Path(directory) / "story-codex-0.4.0.zip"
            files = {"story-codex/SKILL.md": b"core", "story-codex-write/SKILL.md": b"writing"}
            expected = {key: hashlib.sha256(raw).hexdigest() for key, raw in files.items()}
            with zipfile.ZipFile(archive, "w") as bundle:
                for name, raw in files.items():
                    bundle.writestr(name, raw if name.startswith("story-codex/") else b"changed")
            with patch.object(verify, "skill_files", return_value=expected), patch.object(verify, "package_module") as loader:
                loader.return_value.current_version.return_value = "0.4.0"
                result = verify.check_archive(archive)
            self.assertEqual(result["status"], "failed")
            self.assertEqual(result["changed"], ["story-codex-write/SKILL.md"])

    def test_counts_come_from_real_callbacks_including_failed_subtests(self):
        class Example(unittest.TestCase):
            def test_pass(self):
                pass

            def test_fail(self):
                for i in range(3):
                    with self.subTest(i=i):
                        self.fail("intentional fixture failure")

            @unittest.skip("intentional fixture skip")
            def test_skip(self):
                pass

        runner = unittest.TextTestRunner(stream=io.StringIO(), resultclass=verify.CountedTestResult)
        actual = runner.run(unittest.defaultTestLoader.loadTestsFromTestCase(Example))
        result = verify.summarize_unittest(actual)
        self.assertEqual((result["run"], result["passed"], result["failed"], result["skipped"]), (3, 1, 3, 1))
        self.assertEqual(result["status"], "failed")

    def test_empty_suite_cannot_be_reported_as_passed(self):
        runner = unittest.TextTestRunner(stream=io.StringIO(), resultclass=verify.CountedTestResult)
        result = verify.summarize_unittest(runner.run(unittest.TestSuite()))
        self.assertEqual(result["run"], 0)
        self.assertEqual(result["status"], "failed")

    def test_all_skipped_tests_cannot_be_reported_as_passed(self):
        class Example(unittest.TestCase):
            @unittest.skip("no usable test environment")
            def test_skip(self):
                pass

        runner = unittest.TextTestRunner(stream=io.StringIO(), resultclass=verify.CountedTestResult)
        result = verify.summarize_unittest(runner.run(unittest.defaultTestLoader.loadTestsFromTestCase(Example)))
        self.assertEqual((result["run"], result["passed"], result["skipped"]), (1, 0, 1))
        self.assertEqual(result["status"], "failed")

    def test_reparse_point_output_is_rejected_before_writing(self):
        with tempfile.TemporaryDirectory(prefix="story-verify-links-test-") as directory:
            root = Path(directory)
            output = root / "verification.json"
            output.write_text("existing external evidence", encoding="utf-8")
            original = Path.lstat

            class ReparseAttributes:
                st_mode = 0o100644
                st_file_attributes = 0x400

            def attributes(path, *args, **kwargs):
                return ReparseAttributes() if path == output else original(path, *args, **kwargs)

            with patch.object(Path, "lstat", attributes):
                with self.assertRaisesRegex(ValueError, "linked report output"):
                    verify.write_report({"ok": True}, output)
            self.assertEqual(output.read_text(encoding="utf-8"), "existing external evidence")

    def test_linked_parent_cannot_redirect_report_outside_requested_directory(self):
        with tempfile.TemporaryDirectory(prefix="story-verify-native-link-test-") as directory:
            root = Path(directory)
            requested, external = root / "requested", root / "external"
            requested.mkdir()
            external.mkdir()
            link = requested / "reports"
            try:
                link.symlink_to(external, target_is_directory=True)
            except OSError as error:
                if os.name != "nt":
                    self.skipTest(f"Directory links unavailable: {error}")
                import _winapi
                _winapi.CreateJunction(str(external), str(link))
            with self.assertRaisesRegex(ValueError, "linked report output"):
                verify.write_report({"ok": True}, link / "verification.json")
            self.assertEqual(list(external.iterdir()), [])

    def test_default_archive_matches_canonical_version_even_if_other_versions_exist(self):
        with tempfile.TemporaryDirectory(prefix="story-verify-version-test-") as directory:
            root = Path(directory)
            (root / "dist").mkdir()
            current = root / "dist/story-codex-2.4.6.zip"
            current.write_bytes(b"current")
            (root / "dist/story-codex-9.9.9.zip").write_bytes(b"different release")
            with patch.object(verify, "ROOT", root), patch.object(verify, "package_module") as loader:
                loader.return_value.current_version.return_value = "2.4.6"
                self.assertEqual(verify.select_archive(), current)

    def test_failure_report_preserves_existing_success_evidence(self):
        with tempfile.TemporaryDirectory(prefix="story-verify-report-test-") as directory:
            path = Path(directory) / "verification.json"
            passed = {"ok": True, "unit_tests": {"run": 57}}
            self.assertEqual(verify.write_report(passed, path), path)
            failure_path = verify.write_report({"ok": False}, path)
            self.assertNotEqual(failure_path, path)
            self.assertEqual(json.loads(path.read_text(encoding="utf-8")), passed)
            self.assertFalse(json.loads(failure_path.read_text(encoding="utf-8"))["ok"])


class BenchmarkContractTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="story-benchmark-contract-test-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "benchmarks/results").mkdir(parents=True)
        candidate = b"hello\n"
        (self.root / "candidate.md").write_bytes(candidate)
        self.config = {"repository": "https://example.invalid/fixture", "revision": "pinned-fixture",
                       "encoding": "fixture-encoding", "profiles": [
                           {"id": "writing", "label": "写作夹具", "scope": "Static instruction files only",
                            "upstream": ["skills/example/SKILL.md", "skills/example/reference.md"],
                            "candidate": ["candidate.md"]}]}
        candidate_entry = {"path": "candidate.md", "bytes": len(candidate), "tokens": 2,
                           "sha256": hashlib.sha256(candidate).hexdigest(),
                           "normalized_text_sha256": hashlib.sha256(candidate).hexdigest()}
        self.report = {"schema": 1, "repository": self.config["repository"],
                       "upstream_revision": self.config["revision"], "encoding": self.config["encoding"],
                       "profiles": [{"id": "writing", "label": "写作夹具", "scope": "Static instruction files only",
                                     "upstream_files": [{"path": self.config["profiles"][0]["upstream"][0], "tokens": 10},
                                                        {"path": self.config["profiles"][0]["upstream"][1], "tokens": 20}],
                                     "candidate_files": [candidate_entry], "upstream_tokens": 30,
                                     "candidate_tokens": 2, "reduction_percent": 93.33}]}

    def check(self, config=None, report=None):
        (self.root / "benchmarks/profiles.json").write_text(
            json.dumps(self.config if config is None else config), encoding="utf-8")
        (self.root / "benchmarks/results/tokens.json").write_text(
            json.dumps(self.report if report is None else report), encoding="utf-8")
        with patch.object(verify, "ROOT", self.root):
            return verify.check_benchmark()

    def test_matching_lists_metadata_hashes_and_arithmetic_pass(self):
        result = self.check()
        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["problems"], [])

    def test_changed_upstream_inputs_cannot_validate_an_old_report(self):
        alternatives = [["skills/example/SKILL.md"],
                        ["skills/example/reference.md", "skills/example/SKILL.md"],
                        [*self.config["profiles"][0]["upstream"], "skills/example/extra.md"]]
        for paths in alternatives:
            with self.subTest(paths=paths):
                config = copy.deepcopy(self.config)
                config["profiles"][0]["upstream"] = paths
                result = self.check(config=config)
                self.assertEqual(result["status"], "failed")
                self.assertTrue(any("Upstream file list differs" in problem for problem in result["problems"]))

    def test_changed_candidate_inputs_are_rejected(self):
        config = copy.deepcopy(self.config)
        config["profiles"][0]["candidate"].append("new-candidate.md")
        result = self.check(config=config)
        self.assertEqual(result["status"], "failed")
        self.assertTrue(any("Candidate file list differs" in problem for problem in result["problems"]))

    def test_changed_configuration_metadata_is_rejected(self):
        for field in ("repository", "revision", "encoding", "id", "label", "scope"):
            with self.subTest(field=field):
                config = copy.deepcopy(self.config)
                target = config if field in ("repository", "revision", "encoding") else config["profiles"][0]
                target[field] = "changed fixture value"
                self.assertEqual(self.check(config=config)["status"], "failed")

    def test_duplicate_input_paths_and_reordered_profiles_are_rejected(self):
        for side in ("upstream", "candidate"):
            with self.subTest(side=side):
                config, report = copy.deepcopy(self.config), copy.deepcopy(self.report)
                config["profiles"][0][side].append(config["profiles"][0][side][0])
                entries = report["profiles"][0][f"{side}_files"]
                entries.append(copy.deepcopy(entries[0]))
                self.assertEqual(self.check(config=config, report=report)["status"], "failed")
        config, report = copy.deepcopy(self.config), copy.deepcopy(self.report)
        config["profiles"].append({**copy.deepcopy(config["profiles"][0]), "id": "second"})
        report["profiles"].append({**copy.deepcopy(report["profiles"][0]), "id": "second"})
        config["profiles"].reverse()
        self.assertEqual(self.check(config=config, report=report)["status"], "failed")

    def test_inconsistent_totals_and_reduction_cannot_be_reported_as_passed(self):
        for field in ("upstream_tokens", "candidate_tokens", "reduction_percent"):
            with self.subTest(field=field):
                report = copy.deepcopy(self.report)
                report["profiles"][0][field] += 1
                self.assertEqual(self.check(report=report)["status"], "failed")


if __name__ == "__main__":
    unittest.main()
