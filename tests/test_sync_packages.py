import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from contextlib import ExitStack
from types import SimpleNamespace
from unittest.mock import patch
import urllib.error

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
try:
    spec = importlib.util.spec_from_file_location("package_sync_test", SCRIPTS / "sync_packages.py")
    sync = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(sync)
finally:
    sys.path.remove(str(SCRIPTS))


class PackageSyncTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="story-sync-test-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.dict(os.environ, {
            "NODE_AUTH_TOKEN": "fake-test-token", "GITHUB_REPOSITORY": sync.REPOSITORY}))

    def pipeline(self):
        built = {"name": sync.NAME, "version": "0.3.0", "tarball": str(self.root / "built.tgz")}
        self.stack.enter_context(patch.object(sync, "release_files", return_value=(
            {"html_url": "https://github.com/Cuinings/story-skill/releases/tag/v0.3.0"},
            self.root / "release.zip", self.root / "release.sha256")))
        self.stack.enter_context(patch.object(sync.package_npm, "build", return_value=built))
        self.registry = self.stack.enter_context(patch.object(sync, "registry_version"))
        self.npm = self.stack.enter_context(patch.object(sync, "npm_command", return_value=SimpleNamespace(
            returncode=0, stdout=json.dumps("github-actions[bot]"), stderr="")))
        self.verify = self.stack.enter_context(patch.object(sync, "verify_download", return_value=(
            self.root / "verified.tgz", {"ok": True}, "sha512-verified")))
        self.stack.enter_context(patch.object(sync, "runtime_smoke", return_value={"ok": True}))
        self.stack.enter_context(patch.object(sync, "read_json", return_value={
            "html_url": "https://github.com/users/Cuinings/packages/npm/package/story-codex",
            "visibility": "public", "repository": {"full_name": sync.REPOSITORY}}))
        self.stack.enter_context(patch.object(sync.time, "sleep"))

    def test_redirect_removes_registry_credential_from_signed_asset_host(self):
        requests = []

        def opened(request, **kwargs):
            requests.append(request)
            if len(requests) == 1:
                raise urllib.error.HTTPError(request.full_url, 302, "redirect", {
                    "Location": "https://release-assets.githubusercontent.com/package.tgz?signature=test"}, None)
            return io.BytesIO(b"verified bytes")

        opener = SimpleNamespace(open=opened)
        with patch.object(sync.urllib.request, "build_opener", return_value=opener):
            raw = sync.read_url("https://npm.pkg.github.com/download/test", "fake", "npm.pkg.github.com")
        self.assertEqual(raw, b"verified bytes")
        self.assertEqual(requests[0].get_header("Authorization"), "Bearer fake")
        self.assertIsNone(requests[1].get_header("Authorization"))

    def test_invalid_tag_stops_before_network_or_build(self):
        with patch.object(sync, "release_files") as fetch:
            with self.assertRaises(ValueError):
                sync.sync("v0.3.0; echo bad", self.root)
        fetch.assert_not_called()

    def test_prepare_only_never_reads_or_writes_registry(self):
        self.pipeline()
        with patch.dict(os.environ, {"NODE_AUTH_TOKEN": ""}):
            result = sync.sync("v0.3.0", self.root, prepare_only=True)
        self.assertTrue(result["ok"])
        self.npm.assert_not_called()
        self.registry.assert_not_called()

    def test_failed_authentication_never_treats_package_as_absent(self):
        self.pipeline()
        self.npm.return_value = SimpleNamespace(returncode=1, stdout="", stderr="401")
        with self.assertRaisesRegex(ValueError, "authentication"):
            sync.sync("v0.3.0", self.root)
        self.registry.assert_not_called()
        self.assertEqual(len(self.npm.call_args_list), 1)

    def test_existing_matching_version_is_verified_without_republishing(self):
        self.pipeline()
        self.registry.return_value = {"name": sync.NAME, "version": "0.3.0"}
        result = sync.sync("v0.3.0", self.root)
        self.assertTrue(result["already_published"])
        self.assertTrue(result["ok"])
        self.verify.assert_called_once()
        self.assertEqual([c.args[0][0] for c in self.npm.call_args_list], ["whoami"])

    def test_existing_different_payload_is_never_overwritten(self):
        self.pipeline()
        self.registry.return_value = {"name": sync.NAME, "version": "0.3.0"}
        self.verify.side_effect = ValueError("payload mismatch")
        with self.assertRaisesRegex(ValueError, "payload mismatch"):
            sync.sync("v0.3.0", self.root)
        self.assertEqual([c.args[0][0] for c in self.npm.call_args_list], ["whoami"])

    def test_uncertain_publish_reads_back_without_a_second_publish(self):
        self.pipeline()
        self.registry.side_effect = [None, {"name": sync.NAME, "version": "0.3.0"}]
        self.npm.side_effect = [SimpleNamespace(returncode=0, stdout='"github-actions[bot]"', stderr=""),
                               SimpleNamespace(returncode=1, stdout="", stderr="response lost")]
        result = sync.sync("v0.3.0", self.root)
        self.assertTrue(result["ok"])
        self.assertFalse(result["already_published"])
        self.assertEqual([c.args[0][0] for c in self.npm.call_args_list], ["whoami", "publish"])

    def test_publish_timeout_also_reads_back_without_a_second_publish(self):
        self.pipeline()
        self.registry.side_effect = [None, {"name": sync.NAME, "version": "0.3.0"}]
        self.npm.side_effect = [SimpleNamespace(returncode=0, stdout='"github-actions[bot]"', stderr=""),
                               subprocess.TimeoutExpired(["npm", "publish"], 180)]
        self.assertTrue(sync.sync("v0.3.0", self.root)["ok"])
        self.assertEqual([c.args[0][0] for c in self.npm.call_args_list], ["whoami", "publish"])


if __name__ == "__main__":
    unittest.main()
