#!/usr/bin/env python3
"""Story Codex: local, bounded context and transactional writing state. No API calls."""
from __future__ import annotations

import argparse
from collections import Counter
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import sys
import tempfile
import unicodedata
import uuid
import importlib.util
from types import SimpleNamespace

VERSION = "0.4.0"
SCHEMA_VERSION = 2
CHECKS = ("causality", "continuity", "constraints", "style")
KINDS = ("fact", "character", "world", "hook", "preference", "contract")
COUNT_METHODS = ("visible_nonspace_v1", "letters_numbers_v1", "han_v1")


class StoryError(Exception):
    def __init__(self, code, message, **details):
        super().__init__(message)
        self.code, self.message, self.details = code, message, details


def fail(code, message, **details):
    raise StoryError(code, message, **details)


def dumps(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def digest(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def text_field(value, name, maximum=2000):
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        fail("invalid_input", f"{name} must be nonempty text, at most {maximum} characters")
    if "<填写" in value or value.strip() in ("TODO", "待补充", "REPLACE_ME"):
        fail("placeholder", f"Fill {name} before saving")
    return value


def integer(value, name, minimum=0):
    if type(value) is not int or not minimum <= value <= 2**63 - 1:
        fail("invalid_input", f"{name} must be an integer from {minimum} to {2**63 - 1}")
    return value


def string_list(value, name, maximum=50):
    if not isinstance(value, list) or len(value) > maximum:
        fail("invalid_input", f"{name} must be an array, at most {maximum} entries")
    return list(dict.fromkeys(text_field(v, name, 1200) for v in value))


def object_value(value, name):
    if not isinstance(value, dict):
        fail("invalid_input", f"{name} must be an object")
    return value


def read_text(path, encoding="utf-8-sig"):
    return Path(path).read_bytes().decode(encoding)


def read_json(path):
    return json.loads(read_text(path))


def safe_path(root, relative):
    """Only internally chosen relative paths; reject symlinks and Windows junctions."""
    rel = Path(relative)
    if rel.is_absolute() or ".." in rel.parts:
        fail("path_escape", "Expected a relative path inside the book")
    current = root
    for part in rel.parts:
        current = current / part
        if current.is_symlink() or getattr(current, "is_junction", lambda: False)():
            fail("linked_path", "Managed paths cannot contain links or junctions", path=str(current))
    try:
        current.resolve().relative_to(root)
    except ValueError:
        fail("path_escape", "Managed path leaves the book", path=str(current))
    return current


def _publish_no_replace(source, target):
    """Publish a complete same-directory stage without replacing an existing path."""
    if os.name == "nt":
        # Windows rename fails when target exists, including on exFAT where
        # hard links are unavailable. POSIX rename would overwrite the target.
        os.rename(source, target)
    else:
        os.link(source, target)


def _restore_displaced_file(backup, target):
    if os.name != "nt":
        _publish_no_replace(backup, target)
        return
    # Do not rename the backup itself: keep it available even after restoration
    # and when an editor still has the displaced file open.
    fd, staged = tempfile.mkstemp(prefix=".story-restore-", dir=target.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(backup.read_bytes())
            handle.flush()
            os.fsync(handle.fileno())
        _publish_no_replace(staged, target)
    finally:
        if os.path.exists(staged):
            os.unlink(staged)


def atomic_write(path, content, allowed_hashes, backup):
    """Preserve the displaced inode and publish without clobbering a concurrent save.

    Windows uses no-replace rename; POSIX uses a hard link. Failure leaves a
    retryable export, never an unconditional replacement. Backups are retained
    even after success so an editor holding the old inode keeps its later write.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".story-tmp-", dir=path.parent)
    displaced = False
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(content.encode("utf-8"))
            handle.flush()
            os.fsync(handle.fileno())
        if path.exists():
            # A fresh directory reserves this backup; existing backups are never reused.
            backup.parent.mkdir(parents=True, exist_ok=False)
            os.replace(path, backup)
            displaced = True
            if hashlib.sha256(backup.read_bytes()).hexdigest() not in allowed_hashes:
                fail("export_conflict", "File changed during export; displaced version preserved",
                     path=str(path), backup=str(backup))
        _publish_no_replace(tmp, path)
        if hashlib.sha256(path.read_bytes()).hexdigest() != digest(content):
            fail("export_conflict", "File changed during publication; preserve it and reconcile", path=str(path))
        return str(backup) if displaced else None
    except (OSError, StoryError) as error:
        if displaced:
            try:
                _restore_displaced_file(backup, path)
            except OSError:
                pass  # A newer file may exist. Never overwrite it to restore a backup.
            if isinstance(error, StoryError):
                error.details.setdefault("backup", str(backup))
            else:
                fail("export_io", str(error), path=str(path), backup=str(backup))
        raise
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def bounded_packet(packet, limit):
    integer(limit, "budget_bytes", 256)
    packet["budget"] = {"unit": "utf8_bytes", "limit": limit, "used": 0}
    for _ in range(8):
        used = len(dumps(packet).encode("utf-8"))
        if packet["budget"]["used"] == used:
            break
        packet["budget"]["used"] = used
    if used > limit:
        fail("budget_exceeded", "Required content cannot fit; increase the budget or narrow the range",
             minimum_bytes=used, budget_bytes=limit)
    return packet


def valid_card(raw):
    raw = object_value(raw, "card")
    cid = text_field(raw.get("id"), "card.id", 80)
    if not re.fullmatch(r"[\w.-]+", cid):
        fail("invalid_input", "card.id accepts letters, digits, underscore, dot and hyphen")
    kind = raw.get("kind", "fact")
    if kind not in KINDS:
        fail("invalid_input", f"card.kind must be one of {KINDS}")
    if type(raw.get("critical", False)) is not bool:
        fail("invalid_input", "card.critical must be boolean")
    status = raw.get("status", "active")
    if status not in ("active", "resolved"):
        fail("invalid_input", "card.status must be active or resolved")
    due = raw.get("due")
    if due is not None:
        integer(due, "card.due", 1)
    result = {"id": cid, "kind": kind, "text": text_field(raw.get("text"), "card.text"),
            "source": text_field(raw.get("source"), "card.source", 1400),
            "tags": string_list(raw.get("tags", []), "card.tags", 24),
            "critical": raw.get("critical", False), "status": status, "due": due}
    if "scope" in raw:
        scope = text_field(raw["scope"], "card.scope", 180)
        if scope != "global" and not re.fullmatch(r"(volume|arc|line|entity):[\w.-]+", scope):
            fail("invalid_input", "scope must be global or volume/arc/line/entity:ID")
        result["scope"] = scope
    return result


def valid_plan(raw):
    raw = object_value(raw, "plan")
    result = {"goal": text_field(raw.get("goal"), "plan.goal"),
              "stop": text_field(raw.get("stop"), "plan.stop"),
              "constraints": string_list(raw.get("constraints", []), "plan.constraints"),
              "requires": string_list(raw.get("requires", []), "plan.requires"),
              "tags": string_list(raw.get("tags", []), "plan.tags", 24)}
    beats = raw.get("beats")
    if not isinstance(beats, list) or not 1 <= len(beats) <= 40:
        fail("invalid_input", "plan.beats needs 1 to 40 meaningful scenes")
    result["beats"] = []
    for beat in beats:
        object_value(beat, "beat")
        result["beats"].append({key: text_field(beat.get(key), f"beat.{key}")
                                for key in ("choice", "change")})
    length = raw.get("length")
    if not isinstance(length, list) or len(length) != 2:
        fail("invalid_input", "plan.length needs [minimum_visible_chars, maximum_visible_chars]")
    lo, hi = (integer(x, "plan.length", 1) for x in length)
    if lo > hi or hi > 200000:
        fail("invalid_input", "Invalid plan length range")
    result["length"] = [lo, hi]
    method = raw.get("count_method", "visible_nonspace_v1")
    if method not in COUNT_METHODS:
        fail("invalid_input", f"plan.count_method must be one of {COUNT_METHODS}")
    include_title = raw.get("count_title", False)
    if type(include_title) is not bool:
        fail("invalid_input", "plan.count_title must be boolean")
    result.update(count_method=method, count_title=include_title)
    for key in ("volume", "arc", "line"):
        if key in raw:
            result[key] = text_field(raw[key], "plan." + key, 80)
    if "entities" in raw:
        result["entities"] = string_list(raw["entities"], "plan.entities", 40)
    if "time" in raw:
        stamp = object_value(raw["time"], "plan.time")
        result["time"] = {"clock": text_field(stamp.get("clock"), "plan.time.clock", 80)}
        for key in ("start", "end"):
            value = stamp.get(key)
            if value is not None and type(value) is not int:
                fail("invalid_input", "Story time must be integer ticks or null")
            result["time"][key] = value
        if stamp.get("start") is not None and stamp.get("end") is not None and stamp["end"] < stamp["start"]:
            fail("invalid_input", "Story time end precedes start")
    return result


def manuscript_counts(text, include_title=False):
    """Declared character counts, never platform word counts or model tokens."""
    lines = text.splitlines()
    title = re.match(r"^#\s+(\S.*)$", lines[0].lstrip("\ufeff")) if lines else None
    if title:
        lines = ([title[1]] if include_title else []) + lines[1:]
    chars = [c for c in "\n".join(lines)
             if not c.isspace() and unicodedata.category(c) not in ("Cc", "Cf")]
    return {"visible_nonspace_v1": len(chars),
            "letters_numbers_v1": sum(unicodedata.category(c)[0] in "LN" for c in chars),
            "han_v1": sum(c == "〇" or unicodedata.name(c, "").startswith(
                ("CJK UNIFIED IDEOGRAPH-", "CJK COMPATIBILITY IDEOGRAPH-")) for c in chars)}


def visible_count(text):
    return manuscript_counts(text)["visible_nonspace_v1"]


def lint_text(text, plan):
    method = plan.get("count_method", "visible_nonspace_v1")
    if method not in COUNT_METHODS:
        fail("invalid_input", f"Unknown count method: {method}")
    counts = manuscript_counts(text, plan.get("count_title", False))
    count = counts[method]
    errors, warnings = [], []
    if not plan["length"][0] <= count <= plan["length"][1]:
        errors.append({"code": "length", "actual": count, "expected": plan["length"]})
    if "\ufffd" in text or "\x00" in text:
        errors.append({"code": "corrupt_text"})
    if re.search(r"<填写[^>]*>|(?m:^\s*REPLACE_ME\s*$)", text):
        errors.append({"code": "placeholder"})
    paragraphs = [p.strip() for p in text.splitlines() if len(p.strip()) >= 20]
    repeated = [{"text": p[:120], "count": n} for p, n in Counter(paragraphs).items() if n > 1]
    if repeated:
        warnings.append({"code": "repeated_paragraph", "examples": repeated[:6],
                         "note": "Editorial signal only; repetition can be intentional"})
    return {"ok": not errors, "visible_chars": counts["visible_nonspace_v1"],
            "length_count": count, "count_method": method, "counts": counts,
            "count_scope": "body_and_lead_with_title_text" if plan.get("count_title", False) else "body_and_lead_without_first_h1",
            "unicode_version": unicodedata.unidata_version,
            "draft_sha256": digest(text), "errors": errors, "warnings": warnings}


SCHEMA = """
CREATE TABLE meta(key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE cards(id TEXT PRIMARY KEY, data TEXT NOT NULL);
CREATE TABLE plans(chapter INTEGER PRIMARY KEY, data TEXT NOT NULL);
CREATE TABLE events(seq INTEGER PRIMARY KEY AUTOINCREMENT, revision INTEGER NOT NULL,
 kind TEXT NOT NULL, data TEXT NOT NULL, created TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE sources(id TEXT PRIMARY KEY, name TEXT NOT NULL, text TEXT NOT NULL,
 coverage TEXT NOT NULL, encoding TEXT NOT NULL);
CREATE TABLE chunks(source TEXT NOT NULL REFERENCES sources(id), ordinal INTEGER NOT NULL,
 start INTEGER NOT NULL, end INTEGER NOT NULL, title TEXT NOT NULL, sha TEXT NOT NULL, analysis TEXT,
 PRIMARY KEY(source,ordinal));
"""


def index_card(db, card):
    cid = card["id"]
    db.execute("INSERT INTO card_index VALUES (?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET "
               "kind=excluded.kind,status=excluded.status,critical=excluded.critical,due=excluded.due,scope=excluded.scope",
               (cid, card["kind"], card["status"], int(card["critical"]), card["due"], card.get("scope", "global")))
    db.execute("DELETE FROM card_tags WHERE id=?", (cid,))
    db.executemany("INSERT INTO card_tags VALUES (?,?)", ((tag, cid) for tag in card["tags"]))
    search.upsert(db, "card", cid, dumps(card), {"id": cid})


def compact_event(db, kind, payload):
    if kind not in ("commit_chapter", "replace_chapter"):
        return payload
    payload = dict(payload)
    def body_ref(value):
        value = dict(value)
        if "text" in value:
            body = value.pop("text")
            sha = digest(body)
            db.execute("INSERT OR IGNORE INTO core_objects VALUES (?,?)", (sha, body))
            value["body_sha256"] = sha
        return value
    payload = body_ref(payload)
    if payload.get("previous"):
        payload["previous"] = body_ref(payload["previous"])
    return payload


class Book:
    fail = staticmethod(fail)
    safe_path = staticmethod(safe_path)

    def __init__(self, root, integrity="strict"):
        if integrity not in ("strict", "local"):
            fail("invalid_input", "integrity must be strict or local")
        self.integrity = integrity
        self._verified_paths = 0
        self.root = Path(root).expanduser().resolve()
        self.path = safe_path(self.root, ".story/state.sqlite3")
        if not self.path.is_file():
            fail("book_missing", "No Story Codex state here; initialize an explicit book directory",
                 book=str(self.root))
        self.db = sqlite3.connect(self.path.as_uri() + "?mode=rw", uri=True, timeout=10)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA foreign_keys=ON")
        self.db.execute("PRAGMA synchronous=FULL")
        try:
            schema = self.meta("schema")
        except BaseException:
            self.db.close()
            raise
        if schema != SCHEMA_VERSION:
            self.db.close()
            fail("schema_mismatch", "Run migrate on a backed-up book copy to upgrade; do not overwrite the database", actual=schema, required=SCHEMA_VERSION)

    def close(self):
        self.db.close()

    @contextmanager
    def read_snapshot(self):
        """Keep composite reads consistent without ending a caller's transaction."""
        owns_read = not self.db.in_transaction
        if owns_read:
            self.db.execute("BEGIN")
        try:
            yield
        finally:
            if owns_read:
                self.db.rollback()

    @classmethod
    def create(cls, root, title, kind):
        title = text_field(title, "title", 200)
        if kind not in ("long", "short", "analysis"):
            fail("invalid_input", "Unsupported book kind")
        root = Path(root).expanduser().resolve()
        root.mkdir(parents=True, exist_ok=True)
        path = safe_path(root, ".story/state.sqlite3")
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with path.open("xb"):
                pass
        except FileExistsError:
            fail("book_exists", "State already exists; use status, never reinitialize", book=str(root))
        db = sqlite3.connect(path)
        try:
            db.executescript(SCHEMA + storage.SCHEMA + search.SCHEMA + world.SCHEMA + history.SCHEMA)
            values = {"schema": SCHEMA_VERSION, "revision": 0, "last_chapter": 0,
                      "imported_through": 0, "title": title, "kind": kind, "id": str(uuid.uuid4())}
            with db:
                db.executemany("INSERT INTO meta VALUES (?,?)", [(k, dumps(v)) for k, v in values.items()])
        finally:
            db.close()
        return {"created": str(root), **values}

    def meta(self, key):
        row = self.db.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
        if not row:
            fail("state_corrupt", "Missing required metadata", key=key)
        return json.loads(row[0])

    def set_meta(self, key, value):
        self.db.execute("INSERT INTO meta VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, dumps(value)))

    @contextmanager
    def transaction(self, expected=None):
        with storage.operation_lock(self):
            self.db.execute("BEGIN IMMEDIATE")
            try:
                if expected is not None and integer(expected, "expected revision") != self.meta("revision"):
                    fail("stale_revision", "State changed; reload context and recheck the draft",
                         expected=expected, actual=self.meta("revision"))
                yield
                self.db.commit()
            except BaseException:
                self.db.rollback()
                raise

    def event(self, kind, payload):
        rev = self.meta("revision") + 1
        self.set_meta("revision", rev)
        self.db.execute("INSERT INTO events(revision,kind,data) VALUES (?,?,?)", (rev, kind, dumps(compact_event(self.db, kind, payload))))
        return rev

    def cards(self, ids=None):
        if ids is None:
            rows = self.db.execute("SELECT id,data FROM cards ORDER BY id")
        else:
            ids = list(set(ids))
            if not ids:
                return {}
            rows = self.db.execute("SELECT id,data FROM cards WHERE id IN (" + ",".join("?" for _ in ids) + ")", ids)
        return {row[0]: json.loads(row[1]) for row in rows}

    def intern_body(self, text):
        sha = digest(text)
        self.db.execute("INSERT OR IGNORE INTO core_objects VALUES (?,?)", (sha, text))
        return sha

    def index_chapter(self, chapter, text, summary):
        search.upsert(self.db, "chapter", str(chapter), text, {"chapter": chapter, "summary": summary})
        search.upsert(self.db, "chapter_summary", str(chapter), summary, {"chapter": chapter})

    def put_card(self, card):
        self.db.execute("INSERT INTO cards VALUES (?,?) ON CONFLICT(id) DO UPDATE SET data=excluded.data",
                        (card["id"], dumps(card)))
        index_card(self.db, card)

    def delete_card(self, cid):
        search.remove(self.db, "card", cid)
        self.db.execute("DELETE FROM cards WHERE id=?", (cid,))

    def get_plan(self, chapter):
        row = self.db.execute("SELECT data FROM plans WHERE chapter=?", (chapter,)).fetchone()
        if not row:
            fail("plan_missing", "Save a concrete chapter plan before drafting", chapter=chapter)
        return json.loads(row[0])

    def save_notes(self, payload, expected):
        if not isinstance(payload, list) or len(payload) > 200:
            fail("invalid_input", "notes input must be an array of at most 200 cards")
        cards = [valid_card(card) for card in payload]
        if len({card["id"] for card in cards}) != len(cards):
            fail("duplicate_id", "Duplicate card ids in the same batch")
        with self.transaction(expected):
            old = self.cards(c["id"] for c in cards)
            changes = [card for card in cards if old.get(card["id"]) != card]
            if changes:
                for card in changes:
                    self.put_card(card)
                self.event("notes", {"before": {c["id"]: old.get(c["id"]) for c in changes}, "after": changes})
            revision = self.meta("revision")
        return {"updated": len(changes), "revision": revision}

    def save_plan(self, chapter, payload, expected):
        integer(chapter, "chapter", 1)
        plan = valid_plan(payload)
        with self.transaction(expected):
            old = self.db.execute("SELECT data FROM plans WHERE chapter=?", (chapter,)).fetchone()
            if not old or old[0] != dumps(plan):
                self.db.execute("INSERT INTO plans VALUES (?,?) ON CONFLICT(chapter) DO UPDATE SET data=excluded.data",
                                (chapter, dumps(plan)))
                self.event("plan", {"chapter": chapter, "before": json.loads(old[0]) if old else None, "after": plan})
            revision = self.meta("revision")
        return {"chapter": chapter, "revision": revision}

    def _check_artifact(self, relative, new_sha, old_sha):
        target = safe_path(self.root, relative)
        current = None
        if target.exists():
            if not target.is_file():
                fail("export_conflict", "Export target is not a regular file", path=str(target))
            current = hashlib.sha256(target.read_bytes()).hexdigest()
            if current not in {new_sha, old_sha}:
                fail("export_conflict", "Export file was edited outside the state tool; preserve it and reconcile",
                     path=str(target))
        self._last_artifact_check = (relative, current)
        return target

    def queue_artifact(self, relative, content, accepted_sha=None):
        row = self.db.execute("SELECT written_sha FROM artifacts WHERE path=?", (relative,)).fetchone()
        self._check_artifact(relative, digest(content), accepted_sha or (row[0] if row else None))
        self.db.execute("INSERT INTO artifacts(path,content,sha) VALUES (?,?,?)",
                        (relative, content, digest(content)))
        if accepted_sha:
            # Persist the reviewed disk version for post-commit export retries.
            self.db.execute("UPDATE artifacts SET written_sha=? WHERE path=?", (accepted_sha, relative))

    def _artifact_rows(self):
        if self.integrity == "strict":
            return self.db.execute("SELECT path,sha,written_sha FROM artifact_state ORDER BY path").fetchall()
        paths = set(getattr(self, "_local_artifacts", []))
        paths.add(f"chapters/{self.meta('last_chapter'):04d}.md")
        marks = ",".join("?" for _ in paths)
        return self.db.execute("SELECT path,sha,written_sha FROM artifact_state WHERE "
            f"path IN ({marks}) UNION SELECT path,sha,written_sha FROM artifact_state "
            "WHERE written_sha IS NULL OR written_sha<>sha ORDER BY path", tuple(paths)).fetchall()

    def _integrity_report(self):
        total = self.db.execute("SELECT count(*) FROM artifact_state").fetchone()[0]
        audit = self.db.execute("SELECT revision FROM integrity_audits WHERE id=1").fetchone()
        return {"mode": self.integrity, "verified_file_count": self._verified_paths,
                "unverified_archive_count": max(0, total-self._verified_paths),
                "last_full_audit_revision": audit[0] if audit else None,
                "full_book_verified": self.integrity == "strict" and getattr(self, "_health_clean", False),
                "note": "Hash verification is a point-in-time observation; outside editors can save again."}

    def export(self, safe_only=False):
        written, backups, errors = [], [], {}
        def remember(relative, error):
            item = errors.setdefault(relative, {"path": relative, "message": str(error),
                "code": error.code if isinstance(error, StoryError) else "io_error"})
            if isinstance(error, StoryError):
                item.setdefault("details", {}).update(error.details)
        # The OS lock serializes compliant state writers. File I/O does not hold a
        # SQLite write transaction; the expected SHA is rechecked before acknowledgement.
        with storage.operation_lock(self):
            rows = self._artifact_rows()
            snapshots = {}
            for row in rows:
                try:
                    self._check_artifact(row["path"], row["sha"], row["written_sha"])
                    snapshots[row["path"]] = self._last_artifact_check[1]
                except (OSError, StoryError) as error:
                    if not safe_only:
                        raise
                    remember(row["path"], error)
            for row in rows:
                relative = row["path"]
                if relative in errors:
                    continue
                try:
                    if snapshots[relative] != row["sha"]:
                        target = self._check_artifact(relative, row["sha"], row["written_sha"])
                        content = self.db.execute("SELECT text FROM core_objects WHERE sha=?", (row["sha"],)).fetchone()[0]
                        backup = safe_path(self.root, f".story/export-backups/{uuid.uuid4().hex}/{relative}")
                        saved = atomic_write(target, content, {row["sha"], row["written_sha"]}, backup)
                        if saved:
                            backups.append(saved)
                        written.append(relative)
                    if row["written_sha"] != row["sha"]:
                        with self.transaction():
                            live = self.db.execute("SELECT sha FROM artifact_state WHERE path=?", (relative,)).fetchone()
                            if not live or live[0] != row["sha"]:
                                fail("stale_export", "Queued content changed during export; retry", path=relative)
                            self.db.execute("UPDATE artifact_state SET written_sha=? WHERE path=?", (row["sha"], relative))
                except (OSError, StoryError) as error:
                    if not safe_only:
                        raise
                    remember(relative, error)
            # A second pass catches edits of an early file while later files were processed.
            pending, changed = [], []
            for row in rows:
                try:
                    self._check_artifact(row["path"], row["sha"], row["written_sha"])
                    if self._last_artifact_check[1] != row["sha"]:
                        pending.append(row["path"])
                except (OSError, StoryError) as error:
                    changed.append(row["path"])
                    remember(row["path"], error)
                    if not safe_only:
                        raise
            self._verified_paths = len(rows)
            clean = not pending and not changed
            self._health_clean = clean
            if not clean and not safe_only:
                fail("export_conflict", "Files changed or disappeared during export", pending=pending[:20], changed=changed[:20])
            if clean and self.integrity == "strict":
                with self.transaction():
                    self.db.execute("INSERT OR REPLACE INTO integrity_audits(id,revision,checked) VALUES(1,?,?)",
                                    (self.meta("revision"), len(rows)))
            result = {"exported": written, "backups": backups,
                      "exports_complete": clean if self.integrity == "strict" else (False if not clean else None),
                      "scope_exports_complete": clean, "integrity": self._integrity_report()}
            if safe_only:
                result.update(safe_only=True, pending_exports=pending[:20], pending_export_count=len(pending),
                    changed_exports=changed[:20], changed_export_count=len(changed),
                    export_errors=list(errors.values())[:20], export_error_count=len(errors))
                if not clean:
                    result["recovery"] = "Resolve remaining paths; use reconcile for an outside edit of the latest chapter."
            return result

    def delivery(self, result):
        try:
            return {**result, **self.export()}
        except (OSError, StoryError, sqlite3.Error) as error:
            # The SQLite transaction is already durable; never misreport this as a rolled-back commit.
            return {**result, "exports_complete": False,
                    "recovery": "Retry export after IO/lock recovery; use reconcile for an externally edited latest chapter. Preserved versions: .story/export-backups/",
                    "export_error": str(error),
                    "export_details": {"code": error.code, **error.details} if isinstance(error, StoryError) else
                                      {"code": "sqlite_error" if isinstance(error, sqlite3.Error) else "io_error"}}

    def _export_health(self):
        pending, drift = [], []
        rows = self._artifact_rows()
        for row in rows:
            try:
                self._check_artifact(row["path"], row["sha"], row["written_sha"])
                if self._last_artifact_check[1] != row["sha"] or row["written_sha"] != row["sha"]:
                    pending.append(row["path"])
            except StoryError:
                drift.append(row["path"])
        self._verified_paths = len(rows)
        self._health_clean = not pending and not drift
        return pending, drift

    def status(self):
        pending, drift = self._export_health()
        sources = self.list_sources(0, 3, 6000)
        return {"book": str(self.root), "id": self.meta("id"), "title": self.meta("title"),
                "kind": self.meta("kind"), "revision": self.meta("revision"),
                "last_chapter": self.meta("last_chapter"), "next_chapter": self.meta("last_chapter") + 1,
                "imported_through": self.meta("imported_through"),
                "cards": self.db.execute("SELECT count(*) FROM cards").fetchone()[0],
                "pending_exports": pending[:20], "pending_export_count": len(pending),
                "changed_exports": drift[:20], "changed_export_count": len(drift),
                "sources": sources["total"], "recent_sources": sources["results"],
                "more_sources": sources["next_offset"] < sources["total"], "integrity": self._integrity_report()}

    def _external_snapshot(self, chapter):
        existing = self.db.execute("SELECT imported FROM chapters WHERE chapter=?", (chapter,)).fetchone()
        if chapter != self.meta("last_chapter") or not existing or existing["imported"]:
            fail("chapter_order", "Only the latest native chapter can be reconciled")
        relative = f"chapters/{chapter:04d}.md"
        target = safe_path(self.root, relative)
        if not target.is_file():
            fail("external_missing", "Recover the missing export before reconciling", path=str(target))
        return {"path": str(target), "sha256": hashlib.sha256(target.read_bytes()).hexdigest()}

    def reconcile(self, chapter, draft=None, raw=None, budget=16000):
        integer(chapter, "chapter", 1)
        if (draft is None) != (raw is None):
            fail("invalid_input", "Supply both draft and input to apply a reconciliation, or neither to inspect")
        if draft is None:
            return self.context(chapter, budget, _reconcile=True)
        return self.commit(chapter, draft, raw, replace_last=True, accept_external=True)

    def context(self, chapter, budget=16000, _reconcile=False):
        integer(chapter, "chapter", 1)
        # Read one SQLite snapshot. Concurrent writers produce either the old or new packet, never a mix.
        self.db.execute("BEGIN")
        try:
            external = self._external_snapshot(chapter) if _reconcile else None
            pending, drift = self._export_health()
            if external:
                drift = [p for p in drift if p != f"chapters/{chapter:04d}.md"]
            if pending or drift:
                fail("exports_unresolved", "Recover exports or reconcile outside edits before writing",
                     pending=pending[:10], changed=drift[:10])
            plan = self.get_plan(chapter)
            scopes = {"global"}
            scopes.update(f"{key}:{plan[key]}" for key in ("volume", "arc", "line") if key in plan)
            scopes.update("entity:" + eid for eid in world.resolve(self, plan.get("entities", []), plan.get("line")))
            marks = ",".join("?" for _ in scopes)
            pinned = {r[0] for r in self.db.execute(
                f"SELECT id FROM card_index WHERE scope IN ({marks}) AND status='active' "
                "AND (critical=1 OR (kind='hook' AND due<=?))", (*sorted(scopes), chapter))}
            selected = pinned | set(plan["requires"])
            tags = plan["tags"]
            if tags:
                selected.update(r[0] for r in self.db.execute(
                    "SELECT DISTINCT i.id FROM card_tags t JOIN card_index i ON i.id=t.id "
                    f"WHERE t.tag IN ({','.join('?' for _ in tags)}) AND i.scope IN ({marks}) "
                    "AND i.status='active' ORDER BY i.id LIMIT 256", (*tags, *sorted(scopes))))
            replacing = self.db.execute("SELECT receipt FROM chapters WHERE chapter=?", (chapter,)).fetchone()
            if replacing:
                receipt = json.loads(replacing[0])
                if receipt.get("history_branch") or receipt.get("world_changes"):
                    fail("history_revision_required", "Use a history branch to revise a chapter published with a global state correction")
                selected.update(receipt.get("before", {}))
            cards = self.cards(selected)
            last = self.meta("last_chapter")
            if chapter not in (last, last + 1):
                fail("chapter_order", "Context supports the next chapter or revision of the latest chapter")
            previous = self.db.execute("SELECT chapter,summary,substr(text,-600) FROM chapters WHERE chapter<? ORDER BY chapter DESC LIMIT 1",
                                       (chapter,)).fetchone()
            if replacing:
                receipt = json.loads(replacing[0])
                for cid, value in receipt.get("before", {}).items():
                    if cards.get(cid) != receipt.get("after", {}).get(cid):
                        fail("revised_state_conflict", "A card changed after this chapter; reconcile before replacing", card=cid)
                    if value is None:
                        cards.pop(cid, None)
                    else:
                        cards[cid] = value
            required = set(plan["requires"])
            missing = sorted(required - cards.keys())
            if missing:
                fail("missing_required_cards", "Plan references unknown cards", ids=missing)
            required.update(c["id"] for c in cards.values()
                            if c.get("scope", "global") in scopes and c["status"] == "active" and (c["critical"] or
                               (c["kind"] == "hook" and c["due"] is not None and c["due"] <= chapter)))
            packet = {"book_id": self.meta("id"), "revision": self.meta("revision"), "chapter": chapter,
                      "mode": "replace_last" if replacing else "next", "plan": plan,
                      "required_cards": [cards[cid] for cid in sorted(required)], "optional_cards": [],
                      "previous": {"chapter": previous[0], "summary": previous[1], "tail": previous[2][-600:]} if previous else None,
                      "omitted_optional_count": 0}
            if external:
                packet.update(mode="reconcile_last", external_edit=external)
            if any(key in plan for key in ("volume", "arc", "line", "entities", "time")):
                packet["world"] = world.context(self, plan, chapter)
            if self.integrity != "strict":
                packet["integrity"] = self._integrity_report()
            tags = set(plan["tags"])
            search = dumps(plan).casefold()
            optional = [c for c in cards.values() if c["id"] not in required and c["status"] == "active"]
            def score(card):
                return 5 * len(tags.intersection(card["tags"])) + sum(tag.casefold() in search for tag in card["tags"]) + 2 * (card["id"].casefold() in search)
            candidates = sorted((c for c in optional if score(c) > 0), key=lambda c: (-score(c), c["id"]))
            active_total = self.db.execute("SELECT count(*) FROM card_index WHERE status='active'").fetchone()[0]
            packet["omitted_optional_count"] = max(0, active_total - sum(c["status"] == "active" for c in packet["required_cards"]))
            bounded_packet(packet, budget)
            for card in candidates:
                packet["optional_cards"].append(card)
                packet["omitted_optional_count"] -= 1
                try:
                    bounded_packet(packet, budget)
                except StoryError as error:
                    if error.code != "budget_exceeded":
                        raise
                    packet["optional_cards"].pop()
                    packet["omitted_optional_count"] += 1
            return bounded_packet(packet, budget)
        finally:
            self.db.rollback()

    def recall(self, query, budget=8000):
        text_field(query, "query", 200)
        with self.read_snapshot():
            result = search.query(self.db, query, limit=128)
            cards = self.cards(item["key"] for item in result["matches"] if item["kind"] == "card")
        found = []
        for item in result["matches"]:
            if item["kind"] == "card" and item["key"] in cards:
                found.append({"type": "card", **cards[item["key"]]})
            else:
                found.append({"type": item["kind"], "chapter": item["metadata"].get("chapter"),
                              "snippet": item["snippet"], "source_sha256": item["source_sha256"],
                              "path": f"chapters/{int(item['key']):04d}.md" if item["kind"] in ("chapter", "chapter_summary") else None})
        packet = {"query": query, "matches": [], "total": len(found), "omitted": len(found),
                  "complete": False if found else result["complete"], "no_match_confirmed": result["no_match_confirmed"],
                  # Reserve truncation metadata before packing, so marking an
                  # omitted result cannot itself overflow an otherwise full packet.
                  "truncated_reasons": result["truncated_reasons"] + (["budget_limit"] if found else []),
                  "total_semantics": "bounded verified matches; use a narrower query if incomplete"}
        for item in found:
            packet["matches"].append(item)
            packet["omitted"] -= 1
            try:
                bounded_packet(packet, budget)
            except StoryError as error:
                if error.code != "budget_exceeded":
                    raise
                packet["matches"].pop()
                packet["omitted"] += 1
        if not packet["omitted"]:
            packet["complete"] = result["complete"]
            packet["truncated_reasons"] = result["truncated_reasons"]
        return bounded_packet(packet, budget)

    def lint(self, chapter, draft):
        return lint_text(read_text(draft), self.get_plan(chapter))

    def chapter_read(self, chapter, sha=None, start=0, end=None, budget=12000):
        integer(chapter, "chapter", 1)
        integer(start, "start")
        if sha is None:
            row = self.db.execute("SELECT sha FROM chapter_state WHERE chapter=?", (chapter,)).fetchone()
        else:
            if not re.fullmatch(r"[0-9a-f]{64}", sha):
                fail("invalid_input", "sha256 must be a SHA-256 digest")
            row = self.db.execute("SELECT sha FROM chapter_state WHERE chapter=? AND sha=? UNION "
                "SELECT sha FROM history_versions WHERE chapter=? AND sha=? LIMIT 1", (chapter, sha, chapter, sha)).fetchone()
        if not row:
            fail("chapter_missing", "No matching immutable chapter version in this book", chapter=chapter)
        sha = row[0]
        size = self.db.execute("SELECT length(text) FROM core_objects WHERE sha=?", (sha,)).fetchone()[0]
        end = min(start + 2000, size) if end is None else integer(end, "end", 1)
        if not start < end <= size:
            fail("invalid_range", "Use Unicode character offsets within this chapter", characters=size)
        text = self.db.execute("SELECT substr(text,?,?) FROM core_objects WHERE sha=?", (start+1, end-start, sha)).fetchone()[0]
        return bounded_packet({"chapter": chapter, "source_sha256": sha, "start": start, "end": end,
                               "characters": size, "next_start": end if end < size else None, "text": text}, budget)

    def dependency_candidates(self, chapter, budget=16000):
        packet = self.context(chapter, budget)
        found = {("card", c["id"]): {"kind": "card", "ref": c["id"], "sha": digest(dumps(c))}
                 for c in packet["required_cards"] + packet["optional_cards"]}
        world_packet = packet.get("world", {})
        for field, kind in (("entities", "entities"), ("facts", "facts"), ("propositions", "facts"),
                            ("knowledge", "knowledge"), ("hooks", "hooks"), ("rules", "rules"),
                            ("uses", "uses"), ("arc_steps", "arc_steps"), ("line", "lines")):
            values = world_packet.get(field, [])
            if values is None:
                continue
            if isinstance(values, dict):
                values = [values]
            for record in values:
                sha = world.resolve_dependency(self, kind, record["id"])
                if sha:
                    key = ("world." + kind, record["id"])
                    found[key] = {"kind": key[0], "ref": key[1], "sha": sha}
        for key in ("previous",):
            if packet.get(key):
                ref = packet[key]["chapter"]
                row = self.db.execute("SELECT sha FROM chapter_state WHERE chapter=?", (ref,)).fetchone()
                found[("chapter", str(ref))] = {"kind": "chapter", "ref": str(ref), "sha": row[0]}
        if packet["revision"] != self.meta("revision"):
            fail("stale_revision", "State changed while resolving dependency candidates; retry")
        return bounded_packet({"book_id": packet["book_id"], "revision": packet["revision"], "chapter": chapter,
            "candidates": [found[k] for k in sorted(found)],
            "review_required": "Select actual dependencies, add missing sources, then declare completeness with a concrete review note."}, budget)

    def world_read(self, kind, rid, budget=12000):
        with self.read_snapshot():
            return self._world_read(kind, rid, budget)

    def _world_read(self, kind, rid, budget):
        if kind not in world.FIELDS or kind == "aliases":
            fail("invalid_input", "Choose an individual world record kind; resolve aliases through entities")
        value = world._stored(self, kind, text_field(rid, "record id", 80))
        if value is None:
            fail("world_reference", "Unknown world record", kind=kind, id=rid)
        row, evidence, entities, requires = value
        record = dict(row)
        for field, typ in world.FIELDS[kind].items():
            if typ == "bool":
                record[field] = bool(record[field])
        if evidence:
            record["evidence"] = ({"kind": "chapter", "chapter": evidence["chapter"], "sha256": evidence["sha"], "quote": evidence["quote"]}
                                  if evidence["mode"] == "chapter" else {"kind": "author_plan", "note": evidence["note"]})
        if entities:
            record["entities"] = entities
        if kind == "rules":
            record["requires"] = requires
        sha = world.resolve_dependency(self, kind, rid)
        retired = self.db.execute("SELECT retired FROM world_evidence WHERE kind=? AND record_id=?", (kind,rid)).fetchone()
        return bounded_packet({"kind": kind, "id": rid, "record_sha256": sha, "evidence_current": sha is not None,
                               "retired": bool(retired[0]) if retired else False, "payload": {kind: [record]}}, budget)

    def prepare(self, chapter, draft, reconcile=False, budget=16000):
        # Context captures a consistent plan/revision and checks recovery/replace
        # boundaries. Later changes are rejected by commit's existing fences.
        packet = self.context(chapter, budget, _reconcile=reconcile)
        text = read_text(draft)
        lint = lint_text(text, packet["plan"])
        delta = {"book_id": packet["book_id"], "base_revision": packet["revision"],
                 "summary": "<填写本章实际结果与下一章衔接>", "changes": [],
                 "review": {"draft_sha256": lint["draft_sha256"],
                            "checks": {key: {"note": "<填写审查观察>", "quote": "<填写正文原句>"}
                                       for key in CHECKS},
                            "issues": [{"severity": "blocker", "issue": "尚未完成语义审查；填写观察与引文并处理实际问题后移除此占位项。"}]}}
        if reconcile:
            delta["external_sha256"] = packet["external_edit"]["sha256"]
        result = {"mode": packet["mode"], "lint": lint, "delta": delta,
                "ready_to_commit": False,
                "next": "Complete the summary, evidence-based review and state changes; do not change identity or hash fields."}
        if "world" in packet:
            result["world_check"] = world.check(self, {**packet["plan"], "chapter": chapter})
        return bounded_packet(result, budget)

    def validate_delta(self, text, raw):
        raw = object_value(raw, "delta")
        if raw.get("book_id") != self.meta("id"):
            fail("wrong_book", "Delta belongs to a different book or has no book_id")
        integer(raw.get("base_revision"), "delta.base_revision")
        text_field(raw.get("summary"), "delta.summary", 800)
        review = object_value(raw.get("review"), "delta.review")
        if review.get("draft_sha256") != digest(text):
            fail("stale_review", "Review must refer to the exact current draft SHA-256")
        checks = object_value(review.get("checks"), "review.checks")
        for key in CHECKS:
            check = object_value(checks.get(key), f"review.checks.{key}")
            text_field(check.get("note"), f"review.{key}.note", 1200)
            if text_field(check.get("quote"), f"review.{key}.quote", 1200) not in text:
                fail("invalid_evidence", "Review quote is absent from the draft", check=key)
        issues = review.get("issues")
        if not isinstance(issues, list) or len(issues) > 100:
            fail("invalid_input", "review.issues must be an array, at most 100 items")
        for issue in issues:
            object_value(issue, "review.issue")
            text_field(issue.get("issue"), "review.issue.issue", 1200)
            if issue.get("severity") not in ("blocker", "advice"):
                fail("invalid_input", "Issue severity must be blocker or advice")
            if issue["severity"] == "blocker":
                fail("review_blocker", "Resolve blocking findings before committing", issue=issue["issue"])
        changes = raw.get("changes")
        if not isinstance(changes, list) or len(changes) > 100:
            fail("invalid_input", "delta.changes must be an array, at most 100 items")
        ids = []
        for change in changes:
            object_value(change, "change")
            ids.append(text_field(change.get("id"), "change.id", 80))
            if text_field(change.get("quote"), "change.quote", 1200) not in text:
                fail("invalid_evidence", "State change quote is absent from the draft", card=change["id"])
        if len(set(ids)) != len(ids):
            fail("duplicate_id", "Each card can change once per transaction")
        if "world_changes" in raw:
            object_value(raw["world_changes"], "delta.world_changes")
        return raw

    def commit(self, chapter, draft, raw, replace_last=False, accept_external=False):
        integer(chapter, "chapter", 1)
        text = read_text(draft)
        raw = self.validate_delta(text, raw)
        inputs = {"delta": raw, "sha": digest(text), "replace_last": replace_last}
        if accept_external:
            inputs["accept_external"] = True
            if not replace_last or not re.fullmatch(r"[0-9a-f]{64}", str(raw.get("external_sha256", ""))):
                fail("invalid_input", "Reconciliation requires the inspected external_sha256 and a latest-chapter replacement")
        input_hash = digest(dumps(inputs))
        idempotent = False
        with self.transaction():
            existing = self.db.execute("SELECT * FROM chapters WHERE chapter=?", (chapter,)).fetchone()
            if existing and existing["input_hash"] == input_hash:
                idempotent = True
            else:
                if accept_external:
                    external = self._external_snapshot(chapter)
                    if external["sha256"] != raw["external_sha256"]:
                        fail("stale_external", "External draft changed; inspect and review the new version",
                             path=external["path"], expected=raw["external_sha256"], actual=external["sha256"])
                pending, drift = self._export_health()
                if accept_external:
                    drift = [p for p in drift if p != f"chapters/{chapter:04d}.md"]
                if pending or drift:
                    fail("exports_unresolved", "Resolve previous exports before committing another change",
                         pending=pending[:10], changed=drift[:10])
                if raw["base_revision"] != self.meta("revision"):
                    fail("stale_revision", "State changed; reload and review before retrying",
                         expected=raw["base_revision"], actual=self.meta("revision"))
                last = self.meta("last_chapter")
                if replace_last:
                    if chapter != last or not existing or existing["imported"]:
                        fail("chapter_order", "Only the latest native chapter can be replaced")
                elif existing or chapter != last + 1:
                    fail("chapter_order", "Commit exactly the next chapter; existing chapters are never overwritten")
                plan = self.get_plan(chapter)
                check = lint_text(text, plan)
                if not check["ok"]:
                    fail("lint_failed", "Draft fails deterministic checks", lint=check)
                previous = json.loads(existing["receipt"]) if replace_last else {}
                if previous.get("history_branch") or previous.get("world_changes"):
                    fail("history_revision_required", "Use a history branch for this revision")
                touched = set(plan["requires"]) | {c["id"] for c in raw["changes"]} | set(previous.get("before", {}))
                before_state = self.cards(touched)
                if replace_last:
                    for cid, value in previous["before"].items():
                        if before_state.get(cid) != previous["after"].get(cid):
                            fail("revised_state_conflict", "Card changed since last chapter; reconcile first", card=cid)
                        if value is None:
                            self.delete_card(cid)
                        else:
                            self.put_card(value)
                state = self.cards(touched)
                missing = sorted(set(plan["requires"]) - state.keys())
                if missing:
                    fail("missing_required_cards", "Plan references unknown cards", ids=missing)
                dependency_metadata = history.validate_commit_dependencies(self, raw, chapter)
                before, after = {}, {}
                for change in raw["changes"]:
                    cid = change["id"]
                    before[cid] = state.get(cid)
                    merged = {**state.get(cid, {}), **{k: v for k, v in change.items() if k != "quote"}}
                    merged["source"] = f"chapter:{chapter} quote:{change['quote']}"
                    card = valid_card(merged)
                    self.put_card(card)
                    after[cid] = card
                receipt = {"input": raw, "before": before, "after": after, "lint": check}
                receipt.update(dependency_metadata)
                self.queue_artifact(f"chapters/{chapter:04d}.md", text,
                                    accepted_sha=raw["external_sha256"] if accept_external else None)
                self.db.execute("INSERT INTO chapters VALUES (?,?,?,?,?,?,0)",
                                (chapter, text, digest(text), raw["summary"], dumps(receipt), input_hash))
                if raw.get("world_changes"):
                    changes = world.apply_in_transaction(self, raw["world_changes"])
                    receipt["world_changes"] = changes
                    checked_world = world.check_transition(self, plan, chapter, raw["world_changes"])
                    if not checked_world["ok"]:
                        fail("world_constraint", "Resolve recorded rule/resource conflicts in the actual chapter changes", checks=checked_world)
                    receipt["world_checks"] = checked_world
                    self.db.execute("UPDATE chapters SET receipt=? WHERE chapter=?", (dumps(receipt), chapter))
                self.index_chapter(chapter, text, raw["summary"])
                self.set_meta("last_chapter", chapter)
                self.event("replace_chapter" if replace_last else "commit_chapter",
                           {"chapter": chapter, "text": text, "receipt": receipt,
                            "previous": dict(existing) if existing else None})
                history.on_commit(self, chapter, plan, receipt, text, digest(text))
            # Construct the durable receipt from this transaction, before another
            # writer can acquire an exclusive lock and block post-commit reads.
            revision = self.meta("revision")
        return self.delivery({"committed": True, "idempotent": idempotent, "chapter": chapter,
                              "revision": revision, "path": str(self.root / f"chapters/{chapter:04d}.md")})

    def adopt(self, chapter, draft, summary, expected):
        integer(chapter, "chapter", 1)
        summary = text_field(summary, "summary", 800)
        text = read_text(draft)
        if "\x00" in text:
            fail("corrupt_text", "Remove NUL characters before adopting; SQLite text offsets stop at NUL")
        if not visible_count(text):
            fail("empty_source", "Cannot adopt an empty chapter")
        with self.transaction(expected):
            if self.meta("last_chapter") != 0:
                fail("adopt_nonempty", "Adoption only initializes a fresh book baseline")
            receipt = {"source_path": str(Path(draft).resolve()), "quality": "imported_unverified"}
            self.queue_artifact(f"chapters/{chapter:04d}.md", text)
            self.db.execute("INSERT INTO chapters VALUES (?,?,?,?,?,?,1)",
                            (chapter, text, digest(text), summary, dumps(receipt), digest(dumps(receipt))))
            self.index_chapter(chapter, text, summary)
            self.set_meta("last_chapter", chapter)
            self.set_meta("imported_through", chapter)
            self.event("adopt", {"chapter": chapter, "receipt": receipt, "summary": summary})
            history.on_commit(self, chapter, {}, receipt, text, digest(text))
            revision = self.meta("revision")
        return self.delivery({"adopted_through": chapter, "revision": revision,
                              "quality": "imported_unverified"})

    def source(self, sid):
        row = self.db.execute("SELECT * FROM sources WHERE id=?", (sid,)).fetchone()
        if not row:
            fail("source_missing", "Unknown source id", source=sid)
        return row

    def source_info(self, sid):
        row = self.db.execute("SELECT s.id,s.name,s.coverage,s.encoding,t.characters FROM sources s "
                              "JOIN source_stats t ON t.source=s.id WHERE s.id=?", (sid,)).fetchone()
        if not row:
            fail("source_missing", "Unknown source id", source=sid)
        return row

    def _source_slice(self, sid, start, end):
        return self.db.execute("SELECT substr(text,?,?) FROM sources WHERE id=?", (start+1, end-start, sid)).fetchone()[0]

    def _complete_noncontent_chunks(self, sid, text=None):
        # Classify new/legacy chunks once. Later calls inspect only known whitespace
        # candidates, not every pending narrative chunk or the whole source in Python.
        unclassified = self.db.execute("SELECT c.ordinal,c.start,c.end FROM chunks c LEFT JOIN chunk_classification k "
            "ON k.source=c.source AND k.ordinal=c.ordinal WHERE c.source=? AND k.ordinal IS NULL", (sid,)).fetchall()
        if unclassified:
            if text is None:
                text = self.source(sid)["text"]
            self.db.executemany("INSERT INTO chunk_classification VALUES (?,?,?)",
                ((sid, r["ordinal"], int(not text[r["start"]:r["end"]].strip())) for r in unclassified))
        rows = self.db.execute("SELECT c.ordinal,c.start,c.end,c.sha FROM chunk_classification k JOIN chunks c "
            "ON c.source=k.source AND c.ordinal=k.ordinal WHERE k.source=? AND k.noncontent=1 "
            "AND c.analysis IS NULL ORDER BY c.ordinal", (sid,)).fetchall()
        for row in rows:
            chunk = text[row["start"]:row["end"]] if text is not None else self._source_slice(sid,row["start"],row["end"])
            if not chunk or chunk.strip():
                continue
            if digest(chunk) != row["sha"]:
                fail("source_hash_mismatch", "Saved whitespace chunk does not match its source hash", source=sid, chunk=row["ordinal"])
            analysis = {"kind": "non_content", "chunk_sha256": row["sha"],
                        "summary": "此块仅含空白字符；保留原文范围，不生成剧情或文学结论。", "findings": []}
            self.db.execute("UPDATE chunks SET analysis=? WHERE source=? AND ordinal=? AND analysis IS NULL",
                            (dumps(analysis), sid, row["ordinal"]))
            self.event("analysis", {"source": sid, "chunk": row["ordinal"], "before": None, "after": analysis})

    def ingest(self, file, coverage="unknown", encoding="utf-8-sig", chunk_chars=2400):
        integer(chunk_chars, "chunk_chars", 256)
        if chunk_chars > 10000 or coverage not in ("unknown", "partial", "complete"):
            fail("invalid_input", "Invalid chunk size or source coverage")
        raw_bytes = Path(file).read_bytes()
        text = raw_bytes.decode(encoding)
        if "\x00" in text:
            fail("corrupt_text", "Remove NUL characters before ingesting; SQLite text offsets stop at NUL")
        if not text.strip():
            fail("empty_source", "Source contains no text")
        sid = hashlib.sha256(raw_bytes).hexdigest()
        with self.transaction():
            existing = self.db.execute("SELECT * FROM sources WHERE id=?", (sid,)).fetchone()
            if existing:
                if existing["text"] != text or existing["coverage"] != coverage:
                    fail("source_conflict", "Same source bytes already registered with different metadata")
                self._complete_noncontent_chunks(sid, text)
                return {"source": sid, "idempotent": True, **self.coverage(sid)}
            self.db.execute("INSERT INTO sources VALUES (?,?,?,?,?)",
                            (sid, str(Path(file).resolve()), text, coverage, encoding))
            self.db.execute("UPDATE source_stats SET characters=? WHERE source=?", (len(text), sid))
            chunks = split_source(text, chunk_chars)
            self.db.executemany("INSERT INTO chunks(source,ordinal,start,end,title,sha) VALUES (?,?,?,?,?,?)",
                                [(sid, i, start, end, title, digest(text[start:end]))
                                 for i, (start, end, title) in enumerate(chunks, 1)])
            self.event("ingest", {"source": sid, "chunks": len(chunks), "coverage": coverage})
            self._complete_noncontent_chunks(sid, text)
            status = self.coverage(sid)
        return {"source": sid, "idempotent": False, **status}

    def coverage(self, sid):
        source = self.source_info(sid)
        rows = self.db.execute("SELECT ordinal,start,end,CASE WHEN analysis IS NULL THEN NULL ELSE 1 END FROM chunks WHERE source=? ORDER BY ordinal", (sid,)).fetchall()
        missing = [r[0] for r in rows if r[3] is None]
        contiguous = bool(rows) and rows[0][1] == 0 and rows[-1][2] == source["characters"]
        contiguous = contiguous and all(a[2] == b[1] for a, b in zip(rows, rows[1:]))
        report_path = f".story/analysis/{sid}/report.md"
        finalized = self.db.execute("SELECT 1 FROM artifacts WHERE path=?", (report_path,)).fetchone() is not None
        return {"source": sid, "source_coverage": source["coverage"], "chunks_total": len(rows),
                "analyzed": len(rows) - len(missing), "pending": len(missing), "next_chunk": missing[0] if missing else None,
                "text_coverage_contiguous": contiguous, "complete_for_imported_text": not missing and contiguous,
                "report_path": report_path if finalized else None}

    def list_sources(self, offset=0, limit=10, budget=12000):
        integer(offset, "offset")
        integer(limit, "limit", 1)
        total = self.db.execute("SELECT count(*) FROM sources").fetchone()[0]
        rows = self.db.execute("SELECT id,name FROM sources ORDER BY rowid DESC LIMIT ? OFFSET ?",
                               (min(limit, 100), offset)).fetchall()
        packet = {"offset": offset, "next_offset": offset, "total": total, "results": []}
        for row in rows:
            packet["results"].append({"name": Path(row["name"]).name, **self.coverage(row["id"])})
            packet["next_offset"] += 1
            try:
                bounded_packet(packet, budget)
            except StoryError as error:
                if error.code != "budget_exceeded" or len(packet["results"]) == 1:
                    raise
                packet["results"].pop()
                packet["next_offset"] -= 1
                break
        return bounded_packet(packet, budget)

    def next_chunks(self, sid, limit=2, budget=22000):
        integer(limit, "limit", 1)
        with self.transaction():
            source = self.source_info(sid)
            self._complete_noncontent_chunks(sid)
            rows = self.db.execute("SELECT * FROM chunks WHERE source=? AND analysis IS NULL ORDER BY ordinal LIMIT ?", (sid, min(limit, 50))).fetchall()
            packet = {"source": sid, "source_coverage": source["coverage"], "chunks": [], "pending": self.coverage(sid)["pending"]}
            for row in rows:
                item = {k: row[k] for k in ("ordinal", "start", "end", "title", "sha")}
                item["text"] = self._source_slice(sid, row["start"], row["end"])
                packet["chunks"].append(item)
                try:
                    bounded_packet(packet, budget)
                except StoryError as error:
                    if error.code != "budget_exceeded" or len(packet["chunks"]) == 1:
                        raise
                    packet["chunks"].pop()
                    break
            return bounded_packet(packet, budget)

    def source_read(self, sid, start, end, budget):
        source = self.source_info(sid)
        integer(start, "start")
        integer(end, "end", 1)
        if not start < end <= source["characters"]:
            fail("invalid_range", "Use Unicode character offsets: 0 <= start < end <= source length")
        return bounded_packet({"source": sid, "start": start, "end": end, "text": self._source_slice(sid, start, end)}, budget)

    def record(self, sid, ordinal, payload, replace=False):
        integer(ordinal, "chunk", 1)
        payload = dict(object_value(payload, "analysis"))
        if "chunk" in payload:
            embedded = integer(payload.pop("chunk"), "analysis.chunk", 1)
            if embedded != ordinal:
                fail("chunk_mismatch", "Analysis chunk must match the requested chunk",
                     expected=ordinal, actual=embedded)
        with self.transaction():
            self.source_info(sid)
            row = self.db.execute("SELECT * FROM chunks WHERE source=? AND ordinal=?", (sid, ordinal)).fetchone()
            if not row:
                fail("chunk_missing", "Unknown chunk number")
            if payload.get("chunk_sha256") != row["sha"]:
                fail("source_hash_mismatch", "Analysis must reference the exact chunk hash")
            text_field(payload.get("summary"), "analysis.summary", 1000)
            findings = payload.get("findings")
            if not isinstance(findings, list) or not 1 <= len(findings) <= 30:
                fail("invalid_input", "Analysis requires 1 to 30 evidence-backed findings")
            text = self._source_slice(sid, row["start"], row["end"])
            for finding in findings:
                object_value(finding, "finding")
                text_field(finding.get("claim"), "finding.claim", 1200)
                text_field(finding.get("kind"), "finding.kind", 80)
                if text_field(finding.get("quote"), "finding.quote", 1200) not in text:
                    fail("invalid_evidence", "Finding quote is absent from this chunk")
            encoded = dumps(payload)
            previous = json.loads(row["analysis"]) if row["analysis"] else None
            # Older records may contain a redundant, even incorrect, chunk field.
            # Ignore it for equality; identity belongs to the database key.
            if previous is not None and dumps({k: v for k, v in previous.items() if k != "chunk"}) == encoded:
                return {"recorded": ordinal, "idempotent": True, **self.coverage(sid)}
            if row["analysis"] and not replace:
                fail("analysis_exists", "Completed chunks are preserved; explicit --replace revises the analysis")
            report_path = f".story/analysis/{sid}/report.md"
            if replace and self.db.execute("SELECT 1 FROM artifacts WHERE path=?", (report_path,)).fetchone():
                fail("report_already_final", "This analysis has a final report; create a separately reviewed revision")
            self.db.execute("UPDATE chunks SET analysis=? WHERE source=? AND ordinal=?", (encoded, sid, ordinal))
            self.event("analysis", {"source": sid, "chunk": ordinal,
                                    "before": json.loads(row["analysis"]) if row["analysis"] else None, "after": payload})
            result = {"recorded": ordinal, "idempotent": False, **self.coverage(sid)}
        return result

    def findings(self, sid, offset=0, limit=10, budget=20000):
        self.source_info(sid)
        integer(offset, "offset")
        integer(limit, "limit", 1)
        rows = self.db.execute("SELECT ordinal,analysis FROM chunks WHERE source=? AND analysis IS NOT NULL ORDER BY ordinal LIMIT ? OFFSET ?",
                               (sid, min(limit, 100), offset)).fetchall()
        total = self.coverage(sid)["analyzed"]
        packet = {"source": sid, "offset": offset, "next_offset": offset, "total": total, "results": []}
        for row in rows:
            packet["results"].append({**json.loads(row[1]), "chunk": row[0]})
            packet["next_offset"] += 1
            try:
                bounded_packet(packet, budget)
            except StoryError as error:
                if error.code != "budget_exceeded" or len(packet["results"]) == 1:
                    raise
                packet["results"].pop()
                packet["next_offset"] -= 1
                break
        return bounded_packet(packet, budget)

    def report(self, sid, file):
        report = read_text(file)
        if visible_count(report) < 40:
            fail("empty_report", "Final report needs substantive content")
        with self.transaction():
            status = self.coverage(sid)
            if not status["complete_for_imported_text"]:
                fail("analysis_incomplete", "Finish all imported chunks before finalizing", coverage=status)
            content = (f"> source_sha256: {sid}\n> source_coverage: {status['source_coverage']}\n"
                       f"> analyzed_chunks: {status['analyzed']}/{status['chunks_total']}\n"
                       "> Coverage refers to imported text, not independently verified whole-book completeness.\n\n" + report)
            path = f".story/analysis/{sid}/report.md"
            old = self.db.execute("SELECT sha FROM artifacts WHERE path=?", (path,)).fetchone()
            if old and old[0] != digest(content):
                fail("report_exists", "Final report is preserved; save a separately reviewed revision")
            if not old:
                self.queue_artifact(path, content)
                self.event("report", {"source": sid, "path": path, "sha": digest(content)})
            status["report_path"] = path
        return self.delivery({"finalized": True, "report": str(self.root / path), **status})


def split_source(text, maximum):
    pattern = re.compile(r"(?m)^(?:#{1,6}[ \t]*)?(?:第[0-9０-９一二三四五六七八九十百千万零〇两]+[章节回卷][^\r\n]*|(?:番外|序章|序言|楔子|尾声|终章|后记)[^\r\n]*)\r?$")
    heads = [(m.start(), m.group().strip()[:200]) for m in pattern.finditer(text)]
    if not heads or heads[0][0] != 0:
        heads.insert(0, (0, "未命名文本 / 前言"))
    chunks = []
    for index, (start, title) in enumerate(heads):
        boundary = heads[index + 1][0] if index + 1 < len(heads) else len(text)
        while start < boundary:
            end = min(start + maximum, boundary)
            if end < boundary:
                newline = text.rfind("\n", start + maximum // 2, end)
                if newline >= 0:
                    end = newline + 1
            chunks.append((start, end, title))
            start = end
    return chunks


TEMPLATES = {
    "notes": [{"id": "hero", "kind": "character", "text": "<填写人物当前状态>",
               "tags": ["主角"], "source": "<填写用户要求或原文位置>", "critical": False,
               "status": "active", "due": None}],
    "plan": {"goal": "<填写本章推进目标>", "beats": [{"choice": "<填写人物选择>", "change": "<填写后果与变化>"}],
             "stop": "<填写停笔点>", "constraints": ["<填写用户原始硬要求>"], "length": [2200, 2800],
             "requires": ["hero"], "tags": ["主角"], "count_method": "visible_nonspace_v1", "count_title": False},
    "delta": {"book_id": "<填写context返回的book_id>", "base_revision": 0, "summary": "<填写本章结果与下章衔接>", "changes": [],
              "review": {"draft_sha256": "<填写lint返回的SHA256>", "checks": {
                  key: {"note": "<填写核对结论及理由>", "quote": "<填写正文精确摘录>"} for key in CHECKS}, "issues": []}},
    "analysis": {"chunk_sha256": "<填写next返回的sha>", "summary": "<填写本块事件与选择>",
                 "findings": [{"kind": "因果", "claim": "<填写可证实的结论>", "quote": "<填写本块精确摘录>"}]},
}


def parser():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--version", action="version", version=VERSION)
    sub = p.add_subparsers(dest="command", required=True)
    t = sub.add_parser("template", help="Print just one JSON input example")
    t.add_argument("kind", choices=TEMPLATES)
    def command(name, help_text, budget=None):
        s = sub.add_parser(name, help=help_text)
        s.add_argument("--book", required=True, help="Explicit, isolated book directory")
        s.add_argument("--integrity", choices=("strict", "local"), default="strict", help="strict hashes all exports; local verifies recent/queued files and reports unverified archives")
        if budget:
            s.add_argument("--budget-bytes", type=int, default=budget, help="Hard limit on compact JSON UTF-8 bytes")
        return s
    s = command("init", "Create state once; never overwrite an existing book")
    s.add_argument("--title", required=True)
    s.add_argument("--kind", choices=("long", "short", "analysis"), default="long")
    command("status", "Compact checkpoint and export health")
    command("migrate", "Explicit schema upgrade with a consistent rollback backup")
    command("audit", "Hash every managed export and report conflicts")
    s = command("world-save", "Save structured story state with cited evidence")
    s.add_argument("--input", required=True)
    s.add_argument("--expect", type=int, required=True)
    s = command("world-check", "Check recorded rules, knowledge and continuity", 16000)
    s.add_argument("--chapter", type=int, required=True)
    s = command("world-read", "Inspect one stored narrative record, including stale evidence for reviewed repair", 12000)
    s.add_argument("--kind", choices=sorted(set(world.FIELDS)-{"aliases"}), required=True)
    s.add_argument("--id", required=True)
    history.register_parser(sub, command)
    s = command("export", "Repair exports without replacing outside edits")
    s.add_argument("--safe-only", action="store_true",
                   help="Recover known versions and missing files while leaving conflicting paths untouched")
    for name in ("notes", "plan"):
        s = command(name, "Save cards or a chapter plan with optimistic concurrency")
        s.add_argument("--input", required=True)
        s.add_argument("--expect", type=int, required=True)
        if name == "plan":
            s.add_argument("--chapter", type=int, required=True)
    s = command("context", "Build a bounded chapter context packet", 16000)
    s.add_argument("--chapter", type=int, required=True)
    s = command("prepare", "Read-only review scaffold bound to the current book, state and draft", 16000)
    s.add_argument("--chapter", type=int, required=True)
    s.add_argument("--draft", required=True)
    s.add_argument("--reconcile", action="store_true", help="Bind the inspected outside edit for a reviewed reconciliation")
    s = command("reconcile", "Inspect an outside edit of the latest native chapter, or apply its reviewed draft", 16000)
    s.add_argument("--chapter", type=int, required=True)
    s.add_argument("--draft")
    s.add_argument("--input")
    s = command("recall", "Bounded literal substring search of cards, summaries and chapter prose", 8000)
    s.add_argument("--query", required=True)
    s = command("chapter-read", "Read a bounded excerpt of a current or immutable historical chapter", 12000)
    s.add_argument("--chapter", type=int, required=True)
    s.add_argument("--sha256")
    s.add_argument("--start", type=int, default=0)
    s.add_argument("--end", type=int)
    s = command("dependencies", "Resolve candidate evidence hashes for a reviewed chapter dependency declaration", 16000)
    s.add_argument("--chapter", type=int, required=True)
    s = command("sources", "Find saved source IDs and analysis checkpoints after a new session", 12000)
    s.add_argument("--offset", type=int, default=0)
    s.add_argument("--limit", type=int, default=10)
    for name in ("lint", "commit", "adopt"):
        s = command(name, "Check, commit, or import one last complete chapter")
        s.add_argument("--chapter", type=int, required=True)
        s.add_argument("--draft", required=True)
        if name == "commit":
            s.add_argument("--input", required=True)
            s.add_argument("--replace-last", action="store_true")
        if name == "adopt":
            s.add_argument("--summary", required=True)
            s.add_argument("--expect", type=int, required=True)
    s = command("ingest", "Snapshot source text and split without losing bonus chapters")
    s.add_argument("--file", required=True)
    s.add_argument("--coverage", choices=("complete", "partial", "unknown"), default="unknown")
    s.add_argument("--encoding", default="utf-8-sig")
    s.add_argument("--chunk-chars", type=int, default=2400)
    for name, budget in (("coverage", None), ("next", 22000), ("record", None),
                         ("findings", 20000), ("source-read", 12000), ("report", None)):
        s = command(name, "Incremental source analysis and evidence-backed checkpoints", budget)
        s.add_argument("--source", required=True)
        if name in ("next", "findings"):
            s.add_argument("--limit", type=int, default=2 if name == "next" else 10)
        if name == "findings":
            s.add_argument("--offset", type=int, default=0)
        if name == "source-read":
            s.add_argument("--start", type=int, required=True)
            s.add_argument("--end", type=int, required=True)
        if name == "record":
            s.add_argument("--chunk", type=int, required=True)
            s.add_argument("--input", required=True)
            s.add_argument("--replace", action="store_true")
        if name == "report":
            s.add_argument("--file", required=True)
    return p


def run(args):
    cmd = args.command
    if cmd == "template":
        return TEMPLATES[args.kind]
    if cmd == "init":
        return Book.create(args.book, args.title, args.kind)
    if cmd == "migrate":
        return storage.migrate(CORE, args.book)
    book = Book(args.book, integrity=getattr(args, "integrity", "strict"))
    try:
        if cmd.startswith("history-") or cmd.startswith("cache-"):
            return history.run(book, args)
        if cmd == "world-save":
            return world.save(book, read_json(args.input), args.expect)
        if cmd == "world-check":
            return bounded_packet(world.check(book, {**book.get_plan(args.chapter), "chapter": args.chapter}), args.budget_bytes)
        if cmd == "world-read":
            return book.world_read(args.kind, args.id, args.budget_bytes)
        if cmd == "audit":
            book.integrity = "strict"
            return book.export(safe_only=True)
        if cmd == "status":
            return book.status()
        if cmd == "export":
            return book.export(safe_only=args.safe_only)
        if cmd == "notes":
            return book.save_notes(read_json(args.input), args.expect)
        if cmd == "plan":
            return book.save_plan(args.chapter, read_json(args.input), args.expect)
        if cmd == "context":
            return book.context(args.chapter, args.budget_bytes)
        if cmd == "prepare":
            return book.prepare(args.chapter, args.draft, args.reconcile, args.budget_bytes)
        if cmd == "reconcile":
            return book.reconcile(args.chapter, args.draft, read_json(args.input) if args.input else None,
                                  args.budget_bytes)
        if cmd == "recall":
            return book.recall(args.query, args.budget_bytes)
        if cmd == "chapter-read":
            return book.chapter_read(args.chapter, args.sha256, args.start, args.end, args.budget_bytes)
        if cmd == "dependencies":
            return book.dependency_candidates(args.chapter, args.budget_bytes)
        if cmd == "sources":
            return book.list_sources(args.offset, args.limit, args.budget_bytes)
        if cmd == "lint":
            return book.lint(args.chapter, args.draft)
        if cmd == "commit":
            return book.commit(args.chapter, args.draft, read_json(args.input), args.replace_last)
        if cmd == "adopt":
            return book.adopt(args.chapter, args.draft, args.summary, args.expect)
        if cmd == "ingest":
            return book.ingest(args.file, args.coverage, args.encoding, args.chunk_chars)
        if cmd == "coverage":
            return book.coverage(args.source)
        if cmd == "next":
            return book.next_chunks(args.source, args.limit, args.budget_bytes)
        if cmd == "record":
            return book.record(args.source, args.chunk, read_json(args.input), args.replace)
        if cmd == "findings":
            return book.findings(args.source, args.offset, args.limit, args.budget_bytes)
        if cmd == "source-read":
            return book.source_read(args.source, args.start, args.end, args.budget_bytes)
        if cmd == "report":
            return book.report(args.source, args.file)
        raise AssertionError(cmd)
    finally:
        book.close()


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", newline="\n")
        sys.stderr.reconfigure(encoding="utf-8", newline="\n")
    args = parser().parse_args()
    try:
        result = run(args)
        print(dumps(result))
        if isinstance(result, dict) and (result.get("ok") is False or result.get("exports_complete") is False):
            return 2
        return 0
    except StoryError as error:
        print(dumps({"ok": False, "error": error.code, "message": error.message, **error.details}), file=sys.stderr)
        return 2
    except (OSError, ValueError, sqlite3.Error, LookupError) as error:
        print(dumps({"ok": False, "error": "io_or_input_error", "message": str(error)}), file=sys.stderr)
        return 2


def _load_extension(name):
    spec = importlib.util.spec_from_file_location("story_codex_" + name, Path(__file__).with_name("story_" + name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


storage, search, world, history = (_load_extension(name) for name in ("storage", "search", "world", "history"))
CORE = SimpleNamespace(**globals())
for extension in (search, world, history):
    extension.inject(CORE)
TEMPLATES["world"] = world.template()
for world_kind in world.FIELDS:
    TEMPLATES["world-" + world_kind] = world.template(world_kind)


if __name__ == "__main__":
    raise SystemExit(main())
