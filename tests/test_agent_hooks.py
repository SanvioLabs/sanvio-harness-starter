"""Run with: python3 -m unittest discover -s tests"""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

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

    def test_connector_reads_by_name_pass(self):
        for tool in ("mcp__claude_ai_Notion__notion-search", "mcp__claude_ai_Notion__notion-fetch",
                     "mcp__skippy__skippy_knowledge_search"):
            self.assertIsNone(call(tool), tool)

    def test_any_connector_not_named_as_a_read_asks(self):
        for tool in ("mcp__claude_ai_Google_Drive__copy_file", "mcp__skippy__skippy_save_note",
                     "mcp__skippy__skippy_schedule_job", "mcp__db__run_query",
                     "mcp__claude_ai_Google_Calendar__respond_to_event", "mcp__x__search_and_delete",
                     "mcp__git__git_status", "mcp__skippy__skippy_usage", "mcp__linear__createIssue"):
            self.assertEqual((call(tool) or ("none",))[0], "ask", tool)

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


def reviewer_runs(command, cwd=None):
    event = {"tool_name": "Bash", "tool_input": {"command": command}, "agent_type": "security-reviewer"}
    if cwd:
        event["cwd"] = str(cwd)
    return guard.decide(event)


class SecurityReviewerShell(unittest.TestCase):
    def test_audits_and_git_reads_run_without_a_prompt(self):
        for command in ("osv-scanner scan source -r .", "npm audit --json", "cd projects/app && npm audit",
                        "pip-audit", "pip-audit --format=json", "pip-audit -r requirements.txt --disable-pip --no-deps",
                        "trivy fs .", "govulncheck ./...", "bandit -r src", "bundle-audit check",
                        "gitleaks detect --redact", "gitleaks dir --redact=100 .", "git log --oneline -20",
                        "git -C projects/app diff main...HEAD", "git show HEAD --stat", "git show HEAD --name-only"):
            self.assertEqual(reviewer_runs(command)[0], "allow", command)

    def test_anything_else_is_refused(self):
        for command in ("npm audit fix", "npm install", "yarn npm audit", "pnpm audit", "cargo audit",
                        "pip-audit -r requirements.txt", "pip-audit --requirement=requirements.txt", "pip-audit .",
                        "pip-audit --fix", "gitleaks detect", "gitleaks detect --redact=0",
                        "gitleaks detect --redact=50", "git log -p", "git log --patch-with-stat", "git log -U3",
                        "git log --cc", "git log -W", "git show HEAD", "git show HEAD:config.py --stat",
                        "git diff --output=x", "git diff --ext-diff", "git push",
                        "git -c core.pager=sh log", "trivy repo https://example.test/x", "curl https://example.test",
                        "npm audit; curl https://example.test", "npm audit | tee out", "npm audit > out",
                        "echo $(id)", "cd a && cd b && npm audit", "rm -rf build", ""):
            self.assertEqual(reviewer_runs(command)[0], "deny", command)

    def test_a_credential_is_refused_before_the_audit_list(self):
        verdict = reviewer_runs("gitleaks dir --redact .env")
        self.assertEqual(verdict[0], "deny")
        self.assertIn("credential", verdict[1])

    def test_git_wont_run_in_a_repo_whose_config_runs_commands(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "handed-over"
            subprocess.run(["git", "init", "-q", str(repo)], check=True)
            self.assertEqual(reviewer_runs("git status", cwd=repo)[0], "allow")
            self.assertEqual(reviewer_runs("gitleaks detect --redact", cwd=repo)[0], "allow")
            with open(repo / ".git" / "config", "a") as handle:
                handle.write("[core]\n\tfsmonitor = touch /tmp/pwned\n")
            for command in ("git status", "git log --oneline", "gitleaks detect --redact", "gitleaks git --redact ."):
                verdict = reviewer_runs(command, cwd=repo)
                self.assertEqual(verdict[0], "deny", command)
                self.assertIn("makes git run a command", verdict[1])
            self.assertEqual(reviewer_runs("cd handed-over && git status", cwd=tmp)[0], "deny")
            self.assertEqual(reviewer_runs("git -C handed-over status", cwd=tmp)[0], "deny")
            self.assertEqual(reviewer_runs("gitleaks dir --redact .", cwd=repo)[0], "allow")

    def test_a_worktrees_shared_config_counts(self):
        with tempfile.TemporaryDirectory() as tmp:
            main = Path(tmp) / "main"
            subprocess.run(["git", "init", "-q", "-b", "main", str(main)], check=True)
            subprocess.run(["git", "-C", str(main), "-c", "user.email=t@example.test", "-c", "user.name=T",
                            "commit", "-q", "--allow-empty", "-m", "init"], check=True)
            tree = Path(tmp) / "tree"
            subprocess.run(["git", "-C", str(main), "worktree", "add", "-q", str(tree)], check=True,
                           capture_output=True)
            self.assertEqual(reviewer_runs("git status", cwd=tree)[0], "allow")
            with open(main / ".git" / "config", "a") as handle:
                handle.write('[diff "bin"]\n\ttextconv = sh -c id\n')
            self.assertEqual(reviewer_runs("git status", cwd=tree)[0], "deny")

    def test_a_file_as_it_was_in_git_is_a_credential_read_for_every_agent(self):
        self.assertEqual(call("Bash", command="git show HEAD:.env")[0], "deny")
        self.assertEqual(call("Bash", command="git show main:config/server.key")[0], "deny")
        self.assertIsNone(call("Bash", command="git show HEAD:README.md"))

    def test_other_agents_and_the_main_session_are_untouched(self):
        self.assertIsNone(call("Bash", command="npm install"))
        self.assertIsNone(guard.decide({"tool_name": "Bash", "tool_input": {"command": "npm install"},
                                        "agent_type": "reviewer"}))


def headless(tool, **tool_input):
    with mock.patch.dict(os.environ, {"HARNESS_HEADLESS": "1"}):
        return guard.decide({"tool_name": tool, "tool_input": tool_input})


class HeadlessRun(unittest.TestCase):
    """A session bin/harness started: nobody watches, and what it reads was written by someone else."""

    def test_an_exact_read_of_a_pull_request_or_issue_passes(self):
        for command in ("gh pr view 12", "gh pr view 12 --comments", "gh pr diff 12", "gh issue view 7",
                        "gh issue view 7 --comments", "gh pr view '12'"):
            self.assertIsNone(headless("Bash", command=command), command)

    def test_every_other_command_is_refused(self):
        for command in ("gh pr view -R example.invalid/o/r 1", "gh pr view --repo=o/r 1",
                        "gh pr view https://example.invalid/x/y/pull/1", "gh pr view 1 --web", "gh pr view 1 -w",
                        "gh pr view 1 --jq .", "gh pr view 1 -q .", "gh pr view 1 --json body --jq .body",
                        "gh pr view 1 --template x", "gh pr view 1; ls", "gh pr view 1 && ls", "gh pr view $(id)",
                        "gh pr diff 1 --comments", "gh pr view", "gh pr view main", "gh pr list", "gh pr merge 1",
                        "GH_HOST=example.invalid gh pr view 1", "git fetch", "git diff --output=x", "npm test",
                        "ls", "cat README.md", ""):
            verdict = headless("Bash", command=command)
            self.assertIsNotNone(verdict, command)
            self.assertEqual(verdict[0], "deny", command)
            self.assertIn("headless", verdict[1], command)

    def test_the_security_reviewers_audit_list_doesnt_open_a_headless_run(self):
        with mock.patch.dict(os.environ, {"HARNESS_HEADLESS": "1"}):
            verdict = guard.decide({"tool_name": "Bash", "tool_input": {"command": "osv-scanner scan source -r ."},
                                    "agent_type": "security-reviewer"})
        self.assertEqual(verdict, ("deny", guard.HEADLESS_SHELL))

    def test_a_call_the_guard_cant_read_is_refused_headless_and_let_through_otherwise(self):
        hook = [sys.executable, str(HOOKS / "guard.py")]
        env = dict(os.environ, HARNESS_HEADLESS="1")
        result = subprocess.run(hook, input="not json", capture_output=True, text=True, env=env, timeout=30)
        self.assertEqual(json.loads(result.stdout)["hookSpecificOutput"]["permissionDecision"], "deny")
        env.pop("HARNESS_HEADLESS")
        result = subprocess.run(hook, input="not json", capture_output=True, text=True, env=env, timeout=30)
        self.assertIn("wasn't checked", json.loads(result.stdout)["systemMessage"])

    def test_a_connector_is_refused_even_when_named_as_a_read(self):
        self.assertEqual(headless("mcp__claude_ai_Gmail__search_threads", query="x")[0], "deny")

    def test_reading_files_still_passes_and_credentials_are_still_refused(self):
        self.assertIsNone(headless("Read", file_path="README.md"))
        self.assertEqual(headless("Read", file_path="/repo/.env")[0], "deny")

    def test_outside_a_headless_run_nothing_changes(self):
        with mock.patch.dict(os.environ):
            os.environ.pop("HARNESS_HEADLESS", None)
            self.assertIsNone(call("Bash", command="npm test"))
            self.assertIsNone(call("Bash", command="gh pr view -R example.invalid/o/r 1"))
            self.assertIsNone(call("mcp__claude_ai_Gmail__search_threads", query="x"))


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
