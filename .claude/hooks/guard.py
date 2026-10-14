#!/usr/bin/env python3
"""Claude Code guard: runs before every tool call the agent makes.

From the Sanvio Labs harness starter, MIT: https://github.com/SanvioLabs/sanvio-harness-starter

Wired in .claude/settings.json as a PreToolUse hook. Three jobs:

1. Credentials stay unread. A Read, Edit or Write on a credential file, or a
   shell command that names one, is refused.
2. A connector that changes something asks first. Any MCP tool whose name says
   it sends, creates, edits, deletes or shares is put to the human. It goes by
   the tool's name, so a write tool with a name like run_query gets through.
3. The security-reviewer agent's shell runs audits and nothing else. It reads
   code someone else may have written, and that code can carry text meant to
   steer it. A command on the audit list runs without a prompt; any other is
   refused.

AGENTS.md says the same thing as a rule. This is the part that holds when the
agent decides otherwise. It's a backstop for honest mistakes, not a sandbox: a
command built to dodge it can.

Claude Code only. The git hook in .githooks/ is the check every tool shares.
"""
import json
import re
import shlex
import sys

CREDENTIAL = re.compile(
    r"(^|[\s/'\"=<])("
    r"\.env(\.(?!example\b|sample\b|template\b)[\w.-]+)?"  # .env, .env.local, not .env.example
    r"|[\w.-]*\.pem|[\w.-]*\.key|id_(rsa|ed25519|ecdsa)[\w.-]*"
    r"|\.aws/credentials|\.ssh/[\w.-]+|\.netrc|\.npmrc|\.pypirc"
    r")(?=$|[\s'\";|&>)])"
)
SECRET_COMMANDS = re.compile(
    r"\bsecretsmanager\s+get-secret-value\b|\bssm\s+get-parameters?\b.*--with-decryption"
    r"|\bgh\s+auth\s+token\b|\bprintenv\b|^\s*env\s*($|[|>])"
)
# `test -e .env`, `[ -f .env ]`: whether a file exists, which is the check the
# steering asks for. It's taken out before the credential match, so the rest of
# the command still has to pass: `test -f .env && cat .env` is still refused.
EXISTENCE_CHECK = re.compile(
    r"\btest\s+-[efs]\s+[^\s;|&]+|\[\[?\s+-[efs]\s+[^\s;|&\]]+\s+\]\]?"
)
WRITE_VERBS = re.compile(
    r"(^|_)(send|create|update|edit|write|delete|remove|trash|share|post|publish"
    r"|upload|move|rename|archive|invite|reply|forward|comment|label|assign|merge|close)(_|$)",
    re.I,
)

# The agent whose shell is held to AUDITS, by its name in .claude/agents/.
AUDITOR = "security-reviewer"
# One `cd <dir> &&` in front is fine; anything else that chains, pipes,
# redirects or substitutes is refused.
CD_PREFIX = re.compile(r"^\s*cd\s+[^\s;&|`$<>()]+\s*&&\s*")
SHELL_MAGIC = re.compile(r"[;&|`$<>()\n\\]")
GIT_READS = {"log", "diff", "show", "ls-files", "blame", "status", "rev-parse", "shortlog"}


def audit_allowed(command):
    """Whether a command is one the security reviewer may run: a read-only audit or git read."""
    command = CD_PREFIX.sub("", command, count=1)
    if SHELL_MAGIC.search(command):
        return False
    try:
        words = shlex.split(command)
    except ValueError:
        return False
    if not words:
        return False
    tool, args = words[0], words[1:]
    if tool == "git":
        if args[:1] == ["-C"] and len(args) > 2:
            args = args[2:]
        if not args or args[0] not in GIT_READS:
            return False
        # A patch prints file contents, history's secrets included: that's the secret scan's job.
        if args[0] == "log" and any(a in ("-p", "-u", "--patch") for a in args):
            return False
        return not any(a.startswith("--output") for a in args)
    first = args[0] if args else ""
    # Only tools that read a lock file or the code without running it. yarn and pnpm are left
    # out because a checkout can carry plugins or hooks they run, and osv-scanner reads their
    # lock files anyway, as it does Cargo, Go, Ruby and uv ones.
    if tool == "npm":
        return first == "audit" and "fix" not in args
    if tool == "pip-audit":
        # Given a requirements file or a project, pip-audit installs the packages to resolve
        # them, and an install can run their code. --disable-pip reads the file as it is; with
        # flags only, it audits the environment it's run in.
        installs = any(a in ("-r", "--requirement") or a.startswith(("--requirement=", "-r"))
                       or not a.startswith("-") for a in args)
        return "--fix" not in args and (not installs or "--disable-pip" in args)
    if tool == "osv-scanner":
        return first != "fix"
    if tool == "trivy":
        return first in ("fs", "filesystem", "config")
    if tool in ("govulncheck", "bandit", "bundle-audit", "bundler-audit"):
        return True
    if tool == "gitleaks":
        return first in ("detect", "git", "dir", "protect") and any(a.startswith("--redact") for a in args)
    return False


def decide(event):
    """(decision, reason) for one tool call, or None to let it through untouched."""
    tool = event.get("tool_name", "")
    data = event.get("tool_input") or {}

    if tool in ("Read", "Edit", "Write", "MultiEdit", "NotebookEdit"):
        path = data.get("file_path") or data.get("notebook_path") or ""
        if CREDENTIAL.search(" " + path):
            return ("deny", "{} looks like a credential file. Agents never read or write those. "
                    "Reference the secret by name and let the runtime load it.".format(path))

    if tool == "Bash":
        command = data.get("command", "")
        named = EXISTENCE_CHECK.sub(" ", command)
        if CREDENTIAL.search(" " + named) or SECRET_COMMANDS.search(command):
            return ("deny", "That command reads a credential or prints secrets. Agents never do "
                    "that. Check the secret exists without showing its value, or ask a human.")
        if event.get("agent_type") == AUDITOR:
            if audit_allowed(command):
                return ("allow", "a read-only audit on the security reviewer's list")
            return ("deny", "The security reviewer's shell runs audits only: osv-scanner, npm audit, "
                    "pip-audit (flags only, or --disable-pip), trivy fs or config, govulncheck, "
                    "bundle-audit, bandit, gitleaks with --redact, and git reads without a patch. One "
                    "command, no pipes. List anything else under Not checked for a person to run.")

    if tool.startswith("mcp__"):
        # create_draft, notion-create-pages and createIssue all read as create_...
        action = re.sub(r"(?<=[a-z])(?=[A-Z])", "_", tool.split("__")[-1]).replace("-", "_")
        if WRITE_VERBS.search(action):
            return ("ask", "{} changes something outside this repo. A human says yes to each "
                    "one.".format(tool))

    return None


def main():
    try:
        event = json.load(sys.stdin)
    except ValueError:
        # Unreadable input: let the call through and say so, rather than block every tool.
        print(json.dumps({"systemMessage": "[guard] couldn't read the tool call, so it wasn't checked"}))
        return 0
    verdict = decide(event)
    if verdict:
        decision, reason = verdict
        print(json.dumps({"hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": decision,
            "permissionDecisionReason": reason,
        }}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
