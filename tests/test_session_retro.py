"""Run with: python3 -m unittest discover -s tests"""
import io
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
HOOK = ROOT / ".claude" / "hooks" / "session_retro.py"
sys.path.insert(0, str(ROOT / ".claude" / "hooks"))
sys.path.insert(0, str(ROOT / "scripts"))
import loop  # noqa: E402 (the imports need those folders on the path first)
import session_retro  # noqa: E402 (same reason)

SESSION = "11111111-2222-3333-4444-555555555555"


def said(uuid, text, **extra):
    return dict({"type": "user", "uuid": uuid, "timestamp": "2026-10-31T10:00:00.000Z",
                 "message": {"role": "user", "content": text}}, **extra)


def edit(uuid, path):
    return {"type": "assistant", "uuid": uuid, "timestamp": "2026-10-31T10:00:01.000Z",
            "message": {"role": "assistant", "content": [
                {"type": "tool_use", "id": "t-" + uuid, "name": "Edit", "input": {"file_path": path}}]}}


def read(uuid, path):
    return {"type": "assistant", "uuid": uuid, "timestamp": "2026-10-31T10:00:02.000Z",
            "message": {"role": "assistant", "content": [
                {"type": "tool_use", "id": "t-" + uuid, "name": "Read", "input": {"file_path": path}}]}}


def tool_output(uuid, text):
    return {"type": "user", "uuid": uuid, "message": {"role": "user", "content": [
        {"type": "tool_result", "tool_use_id": "t1", "content": text}]}}


CORRECTED = [said("r1", "Add the setting."), read("r2", "/work/AGENTS.md"), said("r3", "That's wrong, it goes in loop.json")]
QUIET = [said("r1", "Add the setting."), edit("r2", "/work/a.py"), said("r3", "Thanks, looks good")]


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "harness"
        self.root.mkdir()
        self.folder = self.root / "local-data" / "retro"

    def log(self, records, name=SESSION, where=None):
        path = (where or Path(self.tmp.name)) / (name + ".jsonl")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("".join(json.dumps(one) + "\n" for one in records))
        return path

    def event(self, path, hook="SessionEnd", session=SESSION):
        return {"hook_event_name": hook, "session_id": session, "transcript_path": str(path)}

    def run_hook(self, stdin, **env):
        full = {k: v for k, v in os.environ.items() if k not in ("HARNESS_RETRO", "HARNESS_HEADLESS")}
        full.update(env, CLAUDE_PROJECT_DIR=str(self.root))
        return subprocess.run([sys.executable, str(HOOK)], input=stdin, capture_output=True, text=True,
                              env=full, timeout=30)

    def kept(self):
        return sorted(path.name for path in self.folder.glob("*.jsonl")) if self.folder.is_dir() else []


class Capture(Base):
    def test_off_by_default_nothing_is_copied_or_listed(self):
        result = self.run_hook(json.dumps(self.event(self.log(CORRECTED))))
        self.assertEqual((result.returncode, result.stdout, result.stderr), (0, "", ""))
        self.assertFalse(self.folder.exists())

    def test_a_correction_from_the_person_is_copied_and_listed(self):
        result = self.run_hook(json.dumps(self.event(self.log(CORRECTED))), HARNESS_RETRO="on")
        self.assertEqual((result.returncode, result.stdout, result.stderr), (0, "", ""))
        self.assertEqual(self.kept(), [SESSION + ".jsonl"])
        self.assertEqual(session_retro.listed(self.folder), [SESSION])

    def test_each_phrase_counts_and_no_comma_opens_one(self):
        for text in ("not what I asked for", "Please don't do that again", "learn from that",
                     "no, the other file", "That’s wrong"):
            path = self.log([said("r1", text)])
            self.assertTrue(session_retro.signals(path), text)

    def test_a_file_edited_three_times_counts(self):
        path = self.log([edit("e1", "/w/a.py"), edit("e2", "/w/a.py"), edit("e3", "/w/a.py")])
        found = session_retro.signals(path)
        self.assertEqual(found, [{"kind": "edited", "uuid": "e3", "file": "/w/a.py", "count": 3}])
        with mock.patch.dict(os.environ, {"HARNESS_RETRO": "on"}):
            self.assertEqual(session_retro.capture(self.root, self.event(path)), SESSION)

    def test_no_signal_is_not_copied(self):
        with mock.patch.dict(os.environ, {"HARNESS_RETRO": "on"}):
            self.assertIsNone(session_retro.capture(self.root, self.event(self.log(QUIET))))
        self.assertEqual(self.kept(), [])

    def test_text_the_person_did_not_write_is_not_a_signal(self):
        path = self.log([tool_output("t1", "no, file not found"),
                         said("s1", "no, summary of the earlier part", isCompactSummary=True),
                         said("s2", "that's wrong", isMeta=True),
                         said("s3", "that's wrong", isSidechain=True),
                         said("s4", "<command-name>/clear</command-name> no, that's wrong"),
                         edit("e1", "/w/a.py"), edit("e2", "/w/a.py"),
                         dict(edit("e3", "/w/a.py"), isSidechain=True)])
        self.assertEqual(session_retro.signals(path), [])

    def test_precompact_then_session_end_lists_it_once_and_keeps_the_longer_log(self):
        path = self.log(CORRECTED)
        with mock.patch.dict(os.environ, {"HARNESS_RETRO": "on"}):
            session_retro.capture(self.root, self.event(path, "PreCompact"))
            self.log(CORRECTED + [said("r4", "Done now")])
            session_retro.capture(self.root, self.event(path, "SessionEnd"))
        self.assertEqual(session_retro.listed(self.folder), [SESSION])
        self.assertIn('"r4"', (self.folder / (SESSION + ".jsonl")).read_text())

    def test_a_run_bin_harness_started_is_not_copied(self):
        with mock.patch.dict(os.environ, {"HARNESS_RETRO": "on", "HARNESS_HEADLESS": "1"}):
            self.assertIsNone(session_retro.capture(self.root, self.event(self.log(CORRECTED))))

    def test_a_hook_run_that_fails_leaves_the_session_alone(self):
        for stdin in ("not json", json.dumps({"hook_event_name": "SessionEnd", "session_id": "../x",
                                              "transcript_path": "/nowhere"})):
            result = self.run_hook(stdin, HARNESS_RETRO="on")
            self.assertEqual((result.returncode, result.stdout, result.stderr), (0, "", ""))
        self.assertFalse(self.folder.exists())

    def test_a_copy_older_than_30_days_is_deleted_on_the_next_run_even_when_off(self):
        with mock.patch.dict(os.environ, {"HARNESS_RETRO": "on"}):
            session_retro.capture(self.root, self.event(self.log(CORRECTED)))
        old = time.time() - 31 * 86400
        os.utime(self.folder / (SESSION + ".jsonl"), (old, old))
        result = self.run_hook(json.dumps(self.event(self.log(QUIET, name="other"), session="other")))
        self.assertEqual(result.returncode, 0)
        self.assertEqual(self.kept(), [])
        self.assertEqual(session_retro.listed(self.folder), [])


class PromptAndRecord(Base):
    def setUp(self):
        super().setUp()
        self.transcripts = Path(self.tmp.name) / "projects"
        patcher = mock.patch.object(loop, "TRANSCRIPTS", self.transcripts)
        patcher.start()
        self.addCleanup(patcher.stop)

    def keep(self, records=CORRECTED):
        with mock.patch.dict(os.environ, {"HARNESS_RETRO": "on"}):
            return session_retro.capture(self.root, self.event(self.log(records)))

    def test_prompt_takes_the_oldest_kept_session_and_carries_what_the_person_corrected(self):
        self.keep()
        out = io.StringIO()
        self.assertEqual(session_retro.prompt(self.root, out=out), 0)
        self.assertIn("Session {} (kept), 1 correction signal".format(SESSION), out.getvalue())
        text = (self.folder / (SESSION + ".prompt.md")).read_text()
        self.assertIn('- r3 the person wrote: "That\'s wrong, it goes in loop.json"', text)
        self.assertIn("r2", text)  # the Read, from the loop's digest
        self.assertIn("FINDING: CAUSE | record id or none", text)

    def test_prompt_takes_the_first_kept_of_two(self):
        self.keep()
        with mock.patch.dict(os.environ, {"HARNESS_RETRO": "on"}):
            session_retro.capture(self.root, self.event(self.log(CORRECTED, name="second"), session="second"))
        self.assertEqual(session_retro.listed(self.folder), [SESSION, "second"])
        out = io.StringIO()
        session_retro.prompt(self.root, out=out)
        self.assertIn("Session {} (kept)".format(SESSION), out.getvalue())
        self.assertIn("waiting: 2", out.getvalue())

    def test_drop_deletes_a_kept_session_and_writes_nothing(self):
        self.keep()
        self.assertEqual(session_retro.drop(self.root, SESSION, out=io.StringIO()), 0)
        self.assertEqual(self.kept(), [])
        self.assertEqual(session_retro.listed(self.folder), [])
        self.assertFalse((self.root / ".loop" / "lessons.md").exists())
        self.assertEqual(session_retro.drop(self.root, SESSION, out=io.StringIO()), 1)

    def test_record_appends_a_session_entry_and_deletes_the_copy(self):
        self.keep()
        reply = ("FINDING: UNLOADED | r3 | this repo | steering | loop.json | The setting's home was never read.\n"
                 "FINDING: IGNORED | r-not-in-the-log | this repo | steering | AGENTS.md | Made up.\n"
                 "FINDING: GUESSED | r3 | this repo | steering | none | Not a cause.\n")
        out = io.StringIO()
        self.assertEqual(session_retro.record(self.root, SESSION, reply, out=out), 0)
        entry = (self.root / ".loop" / "lessons.md").read_text()
        self.assertIn("session {}: 1 signal".format(SESSION), entry)
        self.assertIn("- UNLOADED (this repo, steering) loop.json: The setting's home was never read. [record r3]", entry)
        self.assertNotIn("Made up", entry)
        self.assertNotIn("Not a cause", entry)
        self.assertIn("dropped a finding: its record isn't in the session logs", out.getvalue())
        self.assertIn("dropped a finding: unknown cause or scope", out.getvalue())
        self.assertEqual(list(self.folder.iterdir()), [self.folder / "candidates.txt"])
        self.assertEqual(session_retro.listed(self.folder), [])

    def test_an_ignored_finding_the_log_contradicts_is_marked_unverified(self):
        self.keep()
        reply = "FINDING: IGNORED | r3 | this repo | steering | /work/README.md | It was never read.\n"
        session_retro.record(self.root, SESSION, reply, out=io.StringIO())
        self.assertIn("(unverified)", (self.root / ".loop" / "lessons.md").read_text())

    def test_with_none_kept_prompt_reads_this_session(self):
        folder = self.transcripts / re.sub(r"[^A-Za-z0-9-]", "-", os.path.abspath(str(self.root)))
        self.log(QUIET, name="older", where=folder)
        os.utime(folder / "older.jsonl", (1, 1))
        self.log(CORRECTED, name="newest", where=folder)
        out = io.StringIO()
        self.assertEqual(session_retro.prompt(self.root, out=out), 0)
        self.assertIn("Session newest (this session)", out.getvalue())
        session_retro.record(self.root, "newest", "", out=io.StringIO())
        self.assertIn("session newest: 1 signal", (self.root / ".loop" / "lessons.md").read_text())
        self.assertTrue((folder / "newest.jsonl").exists())  # Claude Code's own log is never deleted

    def test_no_session_to_read_says_so(self):
        out = io.StringIO()
        self.assertEqual(session_retro.prompt(self.root, out=out), 1)
        self.assertEqual(session_retro.record(self.root, "../etc", "", out=io.StringIO()), 1)
        self.assertFalse((self.root / ".loop" / "lessons.md").exists())


if __name__ == "__main__":
    unittest.main()
