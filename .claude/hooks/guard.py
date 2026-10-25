#!/usr/bin/env python3
"""Claude Code guard: runs before every tool call the agent makes.

From the Sanvio Labs harness starter, MIT: https://github.com/SanvioLabs/sanvio-harness-starter

Wired in .claude/settings.json as a PreToolUse hook. Three jobs:

1. Credentials stay unread. A Read, Edit or Write on a credential file, or a
   shell command that names one, is refused.
2. A connector call that isn't a plain read asks first. An MCP tool runs
   unasked only when its name says it gets, lists, searches, reads, finds,
   queries, fetches or views, and nothing in it says it sends, creates, edits,
   deletes, shares, runs or executes. Any other is put to the human, so a tool
   nobody has seen yet asks rather than slips through. It goes by the name, so
   a read tool with an odd name (git_status) asks too.
3. The security-reviewer agent's shell runs audits and nothing else. It reads
   code someone else may have written, and that code can carry text meant to
   steer it. A command on the audit list runs without a prompt; any other is
   refused.
4. A run bin/harness started (HARNESS_HEADLESS=1) reads a pull request or an
   issue by number and nothing else. Nobody is watching it, and what it reads
   was written by someone else. Its shell runs only `gh pr view <n>`,
   `gh pr diff <n>` and `gh issue view <n>`, with `--comments` on a view, and
   no connector runs at all.

AGENTS.md says the same thing as a rule. This is the part that holds when the
agent decides otherwise. It's a backstop for honest mistakes, not a sandbox: a
command built to dodge it can.

Claude Code only. The git hook in .githooks/ is the check every tool shares.
"""
import json
import os
import re
import shlex
import sys

CREDENTIAL = re.compile(
    r"(^|[\s/'\"=<:])("  # : as well, for git show HEAD:.env
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
    r"|upload|move|rename|archive|invite|reply|forward|comment|label|assign|merge|close"
    r"|run|execute)(_|$)",
    re.I,
)
READ_VERBS = re.compile(r"(^|_)(get|list|search|read|find|query|fetch|view)(_|$)", re.I)

# The agent whose shell is held to AUDITS, by its name in .claude/agents/.
AUDITOR = "security-reviewer"
# One `cd <dir> &&` in front is fine; anything else that chains, pipes,
# redirects or substitutes is refused.
CD_PREFIX = re.compile(r"^\s*cd\s+[^\s;&|`$<>()]+\s*&&\s*")
SHELL_MAGIC = re.compile(r"[;&|`$<>()\n\\]")
GIT_READS = {"log", "diff", "show", "ls-files", "blame", "status", "rev-parse", "shortlog"}
# Flags that make log or show print file contents, history's secrets included. Finding those is the
# secret scan's job, and it redacts what it finds.
PATCH_FLAGS = {"-p", "-u", "--patch", "--patch-with-stat", "--patch-with-raw", "--cc", "-c", "-m", "-W",
               "--function-context", "--full-diff", "--textconv", "--ext-diff"}
PATCH_PREFIXES = ("-U", "--unified", "--word-diff", "--color-words", "--output")
NO_PATCH = {"--stat", "--shortstat", "--numstat", "--name-only", "--name-status", "--no-patch", "-s", "--summary"}
# What a repo's own git config can make a read run: a filesystem monitor, a pager, an external or
# textconv diff, an ssh command, or another file pulled in. A clone never copies config, but a repo
# handed over as an archive brings its .git/config, and git reads it.
RISKY_GIT_CONFIG = re.compile(
    r"^\s*(fsmonitor|external|textconv|pager|sshcommand|askpass|command)\s*="
    r"|^\s*\[\s*(include|includeif|filter|pager)\b", re.I | re.M)


def git_dir_configs(start):
    """The config files git reads for the repo holding `start`, nearest repo first."""
    here = os.path.abspath(start)
    while True:
        dot = os.path.join(here, ".git")
        if os.path.isdir(dot):
            gitdir = dot
            break
        if os.path.isfile(dot):
            try:
                with open(dot) as handle:
                    line = handle.read().strip()
            except OSError:
                return []
            if not line.startswith("gitdir:"):
                return []
            gitdir = os.path.join(here, line[len("gitdir:"):].strip())
            break
        parent = os.path.dirname(here)
        if parent == here:
            return []
        here = parent
    found = [os.path.join(gitdir, "config"), os.path.join(gitdir, "config.worktree")]
    try:
        with open(os.path.join(gitdir, "commondir")) as handle:
            found.append(os.path.join(gitdir, handle.read().strip(), "config"))
    except OSError:
        pass
    return [f for f in found if os.path.isfile(f)]


def risky_git_config(start):
    """The config file that could make a git read run a command, or None."""
    for path in git_dir_configs(start):
        try:
            with open(path, errors="replace") as handle:
                if RISKY_GIT_CONFIG.search(handle.read()):
                    return path
        except OSError:
            return path
    return None


def git_read_allowed(args):
    """Whether git with these arguments, after any -C, is a read that prints no old file contents."""
    if not args or args[0] not in GIT_READS:
        return False
    sub, rest = args[0], args[1:]
    if any(a in PATCH_FLAGS or a.startswith(PATCH_PREFIXES) for a in rest):
        return False
    if sub == "show":
        # show prints a patch unless told not to, and rev:path prints a file as it was.
        return any(a in NO_PATCH for a in rest) and not any(":" in a for a in rest if not a.startswith("-"))
    return True


def audit_refusal(command, cwd=None):
    """Why the security reviewer may not run this command, or None when it may."""
    listed = ("The security reviewer's shell runs audits only: osv-scanner, npm audit, pip-audit (flags "
              "only, or --disable-pip), trivy fs or config, govulncheck, bundle-audit, bandit, gitleaks "
              "with a bare --redact, and git reads that print no old file contents (show needs --stat or "
              "--name-only). One command, no pipes. List anything else under Not checked for a person "
              "to run.")
    where = cwd or os.getcwd()
    moved = CD_PREFIX.match(command)
    if moved:
        where = os.path.join(where, os.path.expanduser(moved.group(0).strip()[2:].rstrip("&").strip()))
    command = CD_PREFIX.sub("", command, count=1)
    if SHELL_MAGIC.search(command):
        return listed
    try:
        words = shlex.split(command)
    except ValueError:
        return listed
    if not words:
        return listed
    tool, args = words[0], words[1:]
    first = args[0] if args else ""
    uses_git = False
    if tool == "git":
        if args[:1] == ["-C"] and len(args) > 2:
            where = os.path.join(where, os.path.expanduser(args[1]))
            args = args[2:]
        if not git_read_allowed(args):
            return listed
        uses_git = True
    elif tool == "gitleaks":
        # A bare --redact is 100%. --redact=N shows the rest of each secret.
        if first not in ("detect", "git", "dir", "protect") or not any(a in ("--redact", "--redact=100") for a in args):
            return listed
        if first != "dir" and "--no-git" not in args:
            uses_git = True
            for flag in ("--source", "-s"):
                if flag in args and args.index(flag) + 1 < len(args):
                    where = os.path.join(where, os.path.expanduser(args[args.index(flag) + 1]))
            paths = [a for a in args[1:] if not a.startswith("-")]
            if first == "git" and paths:
                where = os.path.join(where, os.path.expanduser(paths[-1]))
    elif not audit_tool_allowed(tool, args):
        return listed
    if uses_git:
        risky = risky_git_config(where)
        if risky:
            return ("{} sets something that makes git run a command on a read (a pager, an external "
                    "diff, a filesystem monitor, an include). Don't run git here; list it under Not "
                    "checked and say why.".format(risky))
    return None


def audit_tool_allowed(tool, args):
    """Whether a non-git audit tool with these arguments reads without installing or running the code."""
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
    return False


HEADLESS_READS = {("pr", "view"), ("pr", "diff"), ("issue", "view")}


def headless_refusal(command):
    """Why a headless run may not run this command, or None when it's an exact read by number.

    Only the issue or pull request number may follow, and --comments on a view: -R, a URL, --web,
    --jq and --template each let the command choose a host, open a browser or read the environment.
    """
    listed = ("A headless run's shell reads a pull request or issue by number and nothing else: "
              "gh pr view <n>, gh pr diff <n> or gh issue view <n>, with --comments on a view. "
              "Say in the report that you couldn't run anything else.")
    if SHELL_MAGIC.search(command):
        return listed
    try:
        words = shlex.split(command)
    except ValueError:
        return listed
    if len(words) < 4 or words[0] != "gh" or tuple(words[1:3]) not in HEADLESS_READS:
        return listed
    rest = words[4:]
    if not re.fullmatch(r"[0-9]+", words[3]) or rest not in ([], ["--comments"]):
        return listed
    if rest and words[2] != "view":
        return listed
    return None


def decide(event):
    """(decision, reason) for one tool call, or None to let it through untouched."""
    tool = event.get("tool_name", "")
    data = event.get("tool_input") or {}
    headless = os.environ.get("HARNESS_HEADLESS") == "1"

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
            why = audit_refusal(command, event.get("cwd"))
            if why:
                return ("deny", why)
            return ("allow", "a read-only audit on the security reviewer's list")
        if headless:
            why = headless_refusal(command)
            if why:
                return ("deny", why)

    if tool.startswith("mcp__"):
        if headless:
            return ("deny", "A headless run uses no connector: nobody is there to say what it may "
                    "read or send. Run it in a session instead.")
        # create_draft, notion-create-pages and createIssue all read as create_...
        action = re.sub(r"(?<=[a-z])(?=[A-Z])", "_", tool.split("__")[-1]).replace("-", "_")
        if WRITE_VERBS.search(action) or not READ_VERBS.search(action):
            return ("ask", "{} isn't named as a plain read, so it may change something outside "
                    "this repo. A human says yes to each one.".format(tool))

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
