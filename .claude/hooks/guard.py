#!/usr/bin/env python3
"""Claude Code guard: runs before every tool call the agent makes.

Wired in .claude/settings.json as a PreToolUse hook. Two jobs:

1. Credentials stay unread. A Read, Edit or Write on a credential file, or a
   shell command that names one, is refused.
2. A connector that changes something asks first. Any MCP tool whose name says
   it sends, creates, edits, deletes or shares is put to the human. It goes by
   the tool's name, so a write tool with a name like run_query gets through.

AGENTS.md says the same thing as a rule. This is the part that holds when the
agent decides otherwise. It's a backstop for honest mistakes, not a sandbox: a
command built to dodge it can.

Claude Code only. The git hook in .githooks/ is the check every tool shares.
"""
import json
import re
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
WRITE_VERBS = re.compile(
    r"(^|_)(send|create|update|edit|write|delete|remove|trash|share|post|publish"
    r"|upload|move|rename|archive|invite|reply|forward|comment|label|assign|merge|close)(_|$)",
    re.I,
)


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
        if CREDENTIAL.search(" " + command) or SECRET_COMMANDS.search(command):
            return ("deny", "That command reads a credential or prints secrets. Agents never do "
                    "that. Check the secret exists without showing its value, or ask a human.")

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
