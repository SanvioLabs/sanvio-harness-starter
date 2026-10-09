"""Run with: python3 -m unittest discover -s tests"""
import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HOOKS = ROOT / ".claude" / "hooks"
sys.path.insert(0, str(HOOKS))
import guard  # noqa: E402 (the import needs .claude/hooks/ on the path first)
import session_start  # noqa: E402


def call(tool, **tool_input):
    return guard.decide({"tool_name": tool, "tool_input": tool_input})


class Guard(unittest.TestCase):
    def assertDenied(self, verdict):
        self.assertIsNotNone(verdict)
        self.assertEqual(verdict[0], "deny")

    def test_reading_env_files_is_denied(self):
        self.assertDenied(call("Read", file_path="/repo/.env"))
        self.assertDenied(call("Read", file_path="/repo/.env.local"))
        self.assertDenied(call("Edit", file_path="config/.env.production"))

    def test_env_example_is_allowed(self):
        self.assertIsNone(call("Read", file_path="/repo/.env.example"))

    def test_keys_are_denied(self):
        self.assertDenied(call("Read", file_path="/home/me/.ssh/id_ed25519"))
        self.assertDenied(call("Read", file_path="certs/server.pem"))
        self.assertDenied(call("Read", file_path="/home/me/.aws/credentials"))

    def test_ordinary_files_are_allowed(self):
        for path in ("AGENTS.md", "examples/proposal/gates/proposal_gate.py", "docs/environment.md", "keys.py"):
            self.assertIsNone(call("Read", file_path=path), path)

    def test_shell_reads_of_credentials_are_denied(self):
        self.assertDenied(call("Bash", command="cat .env"))
        self.assertDenied(call("Bash", command="grep KEY .env.local | head"))
        self.assertDenied(call("Bash", command="gh auth token"))
        self.assertDenied(call("Bash", command="printenv"))
        self.assertDenied(call("Bash", command="aws secretsmanager get-secret-value --secret-id x"))

    def test_checking_a_credential_exists_is_allowed(self):
        for command in ("test -e .env && echo yes", "test -f .env.local", "[ -e .env ] && echo yes",
                        "[[ -s .env ]] || echo missing"):
            self.assertIsNone(call("Bash", command=command), command)

    def test_an_existence_check_does_not_cover_a_read(self):
        self.assertDenied(call("Bash", command="test -f .env && cat .env"))
        self.assertDenied(call("Bash", command="[ -e .env ] && grep KEY .env"))

    def test_ordinary_shell_is_allowed(self):
        for command in ("python3 -m unittest discover -s tests", "git status", "ls -la",
                        "cat .env.example", "python3 scripts/check_setup.py"):
            self.assertIsNone(call("Bash", command=command), command)

    def test_connector_writes_ask(self):
        for tool in ("mcp__claude_ai_Gmail__create_draft", "mcp__claude_ai_Google_Drive__share_file",
                     "mcp__claude_ai_Notion__notion-create-pages", "mcp__linear__createIssue",
                     "mcp__slack__send_message"):
            self.assertEqual(call(tool)[0], "ask", tool)

    def test_connector_reads_pass(self):
        for tool in ("mcp__claude_ai_Gmail__search_threads", "mcp__claude_ai_Google_Drive__read_file_content",
                     "mcp__claude_ai_Gmail__list_labels", "mcp__linear__getIssue"):
            self.assertIsNone(call(tool), tool)

    def test_the_hook_prints_a_deny_decision(self):
        event = json.dumps({"tool_name": "Read", "tool_input": {"file_path": ".env"}})
        out = subprocess.run([sys.executable, str(HOOKS / "guard.py")], input=event,
                             capture_output=True, text=True, check=True).stdout
        decision = json.loads(out)["hookSpecificOutput"]
        self.assertEqual(decision["hookEventName"], "PreToolUse")
        self.assertEqual(decision["permissionDecision"], "deny")

    def test_an_allowed_call_prints_nothing(self):
        event = json.dumps({"tool_name": "Read", "tool_input": {"file_path": "AGENTS.md"}})
        out = subprocess.run([sys.executable, str(HOOKS / "guard.py")], input=event,
                             capture_output=True, text=True, check=True).stdout
        self.assertEqual(out, "")

    def test_garbage_input_lets_the_call_through_and_says_so(self):
        result = subprocess.run([sys.executable, str(HOOKS / "guard.py")], input="not json",
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0)
        self.assertIn("wasn't checked", json.loads(result.stdout)["systemMessage"])


class SessionStart(unittest.TestCase):
    def test_all_passing_says_nothing(self):
        self.assertIsNone(session_start.report([("PASS", "python 3.12", None)]))

    def test_a_fail_leads_the_message(self):
        payload = session_start.report([
            ("WARN", "company: no company record yet", "Run /orientation"),
            ("FAIL", "hooks: core.hooksPath is not set", "git config core.hooksPath .githooks"),
        ])
        self.assertIn("core.hooksPath is not set", payload["systemMessage"])
        self.assertIn("+1 more", payload["systemMessage"])
        context = payload["hookSpecificOutput"]["additionalContext"]
        self.assertIn("git config core.hooksPath .githooks", context)
        self.assertEqual(payload["hookSpecificOutput"]["hookEventName"], "SessionStart")

    def test_the_hook_runs_and_prints_json_or_nothing(self):
        out = subprocess.run([sys.executable, str(HOOKS / "session_start.py")],
                             capture_output=True, text=True, check=True).stdout
        if out:
            self.assertIn("systemMessage", json.loads(out))


if __name__ == "__main__":
    unittest.main()
