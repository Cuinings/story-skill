#!/usr/bin/env python3
"""Migrate copies of the retained Chinese schema1 books and verify rollback copies."""
from contextlib import closing
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "skills/story-codex/scripts/story.py"
spec = importlib.util.spec_from_file_location("migration_probe_story", TOOL)
story = importlib.util.module_from_spec(spec)
spec.loader.exec_module(story)


def inventory(root):
    result = {}
    for path in root.rglob("*"):
        if path.is_symlink() or getattr(path, "is_junction", lambda: False)():
            raise ValueError("Linked fixture path")
        if path.is_file():
            result[path.relative_to(root).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return result


def main():
    source = ROOT / "examples/实测工程-v0.2.0"
    initial = inventory(source)
    evidence = {"version": story.VERSION, "scope": "Existing reviewed Chinese fixtures copied to isolated TEMP; original books unchanged",
                "runtime": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in TOOL.parent.glob("*.py")}, "books": []}
    with tempfile.TemporaryDirectory(prefix="story-migration-probe-") as directory:
        temp = Path(directory)
        old_runtime = temp / "old.py"
        with zipfile.ZipFile(ROOT / "tests/fixtures/story-codex-0.2.0.zip") as archive:
            old_runtime.write_bytes(archive.read("story-codex/scripts/story.py"))
        for name in ("渡口夜账", "留半寸", "留半寸_拆文"):
            origin = source / name
            target = temp / name
            shutil.copytree(origin, target)
            with closing(sqlite3.connect((origin / ".story/state.sqlite3").as_uri() + "?mode=ro", uri=True)) as db:
                meta = dict(db.execute("SELECT key,value FROM meta"))
                chapters = list(db.execute("SELECT chapter,sha,summary FROM chapters ORDER BY chapter"))
            result = story.storage.migrate(story.CORE, target)
            book = story.Book(target)
            try:
                if any(book.meta(k) != json.loads(v) for k,v in meta.items() if k != "schema"):
                    raise ValueError("Identity/checkpoint changed during migration")
                if [tuple(r) for r in book.db.execute("SELECT chapter,sha,summary FROM chapters ORDER BY chapter")] != chapters:
                    raise ValueError("Published manuscript/summary changed")
                status = book.status()
                if status["pending_export_count"] or status["changed_export_count"]:
                    raise ValueError("Migrated exports differ from original fixture")
                book.export()
                rollback = temp / (name + "-rollback")
                shutil.copytree(origin, rollback)
                shutil.copyfile(result["backup"], rollback / ".story/state.sqlite3")
                command = [sys.executable, "-B", "-X", "utf8", str(old_runtime), "status", "--book", str(rollback)]
                process = subprocess.run(command, capture_output=True, timeout=60)
                if process.returncode:
                    raise ValueError(process.stderr.decode("utf-8"))
                old_status = json.loads(process.stdout)
                if old_status["id"] != status["id"] or old_status["revision"] != status["revision"]:
                    raise ValueError("Rollback copy lost identity/checkpoint")
                evidence["books"].append({"title": name, "book_id": status["id"], "revision": status["revision"],
                    "last_chapter": status["last_chapter"], "sources": status["sources"], "migrated": result["migrated"],
                    "original_manuscript_and_summary_preserved": True, "exports_clean": True, "old_runtime_rollback_copy_verified": True})
            finally:
                book.close()
    evidence["original_tree_unchanged"] = inventory(source) == initial
    evidence["ok"] = evidence["original_tree_unchanged"] and len(evidence["books"]) == 3
    output = ROOT / "benchmarks/results/v0.4.0/migration.json"
    output.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(story.dumps({"ok": evidence["ok"], "books": len(evidence["books"]), "report": str(output)}))
    return 0 if evidence["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
