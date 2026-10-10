#!/usr/bin/env python3
"""The loop: take a ready issue, plan it, build it, check it, open a pull request.

Usage:
    python3 scripts/loop.py run [--once] [--issue N] [--dry-run]
    python3 scripts/loop.py stop

One pass is one turn of the flywheel:

    Discover  pick the next open issue labelled loop-ready
    Shape     a fresh agent writes the smallest plan that would count
    Build     a fresh agent makes the change in a git worktree
    Validate  this script runs your tests, a second fresh agent reviews the diff
    Scale     on PASS open a pull request, note what went wrong, take the next one

Build and Validate repeat up to max_rounds. Then the issue is labelled
loop:blocked and the loop moves on without it.

Watch it with:  tail -f .loop/loop.log
The same state, for a tool to read, is in .loop/status.json: what's waiting, what each
issue is on, and how its last round went.
Everything a round produced is in .loop/issue-N/. Checkouts live outside the clone, in
~/.harness-loop/. It never merges.
Standard library only; needs git and the gh CLI, signed in.
"""
import argparse
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

DEFAULTS = {
    # The command that starts an agent session. The prompt arrives on stdin.
    "agent": "claude -p --permission-mode acceptEdits",
    # The agent that plans and reviews. It is told not to edit, and any edit is thrown away.
    "reader_agent": "claude -p",
    # Run by this script, never by the agent, so the agent can't grade its own work.
    "test_command": "python3 -m unittest discover -s tests",
    "base": "main",
    "ready_label": "loop-ready",
    "blocked_label": "loop:blocked",
    "max_rounds": 5,
    "agent_timeout": 1800,
    "test_timeout": 1800,
    "poll_seconds": 60,
    # Where the build checkouts go. Empty means ~/.harness-loop/<this folder's name>. Keep it outside the
    # clone: an agent started in a nested folder loads this repo's CLAUDE.md too, which tells it to stop.
    "worktree_dir": "",
}

VERDICT = re.compile(r"^\s*VERDICT:\s*(PASS|FIX)\s*$", re.I | re.M)
OUTPUT_CAP = 100_000
STATUS_KEEP = 20  # issues kept in status.json, newest first


def load_config(root):
    """The defaults, overlaid with loop.json at the repo root if there is one."""
    cfg = dict(DEFAULTS)
    path = Path(root) / "loop.json"
    if path.exists():
        cfg.update(json.loads(path.read_text()))
    return cfg


def parse_verdict(text):
    """PASS or FIX from the last VERDICT line. No verdict counts as FIX."""
    found = VERDICT.findall(text or "")
    return found[-1].upper() if found else "FIX"


def findings(text, limit=3):
    """The first few lines of a review that aren't the verdict, for the log and the lessons."""
    lines = [l.strip() for l in (text or "").splitlines() if l.strip() and not VERDICT.match(l)]
    return " / ".join(lines[:limit])[:300]


def ready(issues, me, cfg):
    """Every issue the loop may take, lowest number first.

    Skips one already labelled blocked, and one assigned to someone who isn't you.
    """
    out = []
    for issue in sorted(issues, key=lambda i: i["number"]):
        labels = {l["name"] for l in issue.get("labels", [])}
        if cfg["blocked_label"] in labels or cfg["ready_label"] not in labels:
            continue
        who = [a["login"] for a in issue.get("assignees", [])]
        if who and me not in who:
            continue
        out.append(issue)
    return out


def pick(issues, me, cfg, only=None):
    """The lowest-numbered issue the loop may take, or None. With only=N, that issue alone."""
    for issue in ready(issues, me, cfg):
        if only is None or issue["number"] == only:
            return issue
    return None


def shape_prompt(issue):
    return (
        "You are planning, not building. Do not edit any file.\n"
        "Read the ticket below and the rules in AGENTS.md. Write the smallest version of "
        "this change that would count as done, as plain markdown under 40 lines: what "
        "changes, in which files, what check proves it, and what you are leaving out.\n\n"
        "TICKET #{number}: {title}\n{body}\n".format(
            number=issue["number"], title=issue["title"], body=issue.get("body") or "")
    )


def tail(text, size=20_000):
    """The end of a long text, which is where a test failure is."""
    text = text or ""
    return text if len(text) <= size else "...\n" + text[-size:]


def build_prompt(number, plan, review="", tests=""):
    """Everything goes in the prompt: an agent in a worktree can't read the loop's own folder."""
    prompt = (
        "Make the change for issue #{n} in this git worktree.\n"
        "Keep to the plan below. Don't commit, push or use git for anything but reading. "
        "Don't run the test suite: the loop runs it. When the change is in place, say in "
        "two lines what you changed.\n\nPLAN:\n{plan}\n"
    ).format(n=number, plan=plan)
    if review or tests:
        prompt += (
            "\nAn earlier round failed. Fix exactly what it says.\n\n"
            "REVIEW OF THE LAST ROUND:\n{review}\n\nTEST OUTPUT OF THE LAST ROUND:\n{tests}\n"
        ).format(review=review.strip(), tests=tail(tests))
    return prompt


def review_prompt(plan, diff, tests, code):
    return (
        "You are the reviewer, in a fresh context. Do not edit any file.\n"
        "Below are the plan, the diff, and the test output (the tests exited {code}). Say "
        "whether the change does what the plan asks, and list the problems that matter, "
        "most important first, one line each.\n"
        "Your last line must be exactly VERDICT: PASS or VERDICT: FIX. PASS only if the "
        "tests exited 0 and the diff matches the plan.\n\n"
        "PLAN:\n{plan}\n\nDIFF:\n{diff}\n\nTEST OUTPUT:\n{tests}\n"
    ).format(code=code, plan=plan.strip(), diff=tail(diff, 60_000), tests=tail(tests))


class Loop:
    def __init__(self, root=ROOT, cfg=None):
        self.root = Path(root)
        self.cfg = cfg or load_config(self.root)
        self.dir = self.root / ".loop"
        self.dir.mkdir(exist_ok=True)
        self.me = None
        self.status = self.read_status()

    # -- plumbing ---------------------------------------------------------

    def log(self, step, text, number=None):
        """One line per event: time, issue, step, detail. The whole monitor is tail -f."""
        who = "#{}".format(number) if number else "-"
        line = "{} {} {} {}".format(datetime.now().isoformat(timespec="seconds"), who, step, text)
        with open(self.dir / "loop.log", "a") as handle:
            handle.write(line + "\n")
        print(line, flush=True)

    def read_status(self):
        try:
            found = json.loads((self.dir / "status.json").read_text())
        except (OSError, ValueError):
            found = {}
        found.setdefault("queue", [])
        found.setdefault("issues", [])
        return found

    def save_status(self, **fields):
        """Rewrite .loop/status.json whole, so a reader never sees half a file."""
        self.status.update(fields)
        self.status["updated"] = datetime.now().isoformat(timespec="seconds")
        self.status["issues"] = self.status["issues"][:STATUS_KEEP]
        part = self.dir / "status.json.part"
        part.write_text(json.dumps(self.status, indent=2) + "\n")
        os.replace(part, self.dir / "status.json")

    def mark(self, number, **fields):
        """Update one issue's entry and move it to the top: it's the one the loop is on."""
        rows = self.status["issues"]
        row = next((r for r in rows if r["number"] == number), None)
        if row is None:
            row = {"number": number, "title": "", "step": "", "state": "", "round": 0,
                   "tests": None, "review": None, "pr": None, "note": ""}
        else:
            rows.remove(row)
        row.update(fields)
        row["updated"] = datetime.now().isoformat(timespec="seconds")
        rows.insert(0, row)
        if row["state"] in ("pr", "blocked", "skipped"):
            # Off the queue the moment it ends, as its label is: the next look at GitHub agrees.
            self.status["queue"] = [q for q in self.status["queue"] if q["number"] != number]
        self.save_status()

    def sh(self, cmd, cwd=None, stdin=None, timeout=None, shell=False):
        """(exit code, combined output). A missing command or a timeout is a code, not a crash."""
        try:
            done = subprocess.run(cmd, cwd=str(cwd or self.root), input=stdin, shell=shell,
                                  capture_output=True, text=True, timeout=timeout)
        except FileNotFoundError:
            return 127, "command not found: {}".format(cmd if shell else cmd[0])
        except subprocess.TimeoutExpired:
            return 124, "timed out after {}s".format(timeout)
        return done.returncode, (done.stdout or "") + (done.stderr or "")

    def git(self, *args, cwd=None):
        return self.sh(["git"] + list(args), cwd=cwd)

    def gh(self, *args):
        return self.sh(["gh"] + list(args))

    def stopped(self):
        return (self.dir / "STOP").exists()

    def whoami(self):
        if self.me is None:
            code, out = self.gh("api", "user", "-q", ".login")
            self.me = out.strip() if code == 0 else ""
        return self.me

    def agent(self, which, prompt, cwd):
        """Run a fresh agent session. Returns (exit code, what it said)."""
        cmd = shlex.split(self.cfg[which])
        return self.sh(cmd, cwd=cwd, stdin=prompt, timeout=self.cfg["agent_timeout"])

    # -- the flywheel -----------------------------------------------------

    def discover(self, only=None):
        code, out = self.gh("issue", "list", "--state", "open", "--limit", "50", "--json",
                            "number,title,body,labels,assignees")
        if code != 0:
            self.log("ERROR", "could not list issues: " + out.strip()[:200])
            return None
        waiting = ready(json.loads(out or "[]"), self.whoami(), self.cfg)
        self.save_status(queue=[{"number": i["number"], "title": i["title"]} for i in waiting])
        return pick(waiting, self.whoami(), self.cfg, only)

    def worktrees(self):
        if self.cfg["worktree_dir"]:
            return Path(self.cfg["worktree_dir"]).expanduser()
        return Path.home() / ".harness-loop" / self.root.name

    def worktree(self, number):
        path = self.worktrees() / "issue-{}".format(number)
        branch = "loop/issue-{}".format(number)
        if path.exists():
            return path, branch
        self.git("fetch", "-q", "origin", self.cfg["base"])
        path.parent.mkdir(parents=True, exist_ok=True)
        known = self.git("rev-parse", "--verify", "-q", branch)[0] == 0
        args = ["worktree", "add", "-q", str(path), branch] if known else \
            ["worktree", "add", "-q", "-b", branch, str(path), "origin/" + self.cfg["base"]]
        code, out = self.git(*args)
        if code != 0:
            raise RuntimeError("could not make the worktree: " + out.strip()[:200])
        return path, branch

    def block(self, number, why):
        """Take the issue off the queue: drop the ready label first, then mark it blocked."""
        self.gh("issue", "edit", str(number), "--remove-label", self.cfg["ready_label"])
        self.gh("issue", "edit", str(number), "--add-label", self.cfg["blocked_label"])
        self.log("BLOCKED", why, number)
        self.mark(number, state="blocked", note=why)

    def lesson(self, number, rounds, problems, passed):
        """Append an entry in the shape the learn skill reads: what went wrong, what should have happened."""
        right = ("the change on loop/issue-{} passed the tests and the review".format(number)
                 if passed else "unknown: a person decides")
        entry = "## {} #{}: {} round{}\n**What went wrong:** {}\n**What should have happened:** {}\n\n".format(
            datetime.now().strftime("%Y-%m-%d"), number, rounds, "" if rounds == 1 else "s",
            " | ".join(problems) or "the run stopped", right)
        with open(self.dir / "lessons.md", "a") as handle:
            handle.write(entry)

    def process(self, issue):
        number = issue["number"]
        folder = self.dir / "issue-{}".format(number)
        folder.mkdir(exist_ok=True)
        (folder / "ticket.md").write_text("# #{}: {}\n\n{}\n".format(
            number, issue["title"], issue.get("body") or ""))
        self.log("DISCOVER", 'picked "{}"'.format(issue["title"]), number)
        self.mark(number, title=issue["title"], step="SHAPE", state="working", round=0,
                  tests=None, review=None, pr=None, note="", max_rounds=self.cfg["max_rounds"])

        code, plan = self.agent("reader_agent", shape_prompt(issue), self.root)
        if code != 0 or not plan.strip():
            return self.block(number, "shape failed (agent exit {})".format(code))
        (folder / "plan.md").write_text(plan)
        self.log("SHAPE", "done plan.md", number)

        try:
            tree, branch = self.worktree(number)
        except RuntimeError as err:
            return self.block(number, str(err))

        problems = []
        for round_no in range(1, self.cfg["max_rounds"] + 1):
            if self.stopped():
                self.mark(number, state="stopped", note="stopped before round {}".format(round_no))
                return self.log("STOPPED", "before round {}".format(round_no), number)
            self.mark(number, step="BUILD", round=round_no)

            last_review = (folder / "review.md").read_text() if (folder / "review.md").exists() else ""
            last_tests = (folder / "test-output.txt").read_text() if (folder / "test-output.txt").exists() else ""
            code, said = self.agent("agent", build_prompt(number, plan, last_review, last_tests), tree)
            if code != 0:
                return self.block(number, "build failed (agent exit {})".format(code))
            self.git("add", "-A", cwd=tree)
            changed = self.git("diff", "--cached", "--name-only", cwd=tree)[1].split()
            if changed:
                self.git("commit", "-q", "-m", "loop: issue {} round {}".format(number, round_no), cwd=tree)
            self.log("BUILD", "round {} done {} file{}".format(
                round_no, len(changed), "" if len(changed) == 1 else "s"), number)
            self.mark(number, step="VALIDATE")

            tcode, tout = self.sh(self.cfg["test_command"], cwd=tree, shell=True,
                                  timeout=self.cfg["test_timeout"])
            (folder / "test-output.txt").write_text(tout[-OUTPUT_CAP:])
            diff = self.git("diff", "origin/{}...HEAD".format(self.cfg["base"]), cwd=tree)[1]
            (folder / "diff.patch").write_text(diff[:OUTPUT_CAP])

            rcode, review = self.agent("reader_agent", review_prompt(plan, diff, tout or "(no output)", tcode), tree)
            if self.git("status", "--porcelain", cwd=tree)[1].strip():
                self.git("checkout", "--", ".", cwd=tree)
                self.git("clean", "-fdq", cwd=tree)
                self.log("REVIEW", "reviewer edited files; discarded", number)
            (folder / "review.md").write_text(review)
            verdict = parse_verdict(review) if rcode == 0 else "FIX"

            passed = tcode == 0 and verdict == "PASS"
            self.log("VALIDATE", "round {} tests {} review {}".format(
                round_no, "passed" if tcode == 0 else "failed ({})".format(tcode), verdict), number)
            self.mark(number, tests="passed" if tcode == 0 else "failed ({})".format(tcode), review=verdict)
            if passed:
                return self.scale(issue, branch, round_no, problems)
            problems.append("round {}: {}".format(
                round_no, findings(review) if rcode == 0 else "review did not run"))

        self.lesson(number, self.cfg["max_rounds"], problems, passed=False)
        self.block(number, "still failing after {} rounds, see .loop/issue-{}/".format(
            self.cfg["max_rounds"], number))

    def scale(self, issue, branch, rounds, problems):
        number = issue["number"]
        self.mark(number, step="SCALE")
        code, state = self.gh("issue", "view", str(number), "--json", "state", "-q", ".state")
        if code == 0 and state.strip() != "OPEN":
            self.mark(number, state="skipped", note="issue is {}".format(state.strip().lower()))
            return self.log("SCALE", "skipped: issue is {}, no pull request opened".format(state.strip().lower()), number)
        code, out = self.git("push", "-q", "-u", "origin", branch)
        if code != 0:
            return self.block(number, "push failed: " + out.strip()[:200])
        body = "Refs #{}.\n\nPlan, test output and review are in .loop/issue-{}/ on the machine that ran the loop.\n".format(
            number, number)
        code, out = self.gh("pr", "create", "--base", self.cfg["base"], "--head", branch,
                            "--title", "{} (#{})".format(issue["title"], number), "--body", body)
        if code != 0:
            return self.block(number, "could not open the pull request: " + out.strip()[:200])
        self.gh("issue", "edit", str(number), "--remove-label", self.cfg["ready_label"])
        url = out.strip().splitlines()[-1]
        self.log("SCALE", "PR opened " + url, number)
        self.mark(number, state="pr", pr=url)
        if problems:
            self.lesson(number, rounds, problems, passed=True)

    # -- running ----------------------------------------------------------

    def take_lock(self):
        lock = self.dir / "lock"
        if lock.exists():
            try:
                os.kill(int(lock.read_text()), 0)
                return False
            except PermissionError:
                return False  # the process exists and belongs to someone else
            except (ValueError, ProcessLookupError, OSError):
                lock.unlink()
        lock.write_text(str(os.getpid()))
        return True

    def run(self, once=False, only=None, dry_run=False):
        if not self.take_lock():
            print("The loop is already running here (see .loop/lock).", file=sys.stderr)
            return 1
        try:
            (self.dir / "STOP").unlink(missing_ok=True)  # no other loop holds the lock, so an old stop is stale
            self.save_status(running=True, pid=os.getpid())
            idle = False
            while not self.stopped():
                issue = self.discover(only)
                if issue is None:
                    if not idle:
                        self.log("IDLE", "nothing ready")
                        idle = True
                    if once or dry_run:
                        break
                    time.sleep(self.cfg["poll_seconds"])
                    continue
                idle = False
                if dry_run:
                    self.log("DISCOVER", 'would pick "{}"'.format(issue["title"]), issue["number"])
                    break
                self.process(issue)
                if once:
                    break
            if self.stopped():
                self.log("STOPPED", "stop file found")
                (self.dir / "STOP").unlink()
        finally:
            self.save_status(running=False, pid=None)
            (self.dir / "lock").unlink(missing_ok=True)
        return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run", help="take ready issues until none are left, or stopped")
    run.add_argument("--once", action="store_true", help="one issue, then exit")
    run.add_argument("--issue", type=int, help="only this issue number")
    run.add_argument("--dry-run", action="store_true", help="say which issue it would take, then exit")
    sub.add_parser("stop", help="ask a running loop to stop after its current step")
    args = parser.parse_args(argv)

    loop = Loop()
    if args.command == "stop":
        (loop.dir / "STOP").write_text("")
        print("Stop requested. The loop ends at its next step.")
        return 0
    return loop.run(once=args.once, only=args.issue, dry_run=args.dry_run)


if __name__ == "__main__":
    sys.exit(main())
