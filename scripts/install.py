#!/usr/bin/env python3
"""Install the standalone skill into one Codex project's .agents/skills directory."""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import sys
import tempfile
import uuid

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / ".agents/skills/story-codex"
MARKER = ".story-codex-install.json"


def linked(path):
    try:
        attributes = path.lstat()
    except FileNotFoundError:
        return False
    return stat.S_ISLNK(attributes.st_mode) or bool(
        getattr(attributes, "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400))


def checked(root, relative):
    rel = Path(relative)
    if rel.is_absolute() or ".." in rel.parts:
        raise ValueError("Path is outside the requested project")
    current = root
    for part in rel.parts:
        current /= part
        if linked(current):
            raise ValueError(f"Refusing linked installation path: {current}")
    current.resolve().relative_to(root)
    return current


def inventory(directory):
    files = {}
    for path in sorted(directory.rglob("*")):
        if linked(path):
            raise ValueError(f"Refusing linked package content: {path}")
        rel = path.relative_to(directory)
        if "__pycache__" in rel.parts or path.suffix == ".pyc" or rel.as_posix() == MARKER:
            continue
        if path.is_file():
            files[rel.as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return files


@contextmanager
def installation_lock(project):
    """The OS releases this lock on process exit; the empty lock file may remain."""
    lock = checked(project, ".agents/skills/.story-codex-install.lock")
    lock.parent.mkdir(parents=True, exist_ok=True)
    flags = os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(lock, flags, 0o600)
    try:
        try:
            if os.name == "nt":
                import msvcrt
                os.lseek(fd, 0, os.SEEK_SET)
                msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as error:
            raise ValueError(f"Another installation may be running for this project; retry after it exits: {lock}") from error
        yield
    finally:
        os.close(fd)


def managed_snapshot(directory):
    if linked(directory):
        raise ValueError(f"Refusing linked installation path: {directory}")
    if not directory.exists():
        return None
    marker = checked(directory, MARKER)
    if not marker.is_file():
        raise ValueError("Existing skill has no managed manifest; it will not be replaced")
    raw = marker.read_bytes()
    managed = json.loads(raw.decode("utf-8"))
    if not isinstance(managed, dict) or managed.get("schema") != 1 or not isinstance(managed.get("files"), dict):
        raise ValueError("Invalid installation manifest")
    for relative in managed["files"]:
        checked(directory, relative)
    if inventory(directory) != managed["files"]:
        raise ValueError("Installed skill has local edits or extra files; preserve and reconcile them first")
    return {"files": managed["files"], "manifest_sha256": hashlib.sha256(raw).hexdigest()}


def move_directory(source, destination):
    # Windows rename refuses an existing destination, including an empty directory.
    # On POSIX the preflight guard is not a strong CAS against external writers;
    # the OS lock coordinates other instances of this installer on both platforms.
    if os.path.lexists(destination):
        raise FileExistsError(f"Refusing to replace an existing installation path: {destination}")
    os.rename(source, destination)


def validate_stage(source, stage, files, manifest):
    if inventory(source) != files:
        raise ValueError("Source package changed during installation; retry with a stable source")
    if inventory(stage) != files or (stage / MARKER).read_bytes() != manifest:
        raise ValueError("Staged package differs from its manifest; installation was not published")


def install_locked(project, target, source, files, update):
    original = managed_snapshot(target)
    if original is not None:
        if files == original["files"]:
            return {"status": "unchanged", "path": str(target)}
        if not update:
            raise ValueError("A managed version exists; use --update for a reviewed replacement")
    stage = Path(tempfile.mkdtemp(prefix=".story-codex-stage-", dir=target.parent))
    backup = None
    moved_original = False
    try:
        for relative in files:
            destination = checked(stage.resolve(), relative)
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source / relative, destination)
            if hashlib.sha256(destination.read_bytes()).hexdigest() != files[relative]:
                raise ValueError(f"Source file changed while copying; installation was not published: {relative}")
        manifest = (json.dumps({"schema": 1, "files": files}, ensure_ascii=False,
                               sort_keys=True, indent=2) + "\n").encode("utf-8")
        (stage / MARKER).write_bytes(manifest)
        validate_stage(source, stage, files, manifest)
        if managed_snapshot(checked(project, ".agents/skills/story-codex")) != original:
            raise ValueError("Installed skill changed during staging; it will not be replaced")
        if original is not None:
            backup = checked(project, f".agents/.story-codex-backups/{uuid.uuid4().hex}")
            backup.parent.mkdir(parents=True, exist_ok=True)
            move_directory(target, backup)
            moved_original = True
        try:
            if moved_original and managed_snapshot(backup) != original:
                raise ValueError("Installed skill changed while being moved; restoring the moved version")
            validate_stage(source, stage, files, manifest)
            move_directory(stage, checked(project, ".agents/skills/story-codex"))
            expected = {"files": files, "manifest_sha256": hashlib.sha256(manifest).hexdigest()}
            if managed_snapshot(checked(project, ".agents/skills/story-codex")) != expected:
                raise ValueError("Published installation differs from the verified package and manifest")
        except BaseException as error:
            if moved_original:
                try:
                    move_directory(backup, checked(project, ".agents/skills/story-codex"))
                except (OSError, ValueError) as recovery_error:
                    raise ValueError(
                        f"Installation failed ({error}); the moved skill is preserved at {backup}. "
                        f"Recovery did not replace the current target: {recovery_error}") from error
            raise
    finally:
        if stage.exists():
            # This exact temporary child was allocated above, never a caller-supplied deletion target.
            if stage.resolve().parent != target.parent.resolve() or not stage.name.startswith(".story-codex-stage-"):
                raise ValueError("Refusing to clean a stage outside the installation directory")
            shutil.rmtree(stage)
    return {"status": "updated" if backup else "installed", "path": str(target),
            "backup": str(backup) if backup else None, "files": len(files)}


def install(project, update=False, source=SOURCE):
    project, source = Path(project).expanduser().resolve(), Path(source).resolve()
    target = checked(project, ".agents/skills/story-codex")
    if target == source:
        return {"status": "already_in_place", "path": str(target)}
    files = inventory(source)
    if "SKILL.md" not in files or "scripts/story.py" not in files:
        raise ValueError("Source package is incomplete")
    with installation_lock(project):
        return install_locked(project, checked(project, ".agents/skills/story-codex"), source, files, update)


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--project", required=True, help="Target Codex project; no global configuration is changed")
    p.add_argument("--update", action="store_true", help="Replace an unchanged managed installation; retain backup")
    args = p.parse_args()
    try:
        print(json.dumps(install(args.project, args.update), ensure_ascii=False))
        return 0
    except (OSError, ValueError) as error:
        print(json.dumps({"ok": False, "error": str(error)}, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
