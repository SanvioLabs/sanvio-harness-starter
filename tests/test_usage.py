"""Run with: python3 -m unittest discover -s tests"""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HOOK = ROOT / ".claude" / "hooks" / "usage_log.py"
sys.path.insert(0, str(ROOT / ".claude" / "hooks"))
sys.path.insert(0, str(ROOT / "scripts"))
import usage_log  # noqa: E402 (the imports need those folders on the path first)
import usage_report  # noqa: E402 (same reason)


def pre(tool, **tool_input):
    return usage_log.entry("PreToolUse", {"tool_name": tool, "tool_input": tool_input})


class Entries(unittest.TestCase):
    def test_a_skill_is_logged_by_name(self):
        self.assertEqual(pre("Skill", skill="review-pr"), {"event": "skill", "name": "review-pr"})

    def test_an_agent_is_logged_by_type(self):
        self.assertEqual(pre("Agent", subagent_type="reviewer", prompt="secret plan"),
                         {"event": "agent", "name": "reviewer"})

    def test_a_guard_refusal_is_logged_by_rule_without_the_path(self):
        line = pre("Read", file_path="/home/me/project/.env")
        self.assertEqual(line, {"event": "guard_deny", "rule": "credential-file"})
        self.assertEqual(pre("Bash", command="cat .env"), {"event": "guard_deny", "rule": "credential-command"})

    def test_a_connector_ask_names_the_tool(self):
        self.assertEqual(pre("mcp__gmail__send_email", to="x@example.com"),
                         {"event": "guard_ask", "rule": "connector-write", "tool": "mcp__gmail__send_email"})

    def test_an_approved_ask_is_logged_after_it_ran(self):
        line = usage_log.entry("PostToolUse", {"tool_name": "mcp__gmail__send_email", "tool_input": {}})
        self.assertEqual(line["event"], "ask_approved")

    def test_ordinary_calls_log_nothing(self):
        self.assertIsNone(pre("Read", file_path="README.md"))
        self.assertIsNone(pre("Bash", command="git status"))
        self.assertIsNone(usage_log.entry("PostToolUse", {"tool_name": "mcp__gmail__search", "tool_input": {}}))

    def test_a_slash_command_is_logged_without_its_arguments(self):
        line = usage_log.entry("UserPromptSubmit", {"prompt": "/review-pr the payments branch"})
        self.assertEqual(line, {"event": "command", "name": "review-pr"})

    def test_an_ordinary_prompt_is_not_logged(self):
        self.assertIsNone(usage_log.entry("UserPromptSubmit", {"prompt": "fix the login bug in /src/auth"}))

    def test_sessions_are_logged(self):
        self.assertEqual(usage_log.entry("SessionStart", {"source": "startup"})["event"], "session_start")
        self.assertEqual(usage_log.entry("SessionEnd", {"reason": "exit"})["event"], "session_end")


class TheHook(unittest.TestCase):
    def run_hook(self, event, **env):
        with tempfile.TemporaryDirectory() as tmp:
            full_env = dict(os.environ, CLAUDE_PROJECT_DIR=tmp, **env)
            result = subprocess.run([sys.executable, str(HOOK)], input=json.dumps(event),
                                    capture_output=True, text=True, env=full_env, timeout=30)
            logs = list((Path(tmp) / ".harness" / "usage").glob("*.jsonl"))
            lines = [json.loads(l) for p in logs for l in p.read_text().splitlines()]
            return result, lines

    def test_it_appends_a_line_and_prints_nothing(self):
        result, lines = self.run_hook({"hook_event_name": "PreToolUse", "session_id": "s1",
                                       "tool_name": "Skill", "tool_input": {"skill": "learn"}})
        self.assertEqual((result.returncode, result.stdout), (0, ""))
        self.assertEqual(len(lines), 1)
        self.assertEqual((lines[0]["event"], lines[0]["name"], lines[0]["session"]), ("skill", "learn", "s1"))

    def test_off_means_nothing_is_written(self):
        _, lines = self.run_hook({"hook_event_name": "PreToolUse", "tool_name": "Skill",
                                  "tool_input": {"skill": "learn"}}, HARNESS_USAGE_LOG="off")
        self.assertEqual(lines, [])

    def test_bad_input_never_fails_the_call(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = subprocess.run([sys.executable, str(HOOK)], input="not json", capture_output=True,
                                    text=True, env=dict(os.environ, CLAUDE_PROJECT_DIR=tmp), timeout=30)
        self.assertEqual((result.returncode, result.stdout), (0, ""))

    def test_the_log_is_gitignored(self):
        self.assertIn(".harness/", (ROOT / ".gitignore").read_text().splitlines())

    def test_it_is_wired_on_every_event_it_handles(self):
        hooks = json.loads((ROOT / ".claude" / "settings.json").read_text())["hooks"]
        for event in ("SessionStart", "SessionEnd", "UserPromptSubmit", "PreToolUse", "PostToolUse"):
            commands = [h["command"] for block in hooks.get(event, []) for h in block["hooks"]]
            self.assertTrue(any("usage_log.py" in c for c in commands), event)


class Report(unittest.TestCase):
    LINES = [
        {"ts": "2026-10-01T09:00:00Z", "session": "a", "event": "skill", "name": "review-pr"},
        {"ts": "2026-10-02T09:00:00Z", "session": "a", "event": "skill", "name": "review-pr"},
        {"ts": "2026-10-02T09:00:00Z", "session": "b", "event": "command", "name": "learn"},
        {"ts": "2026-10-03T09:00:00Z", "session": "b", "event": "guard_deny", "rule": "credential-file"},
        {"ts": "2026-10-03T09:00:00Z", "session": "b", "event": "guard_ask", "rule": "connector-write",
         "tool": "mcp__gmail__send_email"},
        {"ts": "2026-10-03T09:00:01Z", "session": "b", "event": "ask_approved", "rule": "connector-write",
         "tool": "mcp__gmail__send_email"},
        {"ts": "2026-09-20T09:00:00Z", "session": "old", "event": "skill", "name": "whats-new"},
    ]

    def write_log(self, tmp):
        path = Path(tmp) / "me.jsonl"
        path.write_text("\n".join(json.dumps(l) for l in self.LINES) + "\nnot json\n")
        return path

    def test_it_reads_only_the_period_and_skips_bad_lines(self):
        with tempfile.TemporaryDirectory() as tmp:
            lines = usage_report.read(self.write_log(tmp), "2026-10-01")
        self.assertEqual(len(lines), 6)

    def test_the_summary_counts_and_lists_what_went_unused(self):
        with tempfile.TemporaryDirectory() as tmp:
            lines = usage_report.read(self.write_log(tmp), "2026-10-01")
        text = usage_report.report(lines, "2026-10-01", "2026-10-14", ["learn", "review-pr", "whats-new"])
        self.assertIn("Sessions: 2", text)
        self.assertIn("| `review-pr` | 2 |", text)
        self.assertIn("| `credential-file` | 1 |", text)
        self.assertIn("| `mcp__gmail__send_email` | 1 | 1 |", text)
        self.assertIn("Never used here: `whats-new`", text)

    def test_a_missing_log_says_why(self):
        result = subprocess.run([sys.executable, str(ROOT / "scripts" / "usage_report.py"),
                                 "--log", "/nonexistent/me.jsonl"], capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 1)
        self.assertIn("HARNESS_USAGE_LOG", result.stderr)


if __name__ == "__main__":
    unittest.main()
