#!/usr/bin/env python3
"""Create a self-contained, reproducible skill archive (no novel data or virtualenv)."""
import argparse
import ast
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / ".agents/skills/story-codex"


def source_version(raw):
    """Read the packaged runtime's literal VERSION without executing its code."""
    tree = ast.parse(raw.decode("utf-8-sig"))
    values = []
    for node in tree.body:
        targets = node.targets if isinstance(node, ast.Assign) else (
            [node.target] if isinstance(node, ast.AnnAssign) else [])
        if any(isinstance(target, ast.Name) and target.id == "VERSION" for target in targets):
            values.append(ast.literal_eval(node.value))
    if len(values) != 1 or not isinstance(values[0], str) or not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", values[0]):
        raise ValueError("Runtime must define one literal VERSION in major.minor.patch form")
    return values[0]


def current_version(runtime=None):
    return source_version(Path(runtime or SOURCE / "scripts/story.py").read_bytes())


def validate_archive_name(output, version):
    match = re.fullmatch(r"story-codex-([0-9]+\.[0-9]+\.[0-9]+)\.zip", Path(output).name)
    if match and match.group(1) != version:
        raise ValueError(f"Archive filename version {match.group(1)} differs from runtime VERSION {version}")


def validate_archive(path, entries):
    with zipfile.ZipFile(path) as archive:
        if archive.namelist() != [name for name, _ in entries]:
            raise RuntimeError("Archive file list differs from the source snapshot")
        if archive.testzip() is not None:
            raise RuntimeError("Archive verification failed")
        for name, raw in entries:
            if archive.read(name) != raw:
                raise RuntimeError(f"Archive content differs from the source snapshot: {name}")


def package(output=None):
    entries = []
    for path in sorted(SOURCE.rglob("*")):
        rel = path.relative_to(SOURCE)
        if path.is_symlink() or getattr(path, "is_junction", lambda: False)():
            raise ValueError(f"Refusing linked package content: {rel}")
        if path.is_file() and "__pycache__" not in rel.parts and path.suffix != ".pyc":
            entries.append((f"story-codex/{rel.as_posix()}", path.read_bytes()))
    if not any(name == "story-codex/LICENSE" for name, _ in entries):
        entries.append(("story-codex/LICENSE", (ROOT / "LICENSE").read_bytes()))
    runtime = dict(entries).get("story-codex/scripts/story.py")
    if runtime is None:
        raise ValueError("Source package is missing scripts/story.py")
    version = source_version(runtime)
    output = (Path(output).expanduser() if output is not None else ROOT / f"dist/story-codex-{version}.zip").absolute()
    validate_archive_name(output, version)
    output.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=".story-codex-package-", suffix=".zip", dir=output.parent)
    stage = Path(name)
    try:
        os.close(fd)
        with zipfile.ZipFile(stage, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
            for entry_name, raw in entries:
                info = zipfile.ZipInfo(entry_name, date_time=(2026, 9, 8, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = 0o644 << 16
                archive.writestr(info, raw)
        validate_archive(stage, entries)
        archive_bytes = stage.read_bytes()
        result = {"archive": str(output), "version": version, "files": len(entries),
                  "sha256": hashlib.sha256(archive_bytes).hexdigest(), "bytes": len(archive_bytes)}
        os.replace(stage, output)
        return result
    finally:
        if stage.exists():
            stage.unlink()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output", help="Archive path; defaults to dist/story-codex-<runtime VERSION>.zip")
    args = p.parse_args()
    print(json.dumps(package(args.output), ensure_ascii=False))


if __name__ == "__main__":
    main()
