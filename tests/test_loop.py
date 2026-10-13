"""Run with: python3 -m unittest discover -s tests"""
import contextlib
import io
import json
import os
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import loop  # noqa: E402

CFG = dict(loop.DEFAULTS)
EM_DASH = chr(0x2014)  # a code point, so this file passes its own check


def issue(number, labels=("loop-ready",), assignees=(), title="Add the thing"):
    return {"number": number, "title": title, "body": "body",
            "labels": [{"name": n} for n in labels],
            "assignees": [{"login": a} for a in assignees]}


class TestPureParts(unittest.TestCase):
    def test_verdict_is_the_last_line_and_defaults_to_fix(self):
        self.assertEqual(loop.parse_verdict("ok\nVERDICT: PASS"), "PASS")
        self.assertEqual(loop.parse_verdict("VERDICT: PASS\nbut wait\nVERDICT: FIX"), "FIX")
        self.assertEqual(loop.parse_verdict("looks fine to me"), "FIX")
        self.assertEqual(loop.parse_verdict(""), "FIX")

    def test_findings_skip_the_verdict(self):
        text = "Missing a test.\n\nHeader is wrong.\nVERDICT: FIX"
        self.assertEqual(loop.findings(text), "Missing a test. / Header is wrong.")

    def test_pick_takes_the_lowest_ready_issue_you_may_take(self):
        issues = [issue(9), issue(3, assignees=("sam",)), issue(5, labels=("loop-ready", "loop:blocked")),
                  issue(4, labels=("bug",)), issue(7)]
        self.assertEqual(loop.pick(issues, "pat", CFG)["number"], 7)
        self.assertEqual(loop.pick(issues, "sam", CFG)["number"], 3)
        self.assertEqual(loop.pick(issues, "pat", CFG, only=9)["number"], 9)
        self.assertIsNone(loop.pick(issues, "pat", CFG, only=5))
        self.assertIsNone(loop.pick([], "pat", CFG))

    def test_ready_lists_every_issue_the_loop_may_take_in_order(self):
        issues = [issue(9), issue(3, assignees=("sam",)), issue(5, labels=("loop-ready", "loop:blocked")),
                  issue(4, labels=("bug",)), issue(7)]
        self.assertEqual([i["number"] for i in loop.ready(issues, "pat", CFG)], [7, 9])
        self.assertEqual([i["number"] for i in loop.ready(issues, "sam", CFG)], [3, 7, 9])

    def test_config_overlays_defaults_from_loop_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(loop.load_config(tmp), loop.DEFAULTS)
            Path(tmp, "loop.json").write_text(json.dumps({"max_rounds": 2}))
            cfg = loop.load_config(tmp)
            self.assertEqual(cfg["max_rounds"], 2)
            self.assertEqual(cfg["base"], "main")

    def test_prompts_carry_their_inputs_so_the_agent_needs_no_file_access(self):
        build = loop.build_prompt(4, "Plan: add feature.txt.")
        self.assertIn("Plan: add feature.txt.", build)
        self.assertIn("Don't run the test suite", build)
        self.assertNotIn("earlier round failed", build)
        again = loop.build_prompt(4, "Plan.", "feature.txt is wrong.", "FAILED test_x")
        self.assertIn("feature.txt is wrong.", again)
        self.assertIn("FAILED test_x", again)
        review = loop.review_prompt("Plan.", "+++ feature.txt", "ok", 0)
        for part in ("Plan.", "+++ feature.txt", "the tests exited 0", "VERDICT: PASS or VERDICT: FIX"):
            self.assertIn(part, review)
        self.assertIn("Do not edit", loop.shape_prompt(issue(4)))
        for text in (build, again, review, loop.shape_prompt(issue(4))):
            self.assertNotIn(EM_DASH, text)

    def test_a_long_test_output_keeps_its_end(self):
        long = "a" * 50_000 + "THE FAILURE"
        cut = loop.tail(long, 1000)
        self.assertTrue(cut.endswith("THE FAILURE"))
        self.assertLess(len(cut), 1100)
        self.assertEqual(loop.tail("short"), "short")


# A stand-in agent and a stand-in gh, so a whole pass runs with no network and no model.
AGENT = """#!/usr/bin/env python3
import os, sys
prompt = sys.stdin.read()
state = os.environ["LOOP_TEST_STATE"]
if "You are planning" in prompt:
    print("Plan: add feature.txt.")
elif "You are the reviewer" in prompt:
    if os.path.exists(os.path.join(state, "reviewer-edits")):
        open("sneaky.txt", "w").write("x")
    verdict = open(os.path.join(state, "verdict")).read().strip()
    print("Looks right." if verdict == "PASS" else "feature.txt is wrong.")
    print("VERDICT: " + verdict)
else:
    open("feature.txt", "a").write("done")
    print("Added feature.txt.")
"""

GH = """#!/usr/bin/env python3
import os, sys
state = os.environ["LOOP_TEST_STATE"]
args = sys.argv[1:]
with open(os.path.join(state, "gh-calls"), "a") as f:
    f.write(" ".join(args) + "\\n")
if args[:2] == ["api", "user"]:
    print("pat")
elif args[:2] == ["issue", "list"]:
    print(open(os.path.join(state, "issues.json")).read())
elif args[:2] == ["issue", "view"]:
    path = os.path.join(state, "issue-state")
    print(open(path).read().strip() if os.path.exists(path) else "OPEN")
elif args[:2] == ["pr", "create"]:
    print("https://example.test/pull/1")
elif args[:2] == ["issue", "comment"] and os.path.exists(os.path.join(state, "comment-fails")):
    print("HTTP 403: comments are locked", file=sys.stderr)
    sys.exit(1)
"""

# A stand-in tmux that answers display-message with the session name, and records what it was asked.
TMUX = """#!/usr/bin/env python3
import os, sys
state = os.environ["LOOP_TEST_STATE"]
with open(os.path.join(state, "tmux-calls"), "a") as f:
    f.write(" ".join(sys.argv[1:]) + "\\n")
print("loop-work")
"""


def git(cwd, *args):
    return subprocess.run(["git", "-C", str(cwd)] + list(args), capture_output=True, text=True, check=True)


class TestAPass(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        tmp = Path(self.tmp.name)
        self.state = tmp / "state"
        self.state.mkdir()
        bin_dir = tmp / "bin"
        bin_dir.mkdir()
        for name, body in (("gh", GH), ("agent", AGENT), ("tmux", TMUX)):
            path = bin_dir / name
            path.write_text(body)
            path.chmod(path.stat().st_mode | stat.S_IEXEC)
        self.origin = tmp / "origin.git"
        subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(self.origin)], check=True)
        self.work = tmp / "work"
        subprocess.run(["git", "clone", "-q", str(self.origin), str(self.work)], check=True, capture_output=True)
        git(self.work, "config", "user.email", "t@example.test")
        git(self.work, "config", "user.name", "Test")
        (self.work / "README.md").write_text("hi")
        git(self.work, "add", "-A")
        git(self.work, "commit", "-q", "-m", "init")
        git(self.work, "push", "-q", "-u", "origin", "main")
        agent = "{} {}".format(sys.executable, bin_dir / "agent")
        self.cfg = dict(loop.DEFAULTS, agent=agent, reader_agent=agent, test_command="test -f feature.txt",
                        max_rounds=2, poll_seconds=0, worktree_dir=str(tmp / "trees"))
        (self.state / "issues.json").write_text(json.dumps([issue(12)]))
        (self.state / "verdict").write_text("PASS")
        os.environ["LOOP_TEST_STATE"] = str(self.state)
        self.old_path = os.environ["PATH"]
        os.environ["PATH"] = str(bin_dir) + os.pathsep + self.old_path
        # The suite may itself run inside tmux; each test says whether the loop does.
        self.old_tmux = {k: os.environ.pop(k) for k in ("TMUX", "TMUX_PANE") if k in os.environ}

    def tearDown(self):
        os.environ["PATH"] = self.old_path
        for k in ("TMUX", "TMUX_PANE"):
            os.environ.pop(k, None)
        os.environ.update(self.old_tmux)
        os.environ.pop("LOOP_TEST_STATE", None)
        self.tmp.cleanup()

    def lines(self):
        return (self.work / ".loop" / "loop.log").read_text().splitlines()

    def status(self):
        return json.loads((self.work / ".loop" / "status.json").read_text())

    def calls(self):
        return (self.state / "gh-calls").read_text().splitlines()

    def comments(self):
        """The text of each issue comment the loop posted (a body can run over several lines)."""
        text = (self.state / "gh-calls").read_text()
        return [chunk.split("--body ", 1)[1] for chunk in text.split("issue comment ")[1:]]

    def go(self, **kwargs):
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            return loop.Loop(self.work, self.cfg).run(once=True, **kwargs)

    def test_a_good_change_opens_a_pull_request_in_five_steps(self):
        self.assertEqual(self.go(), 0)
        steps = [l.split()[2] for l in self.lines()]
        self.assertEqual(steps, ["DISCOVER", "SHAPE", "BUILD", "VALIDATE", "SCALE"])
        self.assertIn("#12", self.lines()[0])
        self.assertTrue(any(c.startswith("pr create --base main --head loop/issue-12") for c in self.calls()))
        self.assertIn("issue edit 12 --remove-label loop-ready", self.calls())
        folder = self.work / ".loop" / "issue-12"
        for name in ("ticket.md", "plan.md", "test-output.txt", "diff.patch", "review.md"):
            self.assertTrue((folder / name).exists(), name)
        self.assertIn("feature.txt", (folder / "diff.patch").read_text())
        self.assertFalse((self.work / ".loop" / "lessons.md").exists())
        self.assertFalse((self.work / ".loop" / "lock").exists())
        remote = git(self.work, "ls-remote", "origin", "loop/issue-12").stdout
        self.assertIn("refs/heads/loop/issue-12", remote)

    def test_each_round_commits_under_the_issue_title(self):
        self.go()
        subject, body = git(self.origin, "log", "-1", "--format=%s%n%b", "loop/issue-12").stdout.split("\n", 1)
        self.assertEqual(subject, "Add the thing")
        self.assertIn("#12", body)
        self.assertIn("round 1", body)

    def test_two_rounds_make_two_commits_with_the_same_subject(self):
        (self.state / "verdict").write_text("FIX")
        self.go()
        log = git(self.work, "log", "--format=%s|%b%x00", "main..loop/issue-12").stdout
        commits = [c.strip().split("|", 1) for c in log.split("\0") if c.strip()]
        self.assertEqual(len(commits), 2)
        self.assertEqual([subject for subject, _ in commits], ["Add the thing", "Add the thing"])
        self.assertIn("round 2", commits[0][1])
        self.assertIn("round 1", commits[1][1])

    def test_status_says_what_waited_and_where_the_issue_ended(self):
        (self.state / "issues.json").write_text(json.dumps([issue(12), issue(15, title="Next one")]))
        self.go()
        status = self.status()
        self.assertFalse(status["running"])
        self.assertEqual(status["queue"], [{"number": 15, "title": "Next one"}])
        row = status["issues"][0]
        self.assertEqual((row["number"], row["state"], row["step"], row["round"]), (12, "pr", "SCALE", 1))
        self.assertEqual((row["tests"], row["review"], row["pr"]), ("passed", "PASS", "https://example.test/pull/1"))
        self.assertFalse((self.work / ".loop" / "status.json.part").exists())

    def test_status_of_a_blocked_issue_keeps_its_last_round(self):
        (self.state / "verdict").write_text("FIX")
        self.go()
        status = self.status()
        row = status["issues"][0]
        self.assertEqual((row["state"], row["round"], row["review"]), ("blocked", 2, "FIX"))
        self.assertEqual(status["queue"], [])
        self.assertIn("still failing after 2 rounds", row["note"])

    def test_status_keeps_the_newest_issues_first_and_survives_a_bad_file(self):
        (self.work / ".loop").mkdir(exist_ok=True)
        (self.work / ".loop" / "status.json").write_text("{not json")
        runner = loop.Loop(self.work, self.cfg)
        for number in range(1, loop.STATUS_KEEP + 6):
            runner.mark(number, title="t", state="pr")
        runner.mark(3, state="blocked")
        numbers = [r["number"] for r in self.status()["issues"]]
        self.assertEqual(len(numbers), loop.STATUS_KEEP)
        self.assertEqual(numbers[:2], [3, loop.STATUS_KEEP + 5])

    def test_a_pull_request_closes_the_issue_and_the_issue_hears_about_it(self):
        self.go()
        text = (self.state / "gh-calls").read_text()
        self.assertIn("Closes #12.", text)
        self.assertNotIn("Refs #12", text)
        comments = self.comments()
        self.assertEqual(len(comments), 1)
        self.assertIn("The loop opened https://example.test/pull/1 after 1 round:", comments[0])
        self.assertIn("doesn't merge", comments[0])

    def test_a_blocked_issue_says_why_and_how_to_retry(self):
        (self.state / "verdict").write_text("FIX")
        self.go()
        comments = self.comments()
        self.assertEqual(len(comments), 1)
        self.assertIn("after 2 rounds: still failing after 2 rounds", comments[0])
        self.assertIn("take loop:blocked off and put loop-ready back", comments[0])
        calls = self.calls()
        self.assertLess(calls.index("issue edit 12 --add-label loop:blocked"),
                        next(i for i, c in enumerate(calls) if c.startswith("issue comment 12")))

    def test_a_comment_that_fails_is_logged_and_the_pull_request_stands(self):
        (self.state / "comment-fails").write_text("")
        self.assertEqual(self.go(), 0)
        log = "\n".join(self.lines())
        self.assertIn("SCALE PR opened", log)
        self.assertIn("could not comment on the issue: HTTP 403", log)
        self.assertEqual(self.status()["issues"][0]["state"], "pr")

    def test_a_change_that_keeps_failing_is_blocked_with_the_label_taken_off_first(self):
        (self.state / "verdict").write_text("FIX")
        self.go()
        steps = [l.split()[2] for l in self.lines()]
        self.assertEqual(steps.count("BUILD"), 2)
        self.assertEqual(steps[-1], "BLOCKED")
        calls = self.calls()
        remove = calls.index("issue edit 12 --remove-label loop-ready")
        add = calls.index("issue edit 12 --add-label loop:blocked")
        self.assertLess(remove, add)
        self.assertFalse(any(c.startswith("pr create") for c in calls))
        lesson = (self.work / ".loop" / "lessons.md").read_text()
        self.assertIn("**What went wrong:**", lesson)
        self.assertIn("feature.txt is wrong.", lesson)
        self.assertIn("**What should have happened:** unknown", lesson)

    def test_a_change_for_an_issue_closed_meanwhile_opens_no_pull_request(self):
        (self.state / "issue-state").write_text("CLOSED")
        self.go()
        self.assertEqual(self.lines()[-1].split()[2], "SCALE")
        self.assertIn("skipped: issue is closed", self.lines()[-1])
        self.assertEqual(self.status()["issues"][0]["state"], "skipped")
        calls = self.calls()
        self.assertFalse(any(c.startswith("pr create") for c in calls))
        self.assertNotIn("issue edit 12 --remove-label loop-ready", calls)
        self.assertFalse(any(c.startswith("issue comment") for c in calls))
        remote = git(self.work, "ls-remote", "origin", "loop/issue-12").stdout
        self.assertEqual(remote, "")

    def test_failing_tests_block_even_when_the_reviewer_says_pass(self):
        self.cfg["test_command"] = "test -f never-exists.txt"
        self.go()
        self.assertEqual(self.lines()[-1].split()[2], "BLOCKED")
        self.assertIn("tests failed", "\n".join(self.lines()))

    def test_a_reviewer_that_edits_files_has_them_thrown_away(self):
        (self.state / "reviewer-edits").write_text("")
        self.go()
        self.assertIn("reviewer edited files; discarded", "\n".join(self.lines()))
        tree = Path(self.cfg["worktree_dir"]) / "issue-12"
        self.assertFalse((tree / "sneaky.txt").exists())
        self.assertNotIn("sneaky.txt", (self.work / ".loop" / "issue-12" / "diff.patch").read_text())

    def test_checkouts_live_outside_the_clone(self):
        self.go()
        self.assertTrue((Path(self.cfg["worktree_dir"]) / "issue-12" / "feature.txt").exists())
        self.assertFalse((self.work / ".loop" / "worktrees").exists())
        default = loop.Loop(self.work, dict(loop.DEFAULTS)).worktrees()
        self.assertEqual(default, Path.home() / ".harness-loop" / "work")

    def test_a_lock_held_by_another_users_process_is_respected(self):
        original = os.kill

        def kill(pid, sig):
            raise PermissionError()

        os.kill = kill
        try:
            (self.work / ".loop").mkdir(exist_ok=True)
            (self.work / ".loop" / "lock").write_text("1")
            self.assertEqual(self.go(), 1)
        finally:
            os.kill = original

    def test_dry_run_names_the_issue_and_starts_no_agent(self):
        self.go(dry_run=True)
        self.assertEqual(len(self.lines()), 1)
        self.assertIn("would pick", self.lines()[0])
        self.assertFalse((self.work / ".loop" / "issue-12").exists())

    def test_inside_tmux_the_log_and_status_name_the_session(self):
        os.environ.update(TMUX="/tmp/tmux-501/default,1,0", TMUX_PANE="%3")
        self.go()
        self.assertEqual(self.lines()[0].split()[2], "START")
        self.assertIn("in tmux session loop-work: tmux attach -t loop-work", self.lines()[0])
        self.assertIn("-t %3", (self.state / "tmux-calls").read_text())
        self.assertIsNone(self.status()["tmux"])  # a finished run names no session

    def test_status_names_the_session_while_running(self):
        os.environ.update(TMUX="/tmp/tmux-501/default,1,0", TMUX_PANE="%3")
        seen = []
        original = loop.Loop.process
        def process(this, issue):
            seen.append(this.status.get("tmux"))
            return original(this, issue)
        with mock.patch.object(loop.Loop, "process", process):
            self.go()
        self.assertEqual(seen, ["loop-work"])

    def test_outside_tmux_nothing_extra_is_logged_or_asked(self):
        self.go()
        self.assertNotIn("START", [l.split()[2] for l in self.lines()])
        self.assertFalse((self.state / "tmux-calls").exists())

    def test_nothing_ready_logs_idle_once(self):
        (self.state / "issues.json").write_text("[]")
        self.go()
        self.assertEqual([l.split()[2] for l in self.lines()], ["IDLE"])

    def run_issue_flag(self):
        """A run with --issue 12 and no --once. Sleeping means it went on polling, so that fails at once."""
        with mock.patch.object(loop.time, "sleep", side_effect=AssertionError("polled")), \
                contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            return loop.Loop(self.work, self.cfg).run(once=False, only=12)

    def test_issue_flag_exits_after_that_issue(self):
        self.assertEqual(self.run_issue_flag(), 0)
        self.assertEqual(self.lines()[-1].split()[2], "SCALE")

    def test_issue_flag_not_ready_logs_idle_once_and_exits(self):
        (self.state / "issues.json").write_text("[]")
        self.assertEqual(self.run_issue_flag(), 0)
        self.assertEqual([l.split()[2] for l in self.lines()], ["IDLE"])

    def test_a_second_loop_is_refused_while_one_holds_the_lock(self):
        (self.work / ".loop").mkdir(exist_ok=True)
        (self.work / ".loop" / "lock").write_text(str(os.getpid()))
        self.assertEqual(self.go(), 1)
        self.assertFalse((self.work / ".loop" / "loop.log").exists())

    def test_a_stale_lock_is_replaced(self):
        (self.work / ".loop").mkdir(exist_ok=True)
        (self.work / ".loop" / "lock").write_text("999999")
        self.assertEqual(self.go(dry_run=True), 0)

    def test_a_stop_file_ends_the_loop_between_steps(self):
        loop_obj = loop.Loop(self.work, self.cfg)
        (loop_obj.dir / "STOP").write_text("")
        # run() clears a stop left from before it started, so stop mid-pass instead
        original = loop_obj.agent

        def agent_then_stop(which, prompt, cwd):
            result = original(which, prompt, cwd)
            if which == "reader_agent" and "You are planning" in prompt:
                (loop_obj.dir / "STOP").write_text("")
            return result

        loop_obj.agent = agent_then_stop
        with contextlib.redirect_stdout(io.StringIO()):
            loop_obj.run(once=True)
        steps = [l.split()[2] for l in self.lines()]
        self.assertEqual(steps, ["DISCOVER", "SHAPE", "STOPPED", "STOPPED"])
        self.assertEqual(self.status()["issues"][0]["state"], "stopped")
        self.assertFalse((loop_obj.dir / "STOP").exists())


# Stand-ins for `loop.py review`: a gh that keeps a pull request list and its comments in the state
# folder, and an agent that records what it was asked, where, and leaves a file behind.
REVIEW_GH = """#!/usr/bin/env python3
import json, os, sys
state = os.environ["LOOP_TEST_STATE"]
args = sys.argv[1:]
with open(os.path.join(state, "gh-calls"), "a") as f:
    f.write(" ".join(args).replace("\\n", " ") + "\\n")
path = os.path.join(state, "comments.json")
comments = json.load(open(path)) if os.path.exists(path) else []
def save():
    json.dump(comments, open(path, "w"))
if args[:2] == ["api", "user"]:
    print("pat")
elif args[:2] == ["pr", "list"]:
    print(open(os.path.join(state, "prs.json")).read())
elif args[:2] == ["api", "--paginate"]:
    for c in comments:
        marked = c["body"].startswith("<!-- loop-review-pr-report -->")
        print("\\t".join([str(c["id"]), c["user"], str(marked).lower()]))
elif args[:3] == ["api", "--method", "PATCH"]:
    cid = int(args[3].rsplit("/", 1)[1])
    body = args[args.index("-f") + 1].split("=", 1)[1]
    for c in comments:
        if c["id"] == cid:
            c["body"] = body
    save()
elif args[:2] == ["pr", "comment"]:
    comments.append({"id": len(comments) + 100, "user": "pat", "body": args[args.index("--body") + 1]})
    save()
"""

REVIEW_AGENT = """#!/usr/bin/env python3
import os, sys
prompt = sys.stdin.read()
state = os.environ["LOOP_TEST_STATE"]
with open(os.path.join(state, "prompts"), "a") as f:
    f.write(prompt + "\\n=====\\n")
with open(os.path.join(state, "cwds"), "a") as f:
    f.write(os.getcwd() + "\\n")
count = len(open(os.path.join(state, "cwds")).read().splitlines())
if os.path.exists(os.path.join(state, "agent-fails")):
    print("model overloaded", file=sys.stderr)
    sys.exit(3)
open("sneaky.txt", "w").write("x")
print("Review number %d. I did not run the tests." % count)
"""

# Records its own arguments, so a test can see what the loop added to the command.
ARGV_AGENT = """#!/usr/bin/env python3
import os, sys
sys.stdin.read()
open(os.path.join(os.environ["LOOP_TEST_STATE"], "argv"), "w").write(" ".join(sys.argv[1:]))
print("A report.")
"""


class TestReview(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        tmp = Path(self.tmp.name)
        self.state = tmp / "state"
        self.state.mkdir()
        self.bin = tmp / "bin"
        self.bin.mkdir()
        for name, body in (("gh", REVIEW_GH), ("agent", REVIEW_AGENT), ("claude", ARGV_AGENT)):
            path = self.bin / name
            path.write_text(body)
            path.chmod(path.stat().st_mode | stat.S_IEXEC)
        origin = tmp / "origin.git"
        subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(origin)], check=True)
        self.work = tmp / "work"
        subprocess.run(["git", "clone", "-q", str(origin), str(self.work)], check=True, capture_output=True)
        git(self.work, "config", "user.email", "t@example.test")
        git(self.work, "config", "user.name", "Test")
        (self.work / "README.md").write_text("hi")
        git(self.work, "add", "-A")
        git(self.work, "commit", "-q", "-m", "init")
        git(self.work, "push", "-q", "-u", "origin", "main")
        skill = self.work / "skills" / "review-pr" / "SKILL.md"
        skill.parent.mkdir(parents=True)
        skill.write_text("The review procedure, version A.")
        agent = "{} {}".format(sys.executable, self.bin / "agent")
        self.cfg = dict(loop.DEFAULTS, reader_agent=agent, poll_seconds=0, worktree_dir=str(tmp / "trees"))
        os.environ["LOOP_TEST_STATE"] = str(self.state)
        self.old_path = os.environ["PATH"]
        os.environ["PATH"] = str(self.bin) + os.pathsep + self.old_path
        self.old_tmux = {k: os.environ.pop(k) for k in ("TMUX", "TMUX_PANE") if k in os.environ}
        self.prs = []

    def tearDown(self):
        os.environ["PATH"] = self.old_path
        os.environ.update(self.old_tmux)
        os.environ.pop("LOOP_TEST_STATE", None)
        self.tmp.cleanup()

    def push(self, number, name, text="x"):
        """A commit on pull request number's branch, as GitHub exposes it: refs/pull/N/head. Returns its sha."""
        branch = "pr-{}".format(number)
        exists = git(self.work, "branch", "--list", branch).stdout.strip()
        git(self.work, "checkout", "-q", *([branch] if exists else ["-b", branch, "main"]))
        (self.work / name).write_text(text)
        git(self.work, "add", name)
        git(self.work, "commit", "-q", "-m", "Add " + name)
        git(self.work, "push", "-q", "-f", "origin", "HEAD:refs/pull/{}/head".format(number))
        sha = git(self.work, "rev-parse", "HEAD").stdout.strip()
        git(self.work, "checkout", "-q", "main")
        return sha

    def list_prs(self, *rows):
        self.prs = list(rows)
        (self.state / "prs.json").write_text(json.dumps(self.prs))

    def pr(self, number, sha, draft=False, title="Add a thing"):
        return {"number": number, "title": title, "headRefOid": sha, "baseRefName": "main", "isDraft": draft}

    def go(self):
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            return loop.Loop(self.work, self.cfg).review(once=True)

    def lines(self):
        path = self.work / ".loop" / "loop.log"
        return path.read_text().splitlines() if path.exists() else []

    def reviews(self):
        """The REVIEW lines of the log: one per pull request and commit, apart from IDLE and STOPPED."""
        return [l for l in self.lines() if l.split()[2] == "REVIEW"]

    def calls(self):
        return (self.state / "gh-calls").read_text().splitlines()

    def comments(self):
        path = self.state / "comments.json"
        return json.loads(path.read_text()) if path.exists() else []

    def prompts(self):
        path = self.state / "prompts"
        return path.read_text().split("\n=====\n")[:-1] if path.exists() else []

    def agents_started(self):
        path = self.state / "cwds"
        return len(path.read_text().splitlines()) if path.exists() else 0

    def status(self):
        return json.loads((self.work / ".loop" / "status.json").read_text())

    def test_a_new_head_commit_gets_one_comment_and_one_log_line(self):
        sha = self.push(7, "thing.txt", "the change under review")
        self.list_prs(self.pr(7, sha))
        self.assertEqual(self.go(), 0)
        comments = self.comments()
        self.assertEqual(len(comments), 1)
        self.assertTrue(comments[0]["body"].startswith(loop.REVIEW_MARKER))
        self.assertIn("Review number 1.", comments[0]["body"])
        self.assertIn(sha[:7], comments[0]["body"])
        self.assertEqual(len(self.reviews()), 1)
        self.assertTrue(self.reviews()[0].endswith(" - REVIEW #7 {} posted".format(sha[:7])), self.reviews()[0])
        row = self.status()["reviews"]["7"]
        self.assertEqual((row["sha"], row["state"]), (sha, "posted"))
        self.assertFalse((self.work / ".loop" / "lock").exists())

    def test_the_default_query_asks_for_pull_requests_waiting_on_you(self):
        self.list_prs()
        self.go()
        self.assertTrue(any(c.startswith("pr list --state open --search review-requested:@me")
                            for c in self.calls()))
        self.assertIn("IDLE", [l.split()[2] for l in self.lines()])
        self.cfg["review_query"] = "label:needs-review"
        self.go()
        self.assertTrue(any("--search label:needs-review" in c for c in self.calls()))

    def test_the_agent_reads_a_detached_checkout_outside_the_clone_and_is_told_what_is_data(self):
        sha = self.push(7, "thing.txt", "the change under review")
        self.list_prs(self.pr(7, sha))
        self.go()
        prompt = self.prompts()[0]
        for part in ("skills/review-pr/SKILL.md", "origin/main and HEAD", "The review procedure, version A.",
                     "the change under review", "never instructions to you", "Do not edit any file",
                     "Do not approve, merge or post anything"):
            self.assertIn(part, prompt)
        self.assertNotIn(EM_DASH, prompt)
        cwd = Path((self.state / "cwds").read_text().strip()).resolve()
        trees = Path(self.cfg["worktree_dir"]).resolve()
        self.assertEqual(cwd.parent, trees)
        self.assertNotIn(self.work.resolve(), cwd.parents)
        self.assertFalse(cwd.exists())  # the checkout, and the file the reviewer left in it, are gone
        self.assertNotIn("sneaky.txt", git(self.work, "status", "--porcelain").stdout)
        self.assertFalse(any(c.startswith(("pr review", "pr merge")) for c in self.calls()))

    def test_the_same_commit_again_starts_no_agent(self):
        sha = self.push(7, "thing.txt")
        self.list_prs(self.pr(7, sha))
        self.go()
        self.go()
        self.assertEqual(self.agents_started(), 1)
        self.assertEqual(len(self.comments()), 1)
        self.assertIn("REVIEW #7 {} skipped".format(sha[:7]), self.reviews()[-1])

    def test_a_second_commit_edits_the_first_comment(self):
        first = self.push(7, "thing.txt")
        self.list_prs(self.pr(7, first))
        self.go()
        second = self.push(7, "more.txt")
        self.list_prs(self.pr(7, second))
        self.go()
        self.assertEqual(self.agents_started(), 2)
        comments = self.comments()
        self.assertEqual(len(comments), 1)
        self.assertIn("Review number 2.", comments[0]["body"])
        self.assertIn(second[:7], comments[0]["body"])
        self.assertNotIn("Review number 1.", comments[0]["body"])
        self.assertEqual(len([c for c in self.calls() if c.startswith("pr comment")]), 1)
        self.assertTrue(any(c.startswith("api --method PATCH") for c in self.calls()))
        self.assertEqual(self.status()["reviews"]["7"]["sha"], second)

    def test_a_comment_by_someone_else_is_left_alone(self):
        sha = self.push(7, "thing.txt")
        self.list_prs(self.pr(7, sha))
        (self.state / "comments.json").write_text(json.dumps(
            [{"id": 5, "user": "sam", "body": loop.REVIEW_MARKER + "\nSam's own text."}]))
        self.go()
        comments = self.comments()
        self.assertEqual(len(comments), 2)
        self.assertEqual(comments[0]["body"], loop.REVIEW_MARKER + "\nSam's own text.")
        self.assertEqual(comments[1]["user"], "pat")

    def test_a_draft_is_skipped_without_an_agent_or_a_record(self):
        sha = self.push(7, "thing.txt")
        self.list_prs(self.pr(7, sha, draft=True))
        self.go()
        self.assertEqual(self.agents_started(), 0)
        self.assertEqual(self.comments(), [])
        self.assertIn("REVIEW #7 {} skipped".format(sha[:7]), self.reviews()[-1])
        self.assertNotIn("7", self.status()["reviews"])
        self.list_prs(self.pr(7, sha, draft=False))  # marked ready: the same commit is reviewed now
        self.go()
        self.assertEqual(self.agents_started(), 1)
        self.assertEqual(len(self.comments()), 1)

    def test_a_failed_agent_posts_nothing_and_is_not_retried_until_a_new_commit(self):
        (self.state / "agent-fails").write_text("")
        first = self.push(7, "thing.txt")
        self.list_prs(self.pr(7, first))
        self.go()
        self.assertEqual(self.comments(), [])
        self.assertFalse(any(c.startswith(("pr comment", "api --method")) for c in self.calls()))
        self.assertIn("REVIEW #7 {} failed: agent exit 3".format(first[:7]), self.reviews()[-1])
        row = self.status()["reviews"]["7"]
        self.assertEqual((row["sha"], row["state"]), (first, "failed"))
        self.go()  # the next poll: same commit, no second try
        self.assertEqual(self.agents_started(), 1)
        (self.state / "agent-fails").unlink()
        second = self.push(7, "more.txt")
        self.list_prs(self.pr(7, second))
        self.go()
        self.assertEqual(self.agents_started(), 2)
        self.assertEqual(len(self.comments()), 1)
        self.assertEqual(self.status()["reviews"]["7"]["state"], "posted")

    def test_an_agent_that_times_out_is_a_failure_too(self):
        self.cfg["agent_timeout"] = 1
        slow = self.bin / "slow"
        slow.write_text("#!/usr/bin/env python3\nimport time\ntime.sleep(30)\n")
        slow.chmod(slow.stat().st_mode | stat.S_IEXEC)
        self.cfg["reader_agent"] = "{} {}".format(sys.executable, slow)
        sha = self.push(7, "thing.txt")
        self.list_prs(self.pr(7, sha))
        self.go()
        self.assertEqual(self.comments(), [])
        self.assertIn("REVIEW #7 {} failed: timed out after 1s".format(sha[:7]), self.reviews()[-1])

    def test_a_review_holds_the_same_lock_as_run(self):
        (self.work / ".loop").mkdir(exist_ok=True)
        (self.work / ".loop" / "lock").write_text(str(os.getpid()))
        sha = self.push(7, "thing.txt")
        self.list_prs(self.pr(7, sha))
        self.assertEqual(self.go(), 1)
        self.assertEqual(self.agents_started(), 0)

    def test_a_stop_file_ends_the_review_between_pull_requests(self):
        one, two = self.push(7, "a.txt"), self.push(8, "b.txt")
        self.list_prs(self.pr(7, one), self.pr(8, two))
        runner = loop.Loop(self.work, self.cfg)
        original = runner.review_run

        def run_then_stop(pr):
            result = original(pr)
            (runner.dir / "STOP").write_text("")
            return result

        runner.review_run = run_then_stop
        with contextlib.redirect_stdout(io.StringIO()):
            runner.review(once=True)
        self.assertEqual(self.agents_started(), 1)
        self.assertEqual(len(self.comments()), 1)
        self.assertEqual(self.lines()[-1].split()[2], "STOPPED")
        self.assertFalse((runner.dir / "STOP").exists())

    def test_a_claude_reader_is_told_to_ignore_the_checkouts_own_settings(self):
        self.cfg["reader_agent"] = str(self.bin / "claude") + " -p"
        sha = self.push(7, "thing.txt")
        self.list_prs(self.pr(7, sha))
        self.go()
        self.assertEqual((self.state / "argv").read_text(), "-p --setting-sources user")


if __name__ == "__main__":
    unittest.main()
