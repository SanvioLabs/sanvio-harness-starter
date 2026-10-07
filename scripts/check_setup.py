#!/usr/bin/env python3
"""Setup check: is this clone wired up the way the harness assumes?

Usage:
    python3 scripts/check_setup.py

Read-only. Prints one PASS, WARN or FAIL line per check, with the fix on the
line below. Exits 1 when anything FAILs, so you can run it in a script. A WARN
doesn't fail: it's something to decide, not something broken.
"""
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STARTER = re.compile(r"[/:]SanvioLabs/sanvio-harness-starter(\.git)?/?$", re.I)


def git(root, *args):
    """A git command's output, or None when it fails (unset key, no remote)."""
    try:
        result = subprocess.run(["git", "-C", str(root)] + list(args),
                                capture_output=True, text=True)
    except OSError:
        return None
    return result.stdout.strip() if result.returncode == 0 else None


def check_python(version=None):
    version = version or sys.version_info[:3]
    shown = ".".join(str(n) for n in version)
    if tuple(version[:2]) >= (3, 9):
        return ("PASS", "python " + shown, None)
    return ("FAIL", "python " + shown + " is older than 3.9",
            "Install Python 3.9 or newer. No packages are needed.")


def check_hooks(root):
    path = git(root, "config", "core.hooksPath")
    if path == ".githooks":
        return ("PASS", "hooks: core.hooksPath is .githooks", None)
    fix = "git config core.hooksPath .githooks"
    if not path:
        return ("FAIL", "hooks: core.hooksPath is not set, so the pre-commit hook never runs",
                fix + "   (every check in the hook silently does nothing until you do)")
    return ("FAIL", "hooks: core.hooksPath is {}, not .githooks".format(path),
            fix + "   (hooks in {} stop running, so decide first)".format(path))


def check_links(root):
    """CLAUDE.md, .claude/skills and the Kiro steering link all lead back to the real files."""
    problems = []
    claude = root / "CLAUDE.md"
    if not claude.is_file() or "@AGENTS.md" not in claude.read_text():
        problems.append("CLAUDE.md doesn't import @AGENTS.md")
    skills = root / ".claude" / "skills"
    if not skills.is_dir() or skills.resolve() != (root / "skills").resolve():
        problems.append(".claude/skills isn't a link to skills/")
    steering = root / ".kiro" / "steering" / "project.md"
    if not steering.is_file() or steering.resolve() != (root / "AGENTS.md").resolve():
        problems.append(".kiro/steering/project.md isn't a link to AGENTS.md")
    if not problems:
        return ("PASS", "links: CLAUDE.md, .claude/skills and .kiro/steering lead to the real files", None)
    return ("FAIL", "links: " + "; ".join(problems),
            "Re-clone with symlinks on (Windows: git clone -c core.symlinks=true, "
            "with Developer Mode on). Without them Claude Code won't find the skills.")


def safe_url(url):
    """The remote URL with any user:token@ part removed, so a credential never gets printed."""
    return re.sub(r"^([a-z+]+://)[^/@]+@", r"\1", url)


def check_remote(root):
    url = git(root, "remote", "get-url", "origin")
    if not url:
        return ("PASS", "remote: no origin, so nothing gets pushed anywhere yet", None)
    shown = safe_url(url)
    if STARTER.search(url):
        return ("WARN", "remote: origin is the public starter ({})".format(shown),
                "company/ stays on your machine either way. Make your own private copy "
                "before you push your own work: anything pushed to a public repo is public.")
    return ("WARN", "remote: origin is {}".format(shown),
            "If that repo is public, keep company material out of it. "
            "Check: gh repo view --json visibility")


def check_gate(root):
    example = root / "proposals" / "juniper-bakery.md"
    if not example.is_file():
        return ("WARN", "gate: proposals/juniper-bakery.md is gone, so the example gate wasn't run",
                "Fine if you've replaced the proposal job with your own.")
    result = subprocess.run([sys.executable, str(root / "gates" / "proposal_gate.py"), str(example)],
                            capture_output=True, text=True)
    if result.returncode == 0:
        return ("PASS", "gate: the example proposal passes", None)
    return ("FAIL", "gate: the example proposal fails on a clone where it should pass",
            "Run python3 gates/proposal_gate.py proposals/juniper-bakery.md and "
            "git status to see what changed.")


def check_company(root):
    record = root / "company" / "COMPANY.md"
    if record.is_file():
        return ("PASS", "company: company/COMPANY.md is written", None)
    return ("WARN", "company: no company record yet, so the agent doesn't know who it works for",
            "Run /orientation, or say \"get me started\", and it interviews you for it.")


def run(root):
    return [check_python(), check_hooks(root), check_links(root), check_gate(root),
            check_company(root), check_remote(root)]


def main():
    results = run(ROOT)
    for status, line, fix in results:
        print("{} {}".format(status, line))
        if fix:
            print("     {}: {}".format("fix" if status == "FAIL" else "note", fix))
    return 1 if any(status == "FAIL" for status, _, _ in results) else 0


if __name__ == "__main__":
    sys.exit(main())
