import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("installer", ROOT / "scripts/install.py")
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)


class InstallTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="story-install-test-")
        self.root = Path(self.temp.name)
        self.source = self.root / "source"
        (self.source / "scripts").mkdir(parents=True)
        (self.source / "SKILL.md").write_text("---\nname: story-codex\ndescription: 写小说\n---\n", encoding="utf-8")
        (self.source / "scripts/story.py").write_text("print('v1')\n", encoding="utf-8")
        self.project = self.root / "项目"
        self.project.mkdir()

    def tearDown(self):
        self.temp.cleanup()

    def install(self, update=False):
        return installer.install(self.project, update, self.source)

    def test_only_adds_skill_and_repeat_is_noop(self):
        (self.project / "AGENTS.md").write_text("用户配置", encoding="utf-8")
        (self.project / ".active-book").write_text("另一本书", encoding="utf-8")
        result = self.install()
        self.assertEqual(result["status"], "installed")
        self.assertEqual(self.install()["status"], "unchanged")
        self.assertEqual((self.project / "AGENTS.md").read_text(encoding="utf-8"), "用户配置")
        self.assertEqual((self.project / ".active-book").read_text(encoding="utf-8"), "另一本书")

    def test_update_preserves_backup(self):
        self.install()
        (self.source / "scripts/story.py").write_text("print('v2')\n", encoding="utf-8")
        with self.assertRaises(ValueError):
            self.install()
        result = self.install(True)
        self.assertEqual(result["status"], "updated")
        self.assertIn("v1", (Path(result["backup"]) / "scripts/story.py").read_text())
        self.assertIn("v2", (Path(result["path"]) / "scripts/story.py").read_text())

    def test_local_modifications_are_preserved(self):
        result = self.install()
        file = Path(result["path"]) / "SKILL.md"
        file.write_text("我的改动", encoding="utf-8")
        with self.assertRaises(ValueError):
            self.install(True)
        self.assertEqual(file.read_text(encoding="utf-8"), "我的改动")

    def test_unmanaged_existing_skill_not_overwritten(self):
        target = self.project / ".agents/skills/story-codex"
        target.mkdir(parents=True)
        (target / "SKILL.md").write_text("旧技能", encoding="utf-8")
        with self.assertRaises(ValueError):
            self.install(True)

    def test_failed_swap_restores_previous_installation(self):
        first = self.install()
        (self.source / "scripts/story.py").write_text("print('v2')\n", encoding="utf-8")
        original_replace = installer.move_directory
        def replace(source, destination):
            if Path(source).name.startswith(".story-codex-stage-"):
                raise OSError("simulated swap failure")
            return original_replace(source, destination)
        with patch.object(installer, "move_directory", side_effect=replace):
            with self.assertRaises(OSError):
                self.install(True)
        self.assertIn("v1", (Path(first["path"]) / "scripts/story.py").read_text())

    def test_malicious_manifest_path_is_rejected(self):
        first = self.install()
        marker = Path(first["path"]) / installer.MARKER
        marker.write_text(json.dumps({"schema": 1, "files": {"../../outside": "hash"}}), encoding="utf-8")
        with self.assertRaises(ValueError):
            self.install(True)


if __name__ == "__main__":
    unittest.main()
