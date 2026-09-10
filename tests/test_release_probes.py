import importlib.util
from pathlib import Path
import stat
import tempfile
import unittest
import warnings
from unittest.mock import patch
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def load(name):
    spec = importlib.util.spec_from_file_location("test_release_" + name, ROOT / "scripts" / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


migration, upgrade = load("migrate_probe"), load("upgrade_probe")


class ReleaseProbeTests(unittest.TestCase):
    def test_generated_schema1_books_cover_native_baseline_and_analysis_rollback(self):
        report = migration.probe()
        self.assertTrue(report["ok"], report.get("error"))
        self.assertEqual(report["mode"], "generated-schema1-fixtures")
        self.assertIn("not retained historical", report["scope"])
        self.assertEqual({book["kind"] for book in report["books"]}, {"long", "short", "analysis"})
        self.assertTrue(report["original_tree_unchanged"])
        self.assertTrue(report["runtime_stable"])
        self.assertTrue(all(book["source_and_analysis_preserved"] and
                            book["old_runtime_rollback_copy_verified"] for book in report["books"]))

    def test_missing_retained_database_is_not_reported_as_synthetic_or_success(self):
        with tempfile.TemporaryDirectory(prefix="story-probe-source-") as directory:
            source = Path(directory).resolve()
            (source / migration.RETAINED_NAMES[0]).mkdir()
            report = migration.probe(source)
        self.assertFalse(report["ok"])
        self.assertEqual(report["mode"], "retained-source")
        self.assertEqual(report["books"], [])
        self.assertIn("Source database unavailable", report["error"]["message"])

    def test_changed_legacy_runtime_archive_is_rejected_before_execution(self):
        with tempfile.TemporaryDirectory(prefix="story-probe-runtime-") as directory:
            archive = Path(directory) / "changed.zip"
            archive.write_bytes(b"untrusted replacement")
            with patch.object(migration, "LEGACY_ARCHIVE", archive):
                with self.assertRaisesRegex(ValueError, "SHA-256"):
                    migration.legacy_runtime(Path(directory) / "old.py")
            self.assertFalse((Path(directory) / "old.py").exists())

    def test_seven_skill_archive_keeps_all_sibling_roots(self):
        names = upgrade.load_script("install").SKILL_NAMES
        with tempfile.TemporaryDirectory(prefix="story-upgrade-suite-") as directory:
            root = Path(directory).resolve()
            archive = root / "suite.zip"
            with zipfile.ZipFile(archive, "w") as bundle:
                for name in names:
                    bundle.writestr(name + "/SKILL.md", "# " + name)
                bundle.writestr("story-codex/scripts/story.py", 'VERSION = "0.4.0"\n')
            source, files = upgrade.unpack_old_archive(archive, root / "unpacked")
            self.assertEqual(source, root / "unpacked")
            self.assertEqual({name.split("/")[0] for name in files}, set(names))
            self.assertTrue((source / "story-codex-write/SKILL.md").is_file())

    def test_invalid_archive_paths_are_rejected_before_extraction(self):
        invalid_members = [
            ["story-codex/../../escaped"], ["story-codex\\escaped"], ["other-skill/SKILL.md"],
            ["story-codex/CON.txt"], ["story-codex/a./file"], ["story-codex/a:stream"], ["story-codex/a?/file"], ["story-codex/empty//"],
            ["story-codex/A/x", "story-codex/a/y"],
            ["story-codex/caf\u00e9/x", "story-codex/cafe\u0301/y"],
            ["story-codex/parent", "story-codex/parent/file"],
            ["story-codex/SKILL.md"],
        ]
        for members in invalid_members:
            with self.subTest(members=members), tempfile.TemporaryDirectory(prefix="story-upgrade-bad-") as directory:
                root = Path(directory).resolve()
                archive = root / "bad.zip"
                with zipfile.ZipFile(archive, "w") as bundle:
                    bundle.writestr("story-codex/SKILL.md", "# Core")
                    bundle.writestr("story-codex/scripts/story.py", 'VERSION = "0.3.0"\n')
                    with warnings.catch_warnings():
                        warnings.filterwarnings("ignore", message="Duplicate name:", category=UserWarning)
                        for name in members:
                            # Preserve the raw member spelling on Windows too;
                            # ZipInfo(name) otherwise rewrites backslashes.
                            member = zipfile.ZipInfo()
                            member.filename = member.orig_filename = name
                            bundle.writestr(member, "bad")
                with self.assertRaises(ValueError):
                    upgrade.unpack_old_archive(archive, root / "unpacked")
                self.assertFalse((root / "unpacked").exists())
                self.assertFalse((root / "escaped").exists())

    def test_reader_normalized_archive_path_is_rejected_before_extraction(self):
        with tempfile.TemporaryDirectory(prefix="story-upgrade-normalized-") as directory:
            root = Path(directory).resolve()
            archive = root / "normalized.zip"
            with zipfile.ZipFile(archive, "w") as bundle:
                bundle.writestr("story-codex/SKILL.md", "# Core")
                bundle.writestr("story-codex/scripts/story.py", 'VERSION = "0.3.0"\n')
                member = zipfile.ZipInfo()
                member.filename = member.orig_filename = "story-codex\\extra.txt"
                bundle.writestr(member, "extra")
            # Reproduce Windows ZipInfo normalization on every test platform.
            with patch.object(zipfile.os, "sep", "\\"):
                with zipfile.ZipFile(archive) as bundle:
                    member = bundle.infolist()[-1]
                    self.assertNotEqual(member.orig_filename, member.filename)
                with self.assertRaisesRegex(ValueError, "Non-portable archive path"):
                    upgrade.unpack_old_archive(archive, root / "unpacked")
            self.assertFalse((root / "unpacked").exists())

    def test_archive_link_or_partial_suite_is_rejected(self):
        for special in (True, False):
            with self.subTest(special=special), tempfile.TemporaryDirectory(prefix="story-upgrade-kind-") as directory:
                root = Path(directory).resolve()
                archive = root / "bad.zip"
                with zipfile.ZipFile(archive, "w") as bundle:
                    bundle.writestr("story-codex/SKILL.md", "# Core")
                    bundle.writestr("story-codex/scripts/story.py", 'VERSION = "0.3.0"\n')
                    if special:
                        member = zipfile.ZipInfo("story-codex/link")
                        member.create_system = 3
                        member.external_attr = (stat.S_IFLNK | 0o777) << 16
                        bundle.writestr(member, "../../outside")
                    else:
                        bundle.writestr("story-codex-plan/SKILL.md", "# Plan")
                with self.assertRaises(ValueError):
                    upgrade.unpack_old_archive(archive, root / "unpacked")
                self.assertFalse((root / "unpacked").exists())

    def test_legacy_single_skill_upgrade_still_preserves_backup(self):
        report = upgrade.probe(ROOT / "tests/fixtures/story-codex-0.2.0.zip", 60)
        self.assertTrue(report["ok"], report.get("error"))
        self.assertEqual(report["initial_archive"]["version"], "0.2.0")
        self.assertEqual(report["checks"]["archive_extraction_exact"]["skill_count"], 1)
        self.assertEqual(report["checks"]["previous_release_backup_exact"]["status"], "passed")
        self.assertEqual(report["checks"]["all_seven_skills_match_canonical"]["skill_count"], 7)


if __name__ == "__main__":
    unittest.main()
