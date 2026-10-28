"""Run with: python3 -m unittest discover -s tests"""
import datetime
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import dashboard_data  # noqa: E402 (needs scripts/ on the path first)
import token_report  # noqa: E402 (same reason)
from usage_report import log_path  # noqa: E402 (same reason)

TODAY = datetime.date(2026, 10, 27)
SINCE = "2026-10-15"
LEAK = "sentinel-zq7"  # put in every field the output must never carry
NOW = datetime.datetime(2026, 10, 27, 12, 0, tzinfo=datetime.timezone.utc)
SYSTEM_PATH = "/usr/bin:/bin"  # for the fake gh's own commands; the real gh isn't on it


def check_run(status, conclusion):
    return {"__typename": "CheckRun", "name": "tests", "status": status, "conclusion": conclusion,
            "detailsUrl": "https://github.com/o/r/actions/runs/1?" + LEAK}


def commit_status(state):
    return {"__typename": "StatusContext", "context": "ci", "state": state,
            "targetUrl": "https://github.com/o/r/status?" + LEAK}


def pr(number, created, branch, draft=False, mergeable="MERGEABLE", rollup=()):
    """One row of gh pr list --json, with the fields dashboard_data asks for."""
    return {"number": number, "title": "PR {} {}".format(number, LEAK), "createdAt": created,
            "headRefName": branch, "isDraft": draft, "mergeable": mergeable, "statusCheckRollup": list(rollup)}


PRS = [pr(41, "2026-10-27T09:30:00Z", "loop/issue-264",
          rollup=[check_run("COMPLETED", "SUCCESS"), commit_status("SUCCESS")]),
       pr(42, "2026-10-25T12:00:00Z", "fix-typo", draft=True, mergeable="CONFLICTING",
          rollup=[check_run("COMPLETED", "SUCCESS"), check_run("COMPLETED", "FAILURE")]),
       pr(43, "2026-10-27T11:00:00Z", "loop/issue-7-old", mergeable="UNKNOWN",
          rollup=[check_run("COMPLETED", "SUCCESS"), check_run("IN_PROGRESS", "")]),
       pr(44, "2026-10-27T11:00:00Z", "loop/issue-8", rollup=[commit_status("PENDING")]),
       pr(45, "2026-10-27T11:00:00Z", "docs", rollup=[commit_status("ERROR"), check_run("QUEUED", "")]),
       pr(46, "2026-10-27T11:00:00Z", "docs-2")]


def fake_gh(folder, script):
    """A gh in folder that runs the shell script given, for PATH to find instead of the real one."""
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / "gh"
    path.write_text("#!/bin/sh\n" + script + "\n")
    path.chmod(0o755)

# A stand-in for gh, found on PATH. It logs each call, answers pr list from prs.json ([] when there's
# none) and pulls/<n>/commits from commits.json's pages for n, and exits 1 while a file named fail exists.
GH = """#!PYTHON
import json, os, sys
folder = FOLDER
args = sys.argv[1:]
with open(os.path.join(folder, "calls"), "a") as f:
    f.write(" ".join(args) + "\\n")
if os.path.exists(os.path.join(folder, "fail")):
    sys.exit(1)
if args[:2] == ["pr", "list"]:
    path = os.path.join(folder, "prs.json")
    print(open(path).read() if os.path.exists(path) else "[]")
elif args[:1] == ["api"]:
    for page in json.load(open(os.path.join(folder, "commits.json")))[args[1].split("/")[-2]]:
        print(json.dumps(page))
else:
    sys.exit(1)
"""


def run(started, step, model, tokens, cost):
    """One usage.json entry, the shape loop.py's record_usage() writes."""
    return {"step": step, "round": 1, "run_started": started, "reported": True, "model": model,
            "input_tokens": tokens, "output_tokens": 0, "cache_write_tokens": 0, "cache_read_tokens": 0,
            "cost_usd": cost}


def write(folder, relative, content):
    path = Path(folder) / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content if isinstance(content, str) else json.dumps(content))
    return path


class Harness(unittest.TestCase):
    """A temporary harness root, empty until a test fills it."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name).resolve() / ("harness-" + LEAK)
        self.root.mkdir()
        self.transcripts = Path(tmp.name).resolve() / "transcripts"  # not there until a test writes one
        # A gh that fails unless a test says otherwise, so no test reaches the real one.
        self.bin = Path(tmp.name).resolve() / "bin"
        fake_gh(self.bin, "exit 1")
        patcher = mock.patch.dict(os.environ, {"PATH": str(self.bin) + os.pathsep + SYSTEM_PATH})
        patcher.start()
        self.addCleanup(patcher.stop)

    def gh(self, prs):
        """Make gh print prs as gh pr list --json would."""
        write(self.bin, "prs.json", prs)
        fake_gh(self.bin, 'cat "{}"'.format(self.bin / "prs.json"))

    def fill(self):
        write(self.root, ".loop/issue-7/usage.json", [
            run("2026-10-27T09:00:00", "plan", "claude-a", 100, 1.0),
            run("2026-10-27T09:00:00", "build", None, 200, 0.5),
            run("2026-10-22T09:00:00", "plan", "claude-a", 10, 0.25)])
        write(self.root, ".loop/issue-9/usage.json", [
            run("2026-10-16T09:00:00", "plan", "claude-b", 1000, 2.0),
            run("2026-10-01T09:00:00", "plan", "claude-b", 5000, 9.0)])
        write(self.root, ".loop/projects/app/issue-3/usage.json", [
            run("2026-10-27T10:00:00", "review", "claude-a", 5, 0.25)])
        write(self.root, ".loop/status.json", {"queue": [], "issues": [
            {"number": 7, "title": LEAK, "state": "pr", "round": 2, "note": LEAK,
             "pr": "https://github.com/o/r/pull/1?" + LEAK},
            {"number": 9, "title": LEAK, "state": "blocked", "round": 3, "pr": None, "note": LEAK},
            {"number": 12, "title": "", "state": "building", "round": 1, "pr": None, "note": ""}]})
        write(self.root, ".loop/projects/app/status.json", {"issues": [
            {"number": 3, "title": LEAK, "state": "pr", "round": 1, "pr": "https://github.com/o/app/pull/4"}]})
        lines = [{"ts": "2026-10-20T10:00:00Z", "event": "skill", "name": "review-pr"},
                 {"ts": "2026-10-21T10:00:00Z", "event": "skill", "name": "review-pr"},
                 {"ts": "2026-10-21T10:00:00Z", "event": "skill", "name": "learn"},
                 {"ts": "2026-10-21T10:00:00Z", "event": "agent", "name": "reviewer"},
                 {"ts": "2026-10-21T10:00:00Z", "event": "command", "name": "standup", "prompt": LEAK},
                 {"ts": "2026-10-22T10:00:00Z", "event": "guard_deny", "rule": "credential-file"},
                 {"ts": "2026-10-22T10:00:00Z", "event": "guard_deny", "rule": "credential-file"},
                 {"ts": "2026-10-22T10:00:00Z", "event": "guard_ask", "rule": "connector-write",
                  "tool": "mcp__" + LEAK},
                 {"ts": "2026-10-01T10:00:00Z", "event": "skill", "name": "too-old"}]
        write(log_path(self.root).parent, log_path(self.root).name,
              "\n".join(json.dumps(l) for l in lines) + "\nnot json\n")
        saved = {"agent": "claude --" + LEAK, "folder": str(self.root / LEAK)}
        write(self.root, ".harness/evals/2026-10-20T0900-reviewer.json",
              dict(saved, reviewer="reviewer", saved="2026-10-20T09:00:00+00:00",
                   cases={"01-a": {"status": "failing", "reasons": ["missed: " + LEAK]}}))
        write(self.root, ".harness/evals/2026-10-25T0900-reviewer.json",
              dict(saved, reviewer="reviewer", saved="2026-10-25T09:00:00+00:00",
                   cases={"01-a": {"status": "stable", "reasons": []},
                          "02-b": {"status": "flaky", "reasons": ["missed: " + LEAK]},
                          "03-c": {"status": "failing", "reasons": ["missed: " + LEAK]}}))
        write(self.root, ".harness/evals/2026-10-26T0900-security-reviewer.json",
              dict(saved, reviewer="security-reviewer", saved="2026-10-26T09:00:00+00:00",
                   cases={"01-x": {"status": "stable", "reasons": []}}))
        write(self.root, ".harness/evals/2026-10-27T0900-broken.json", "not json")

    def build(self, since=SINCE):
        return dashboard_data.build(self.root, since, TODAY, NOW, projects_dir=self.transcripts)

    def main(self, *args):
        out = io.StringIO()
        with redirect_stdout(out):
            code = dashboard_data.main(["--json", "--since", SINCE, *args], root=self.root,
                                       projects_dir=self.transcripts)
        return code, out.getvalue()


class Layout(Harness):
    def test_the_top_level_keys(self):
        self.fill()
        code, out = self.main()
        self.assertEqual(code, 0)
        found = json.loads(out)
        self.assertEqual(list(found), ["generated", "since", "loop_spend", "loop_throughput", "activity", "evals",
                                       "conversations", "waiting", "loop_rework"])
        self.assertEqual(found["since"], SINCE)
        self.assertIsNotNone(datetime.datetime.fromisoformat(found["generated"]).tzinfo)

    def test_without_json_it_refuses(self):
        with self.assertRaises(SystemExit) as raised, redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            dashboard_data.main([], root=self.root)
        self.assertEqual(raised.exception.code, 2)


class Spend(Harness):
    def test_today_the_last_7_days_and_since(self):
        self.fill()
        spend = self.build()["loop_spend"]
        self.assertEqual(spend["today"], {"tokens": 305, "cost_usd": 1.75})
        self.assertEqual(spend["last_7_days"], {"tokens": 315, "cost_usd": 2.0})
        self.assertEqual(spend["since"], {"tokens": 1315, "cost_usd": 4.0})
        self.assertEqual(spend["by_issue"], {"app/issue-3": {"tokens": 5, "cost_usd": 0.25},
                                             "issue-7": {"tokens": 310, "cost_usd": 1.75},
                                             "issue-9": {"tokens": 1000, "cost_usd": 2.0}})
        self.assertEqual(spend["by_step"], {"build": {"tokens": 200, "cost_usd": 0.5},
                                            "plan": {"tokens": 1110, "cost_usd": 3.25},
                                            "review": {"tokens": 5, "cost_usd": 0.25}})

    def test_by_model_puts_an_unrecorded_model_under_null(self):
        self.fill()
        self.assertEqual(self.build()["loop_spend"]["by_model"], {
            "claude-a": {"tokens": 115, "cost_usd": 1.5, "label": "claude-a"},
            "claude-b": {"tokens": 1000, "cost_usd": 2.0, "label": "claude-b"},
            "null": {"tokens": 200, "cost_usd": 0.5, "label": "model not recorded"}})

    def test_a_since_inside_the_week_still_gives_the_whole_week(self):
        self.fill()
        spend = self.build(since="2026-10-26")["loop_spend"]
        self.assertEqual(spend["last_7_days"], {"tokens": 315, "cost_usd": 2.0})
        self.assertEqual(spend["since"], {"tokens": 305, "cost_usd": 1.75})
        self.assertEqual(spend["by_issue"]["issue-7"], {"tokens": 300, "cost_usd": 1.5})

    def test_odd_numbers_in_a_record_are_left_out_not_counted(self):
        write(self.root, ".loop/issue-1/usage.json", [
            dict(run("2026-10-27T09:00:00", "plan", "m", 10, True), output_tokens="lots"),
            run("2026-10-27T09:00:00", "plan", "m", 5, "free")])
        self.assertEqual(self.build()["loop_spend"]["today"], {"tokens": 15, "cost_usd": None})


class SpendByDay(Harness):
    def test_every_day_from_since_to_today_with_zero_on_a_day_without_a_run(self):
        self.fill()
        spend = self.build()["loop_spend"]
        self.assertEqual([d["day"] for d in spend["by_day"]],
                         ["2026-10-{}".format(n) for n in range(15, 28)])
        found = {d["day"]: {"tokens": d["tokens"], "cost_usd": d["cost_usd"]} for d in spend["by_day"]}
        self.assertEqual(found["2026-10-16"], {"tokens": 1000, "cost_usd": 2.0})
        self.assertEqual(found["2026-10-22"], {"tokens": 10, "cost_usd": 0.25})
        self.assertEqual(found["2026-10-27"], {"tokens": 305, "cost_usd": 1.75})
        self.assertEqual(found["2026-10-20"], {"tokens": 0, "cost_usd": 0.0})
        self.assertEqual({"tokens": sum(d["tokens"] for d in found.values()),
                          "cost_usd": round(sum(d["cost_usd"] for d in found.values()), 4)}, spend["since"])

    def test_first_run_is_the_earliest_day_counted_and_ignores_a_run_before_since(self):
        self.fill()  # issue-9 also ran on 2026-10-01, before SINCE
        self.assertEqual(self.build()["loop_spend"]["first_run"], "2026-10-16")
        self.assertEqual(self.build(since="2026-10-26")["loop_spend"]["first_run"], "2026-10-27")

    def test_a_day_whose_runs_recorded_no_cost_has_cost_null(self):
        write(self.root, ".loop/issue-7/usage.json", [run("2026-10-20T09:00:00", "plan", "m", 10, None)])
        found = {d["day"]: d for d in self.build()["loop_spend"]["by_day"]}
        self.assertEqual(found["2026-10-20"], {"day": "2026-10-20", "tokens": 10, "cost_usd": None})

    def test_a_run_dated_after_today_counts_in_since_but_has_no_day(self):
        self.fill()
        write(self.root, ".loop/issue-11/usage.json", [run("2026-10-28T09:00:00", "plan", "m", 7, 0.5)])
        spend = self.build()["loop_spend"]
        self.assertEqual(spend["by_day"][-1]["day"], "2026-10-27")
        self.assertEqual(spend["since"], {"tokens": 1315 + 7, "cost_usd": 4.0 + 0.5})
        self.assertEqual(sum(d["tokens"] for d in spend["by_day"]), 1315)

    def test_no_run_counted_gives_no_first_run_and_every_day_zero(self):
        write(self.root, ".loop/issue-7/usage.json", [run("2026-09-01T09:00:00", "plan", "m", 10, 1.0)])
        spend = self.build()["loop_spend"]
        self.assertIsNone(spend["first_run"])
        self.assertEqual(len(spend["by_day"]), 13)
        self.assertTrue(all((d["tokens"], d["cost_usd"]) == (0, 0.0) for d in spend["by_day"]))


class CostPerPr(Harness):
    def test_the_since_cost_over_the_issues_with_a_pull_request(self):
        self.fill()
        self.assertEqual(self.build()["loop_spend"]["cost_per_pr"], 2.0)

    def test_only_issues_that_ran_in_the_period_and_status_json_lists(self):
        self.fill()
        # #5 has a pull request but no run since SINCE; #11 ran but has dropped off status.json.
        found = json.loads((self.root / ".loop" / "status.json").read_text())
        found["issues"].append({"number": 5, "state": "pr", "round": 1, "pr": "https://github.com/o/r/pull/2"})
        write(self.root, ".loop/status.json", found)
        write(self.root, ".loop/issue-5/usage.json", [run("2026-10-01T09:00:00", "plan", "claude-a", 1, 8.0)])
        write(self.root, ".loop/issue-11/usage.json", [run("2026-10-20T09:00:00", "plan", "claude-a", 1, 6.0)])
        self.assertEqual(self.build()["loop_spend"]["cost_per_pr"], 2.0)

    def test_no_pull_request_gives_null(self):
        self.fill()
        write(self.root, ".loop/status.json", {"issues": [{"number": 7, "state": "blocked", "pr": None}]})
        write(self.root, ".loop/projects/app/status.json", {"issues": []})
        self.assertIsNone(self.build()["loop_spend"]["cost_per_pr"])

    def test_no_status_json_leaves_spend_but_not_cost_per_pr(self):
        self.fill()
        (self.root / ".loop" / "status.json").unlink()
        (self.root / ".loop" / "projects" / "app" / "status.json").unlink()
        spend = self.build()["loop_spend"]
        self.assertEqual(spend["since"], {"tokens": 1315, "cost_usd": 4.0})
        self.assertIsNone(spend["cost_per_pr"])


class Throughput(Harness):
    def test_states_rounds_and_repeats_across_the_harness_and_projects(self):
        self.fill()
        self.assertEqual(self.build()["loop_throughput"], {
            "issues": 4, "by_state": {"pr": 2, "blocked": 1, "building": 1},
            "rounds": {"app/issue-3": 1, "issue-7": 2, "issue-9": 3, "issue-12": 1},
            "more_than_one_round": 2})


class Activity(Harness):
    def test_counts_by_name_rule_and_asks_since_the_date(self):
        self.fill()
        self.assertEqual(self.build()["activity"], {
            "skills": {"review-pr": 2, "learn": 1}, "agents": {"reviewer": 1}, "commands": {"standup": 1},
            "guard_refusals": {"credential-file": 2}, "asks": 1})


class Evals(Harness):
    def test_the_newest_file_for_each_reviewer(self):
        self.fill()
        gone = {"stale": True, "changed": [], "newest_change": None, "why": "folder missing"}
        self.assertEqual(self.build()["evals"], {
            "reviewer": dict(gone, saved="2026-10-25T09:00:00+00:00", stable=1, flaky=1, failing=1,
                             failing_cases=["03-c"]),
            "security-reviewer": dict(gone, saved="2026-10-26T09:00:00+00:00", stable=1, flaky=0, failing=0,
                                      failing_cases=[])})


class StaleEvals(Harness):
    """A saved result in a git repo holding the files its one case rests on, all committed before it was saved."""

    SAVED = "2026-10-25T09:00:00+00:00"

    def setUp(self):
        super().setUp()
        env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
        env.update(GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1")
        patched = mock.patch.dict(os.environ, env, clear=True)
        patched.start()
        self.addCleanup(patched.stop)
        self.git("init", "-q")
        write(self.root, "agents/reviewer.md", "the reviewer\n")
        write(self.root, "scripts/eval_agents.py", "# the eval\n")
        write(self.root, "briefs/proposal.md", "the brief\n")
        write(self.root, "evals/01-x/case.json", {"agent": "reviewer", "brief": "briefs/proposal.md"})
        write(self.root, "evals/01-x/work.md", "the work\n")
        write(self.root, "notes.md", "read by no case\n")
        self.commit("2026-10-20T09:00:00+00:00")
        self.save("reviewer")

    def git(self, *args, date=None):
        env = dict(os.environ, GIT_AUTHOR_DATE=date, GIT_COMMITTER_DATE=date) if date else None
        return subprocess.run(["git", "-C", str(self.root), "-c", "user.name=t", "-c", "user.email=t@example.com",
                               *args], check=True, capture_output=True, text=True, env=env).stdout

    def commit(self, date):
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "change", date=date)
        # The tests turn on this date, so a commit git dated otherwise fails here rather than as a fresh result.
        # Some versions of git print UTC as Z and others as +00:00, so the times are compared, not the text.
        self.assertEqual(dashboard_data.when(self.git("log", "-1", "--format=%cI").strip()),
                         dashboard_data.when(date))

    def save(self, reviewer, **fields):
        result = {"reviewer": reviewer, "folder": "evals", "saved": self.SAVED, "cases": {"01-x": {"status": "stable"}}}
        write(self.root, ".harness/evals/2026-10-25T0900-{}.json".format(reviewer), dict(result, **fields))

    def stale(self, reviewer="reviewer"):
        found = self.build()["evals"][reviewer]
        return {k: found[k] for k in ("stale", "changed", "newest_change", "why") if k in found}

    def test_files_last_committed_before_it_was_saved_leave_it_fresh(self):
        write(self.root, "notes.md", "changed, but no case reads it\n")
        self.commit("2026-10-26T09:00:00+00:00")
        self.assertEqual(self.stale(), {"stale": False, "changed": [], "newest_change": None})

    def test_a_commit_to_the_brief_after_it_was_saved_makes_it_stale(self):
        write(self.root, "briefs/proposal.md", "the brief, rewritten\n")
        self.commit("2026-10-26T09:00:00+00:00")
        self.assertEqual(self.stale(), {"stale": True, "changed": ["briefs/proposal.md"],
                                        "newest_change": "2026-10-26T09:00:00+00:00"})

    def test_an_uncommitted_edit_to_the_work_makes_it_stale(self):
        work = write(self.root, "evals/01-x/work.md", "the work, edited\n")
        written = datetime.datetime(2026, 10, 26, 12, 0, tzinfo=datetime.timezone.utc)
        os.utime(work, (written.timestamp(), written.timestamp()))
        found = self.stale()
        self.assertEqual((found["stale"], found["changed"]), (True, ["evals/01-x/work.md"]))
        self.assertEqual(datetime.datetime.fromisoformat(found["newest_change"]), written)

    def test_changed_names_each_file_from_the_root_and_newest_change_the_latest_commit(self):
        write(self.root, "evals/01-x/work.md", "the work, edited\n")
        self.commit("2026-10-26T09:00:00+00:00")
        write(self.root, "briefs/proposal.md", "the brief, rewritten\n")
        self.commit("2026-10-27T09:00:00+00:00")
        self.assertEqual(self.stale(), {"stale": True, "changed": ["briefs/proposal.md", "evals/01-x/work.md"],
                                        "newest_change": "2026-10-27T09:00:00+00:00"})
        self.assertNotIn(str(self.root), json.dumps(self.build()))

    def test_a_missing_folder_or_saved_time_stays_with_its_why(self):
        self.save("reviewer", folder="nowhere")
        self.save("security-reviewer", saved=None)
        self.assertEqual(self.stale(), {"stale": True, "changed": [], "newest_change": None, "why": "folder missing"})
        self.assertEqual(self.stale("security-reviewer"),
                         {"stale": True, "changed": [], "newest_change": None, "why": "no saved time"})

    def test_a_commit_dated_with_z_after_it_was_saved_makes_it_stale(self):
        # git prints Z on some versions, and fromisoformat() before Python 3.11 refuses it.
        write(self.root, "briefs/proposal.md", "the brief, rewritten\n")
        self.commit("2026-10-26T09:00:00Z")
        self.assertEqual(self.stale(), {"stale": True, "changed": ["briefs/proposal.md"],
                                        "newest_change": "2026-10-26T09:00:00+00:00"})

    def test_a_brief_git_ignores_written_after_it_was_saved_makes_it_stale(self):
        write(self.root, ".gitignore", "briefs/\n")
        self.git("rm", "-r", "-q", "--cached", "briefs")
        self.commit("2026-10-21T09:00:00+00:00")
        brief = self.root / "briefs" / "proposal.md"
        written = datetime.datetime(2026, 10, 26, 12, 0, tzinfo=datetime.timezone.utc)
        os.utime(brief, (written.timestamp(), written.timestamp()))
        found = self.stale()
        self.assertEqual((found["stale"], found["changed"]), (True, ["briefs/proposal.md"]))

    def test_a_reviewer_that_isnt_a_string_doesnt_stop_the_check(self):
        found = dashboard_data.freshness(self.root, {"reviewer": ["a"], "folder": "evals", "saved": self.SAVED})
        self.assertEqual(found, {"stale": False, "changed": [], "newest_change": None})

    def test_without_git_stale_is_null(self):
        shutil.rmtree(self.root / ".git")
        self.assertEqual(self.stale(), {"stale": None, "changed": [], "newest_change": None, "why": "no git"})


class When(unittest.TestCase):
    def test_a_trailing_z_is_utc_on_every_python(self):
        self.assertEqual(dashboard_data.when("2026-10-20T09:00:00Z"),
                         datetime.datetime(2026, 10, 20, 9, 0, tzinfo=datetime.timezone.utc))

    def test_anything_else_that_isnt_a_time_is_none(self):
        for text in (None, 3, "", "Z", "not a time"):
            self.assertIsNone(dashboard_data.when(text), text)


class PullRequests(Harness):
    def test_each_open_pull_request_with_its_wait_branch_draft_checks_and_conflicts(self):
        self.gh(PRS)
        found = self.build()["waiting"]["pull_requests"]
        self.assertEqual([(p["number"], p["loop_issue"], p["draft"], p["checks"], p["conflicts"]) for p in found], [
            (41, 264, False, "pass", False),
            (42, None, True, "fail", True),
            (43, None, False, "pending", None),
            (44, 8, False, "pending", False),
            (45, None, False, "fail", False),
            (46, None, False, None, False)])

    def test_title_opened_and_hours_waited_against_now(self):
        self.gh(PRS[:2])
        found = self.build()["waiting"]["pull_requests"]
        self.assertEqual(found[0], {"number": 41, "title": "PR 41 " + LEAK, "opened": "2026-10-27T09:30:00Z",
                                    "hours_waited": 2.5, "loop_issue": 264, "draft": False, "checks": "pass",
                                    "conflicts": False})
        self.assertEqual(found[1]["hours_waited"], 48.0)

    def test_no_open_pull_requests_is_an_empty_list(self):
        self.gh([])
        self.assertEqual(self.build()["waiting"]["pull_requests"], [])


class Blocked(Harness):
    def test_blocked_issues_with_title_note_and_update(self):
        self.fill()
        self.assertEqual(self.build()["waiting"]["blocked"], [
            {"issue": "issue-9", "number": 9, "title": LEAK, "note": LEAK, "updated": None}])

    def test_a_project_issue_carries_its_prefix(self):
        self.fill()
        write(self.root, ".loop/projects/app/status.json", {"issues": [
            {"number": 3, "state": "pr", "round": 1},
            {"number": 5, "title": "Stuck", "state": "blocked", "round": 2, "note": "tests failed twice",
             "updated": "2026-10-26T15:00:00", "pr": "https://github.com/o/app/pull/6"}]})
        self.assertEqual(self.build()["waiting"]["blocked"], [
            {"issue": "app/issue-5", "number": 5, "title": "Stuck", "note": "tests failed twice",
             "updated": "2026-10-26T15:00:00"},
            {"issue": "issue-9", "number": 9, "title": LEAK, "note": LEAK, "updated": None}])


class GhUnavailable(Harness):
    def assert_unavailable_but_blocked_filled(self):
        found = self.build()["waiting"]
        self.assertEqual(found["pull_requests"], {"value": None, "why": "gh unavailable"})
        self.assertEqual([b["issue"] for b in found["blocked"]], ["issue-9"])

    def test_gh_missing(self):
        self.fill()
        empty = self.root.parent / "empty"
        empty.mkdir()
        with mock.patch.dict(os.environ, {"PATH": str(empty)}):
            self.assert_unavailable_but_blocked_filled()

    def test_gh_failing_as_when_signed_out(self):
        self.fill()
        self.assert_unavailable_but_blocked_filled()

    def test_gh_printing_something_other_than_a_list(self):
        self.fill()
        for script in ("echo not json", "echo '{\"number\": 1}'"):
            with self.subTest(script=script):
                fake_gh(self.bin, script)
                self.assert_unavailable_but_blocked_filled()

    def test_gh_timing_out(self):
        self.fill()
        fake_gh(self.bin, "exec sleep 5")
        with mock.patch.object(dashboard_data, "GH_TIMEOUT", 0.2):
            self.assert_unavailable_but_blocked_filled()


def commit(message, parents=1):
    """One item from the pulls/<n>/commits API, the parts loop_rework reads and an author it mustn't keep."""
    return {"sha": "abc", "commit": {"message": message, "author": {"name": LEAK}},
            "parents": [{"sha": "p{}".format(i)} for i in range(parents)]}


class Rework(Harness):
    def setUp(self):
        super().setUp()
        # A gh that answers from files in self.bin and logs each call there, in place of the one that fails.
        fake = self.bin / "gh"
        fake.write_text(GH.replace("PYTHON", sys.executable).replace("FOLDER", repr(str(self.bin))))
        fake.chmod(0o755)
        loop = commit("Build it\n\nLoop: issue #1, round 1.")
        write(self.bin, "prs.json", [
            {"number": 101, "title": "All the loop's", "headRefName": "loop/issue-1", "mergedAt": "2026-10-20T12:00:00Z"},
            {"number": 102, "title": "Fixed by hand", "headRefName": "loop/issue-2", "mergedAt": "2026-10-21T12:00:00Z"},
            {"number": 103, "title": "Not the loop's", "headRefName": "feature/x", "mergedAt": "2026-10-22T12:00:00Z"},
            {"number": 104, "title": "Too old", "headRefName": "loop/issue-4", "mergedAt": "2026-10-01T12:00:00Z"}])
        # 102's commits come in two pages, as gh --paginate prints them.
        write(self.bin, "commits.json", {
            "101": [[loop, loop]],
            "102": [[loop, commit("Merge branch 'main' into loop/issue-2", parents=2)], [commit("fix " + LEAK)]],
            "103": [[commit("by hand")]], "104": [[commit("by hand")]]})

    def test_counts_the_loop_pull_requests_merged_since_and_the_reworked_ones(self):
        rework = self.build()["loop_rework"]
        self.assertEqual((rework["merged"], rework["reworked"]), (2, 1))

    def test_lists_each_reworked_pull_request_with_its_merges_and_other_commits(self):
        self.assertEqual(self.build()["loop_rework"]["pull_requests"], [
            {"number": 102, "title": "Fixed by hand", "merges_from_base": 1, "other_commits": 1}])

    def test_asks_gh_for_a_pull_requests_commits_once_and_caches_only_what_it_counts(self):
        first, second = self.build()["loop_rework"], self.build()["loop_rework"]
        self.assertEqual(first, second)
        calls = [c for c in (self.bin / "calls").read_text().splitlines() if "/commits" in c]
        self.assertEqual(sorted(c.split("/")[-2] for c in calls), ["101", "102"])
        cache = (self.root / ".harness" / "cache" / "loop_rework.json").read_text()
        self.assertEqual(sorted(json.loads(cache)), ["101", "102"])
        self.assertNotIn(LEAK, cache)

    def test_a_failed_fetch_keeps_the_commits_already_read_in_the_cache(self):
        commits = json.loads((self.bin / "commits.json").read_text())
        del commits["102"]  # the fake gh fails on 102, after reading 101
        write(self.bin, "commits.json", commits)
        self.assertEqual(self.build()["loop_rework"], {"value": None, "why": "gh failed"})
        cache = json.loads((self.root / ".harness" / "cache" / "loop_rework.json").read_text())
        self.assertEqual(sorted(cache), ["101"])

    def test_gh_failing_gives_null_and_why_and_exits_0(self):
        write(self.bin, "fail", "")
        code, out = self.main()
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["loop_rework"], {"value": None, "why": "gh failed"})


class MissingOrCorrupt(Harness):
    def test_every_source_missing_gives_null_and_why_and_exits_0(self):
        code, out = self.main()
        self.assertEqual(code, 0)
        found = json.loads(out)
        self.assertEqual(found["loop_spend"], {"value": None, "why": "no loop records"})
        self.assertEqual(found["loop_throughput"], {"value": None, "why": "no status.json"})
        self.assertEqual(found["activity"], {"value": None, "why": "no usage log"})
        self.assertEqual(found["evals"], {"value": None, "why": "no saved evals"})
        self.assertEqual(found["conversations"], {"value": None, "why": "no transcripts"})
        for section in ("loop_spend", "conversations"):
            self.assertNotIn("by_day", found[section], section)
        self.assertEqual(found["waiting"], {"pull_requests": {"value": None, "why": "gh unavailable"},
                                            "blocked": {"value": None, "why": "no status.json"}})

    def test_every_source_corrupt_gives_null_and_why_and_exits_0(self):
        write(self.root, ".loop/issue-7/usage.json", "not json")
        write(self.root, ".loop/projects/app/issue-3/usage.json", {"not": "a list"})
        write(self.root, ".loop/status.json", "not json")
        write(self.root, ".loop/projects/app/status.json", ["not", "an", "object"])
        write(log_path(self.root).parent, log_path(self.root).name, "not json\n[1, 2]\n")
        write(self.root, ".harness/evals/2026-10-25T0900-reviewer.json", "not json")
        write(self.root, ".harness/evals/2026-10-26T0900-reviewer.json", {"reviewer": "reviewer"})
        code, out = self.main()
        self.assertEqual(code, 0)
        found = json.loads(out)
        for section in ("loop_spend", "loop_throughput", "activity", "evals"):
            self.assertEqual(found[section], {"value": None, "why": "unreadable"}, section)

    def test_records_with_no_run_in_the_window_are_zero_not_missing(self):
        write(self.root, ".loop/issue-7/usage.json", [run("2026-09-01T09:00:00", "plan", "m", 10, 1.0)])
        spend = self.build()["loop_spend"]
        self.assertEqual(spend["since"], {"tokens": None, "cost_usd": None})
        self.assertEqual(spend["by_issue"], {})


def reply(cwd, n, id, session, model="m-a", ts="2026-10-20T12:00:00Z", sidechain=False):
    """One transcript line for a reply, the shape Claude Code writes, with n, 2n, 3n and 4n tokens."""
    return {"type": "assistant", "cwd": str(cwd), "sessionId": session, "timestamp": ts, "requestId": "req_" + id,
            "isSidechain": sidechain,
            "message": {"id": "msg_" + id, "model": model, "role": "assistant",
                        "usage": {"input_tokens": n, "output_tokens": 2 * n, "cache_creation_input_tokens": 3 * n,
                                  "cache_read_input_tokens": 4 * n},
                        "content": [{"type": "text", "text": "reply " + LEAK}]}}


def lines(folder, relative, entries):
    return write(folder, relative, "".join(json.dumps(e) + "\n" for e in entries))


class Stop(Exception):
    """Stands in for a read stopped part way, as when the pane's timeout kills it."""


class Conversations(Harness):
    """Transcripts beside the harness, and the loop's worktrees in a folder set by loop.json."""

    def setUp(self):
        super().setUp()
        # West of UTC, where an evening's replies carry tomorrow's UTC date, whatever the machine's zone.
        zone = os.environ.get("TZ")
        os.environ["TZ"] = "America/Los_Angeles"
        time.tzset()
        self.addCleanup(time.tzset)
        self.addCleanup(lambda: os.environ.pop("TZ", None) if zone is None else os.environ.__setitem__("TZ", zone))
        self.loop = self.root.parent / "loop-checkouts"
        write(self.root, "loop.json", {"worktree_dir": str(self.loop)})
        self.cache = self.root / ".harness" / "cache" / "conversations.json"
        prompt = {"type": "user", "cwd": str(self.root), "sessionId": "s1", "timestamp": "2026-10-20T11:00:00Z",
                  "message": {"role": "user", "content": "prompt " + LEAK}}
        first = reply(self.root, 1, "1", "s1")
        lines(self.transcripts, "a/s1.jsonl", [
            prompt, first, first, reply(self.root / "projects" / "app", 10, "2", "s1", model="m-b"),
            reply(self.root, 7, "old", "s1", ts="2026-10-01T12:00:00Z"),
            reply(self.root.parent / "elsewhere", 5, "out", "s9")])
        lines(self.transcripts, "a/s1/subagents/agent-x.jsonl", [reply(self.root, 100, "3", "s1", sidechain=True)])
        # The same reply again, as a resumed session copies it, then one from the loop.
        self.other = lines(self.transcripts, "b/s2.jsonl", [
            dict(first, sessionId="s3"), reply(self.loop / "issue-7" / "src", 1000, "4", "s2")])

    def conversations(self):
        return dashboard_data.conversations(self.root, SINCE, TODAY, self.transcripts, self.cache)

    def from_token_report(self):
        """What token_report.read() and group() make of the same transcripts, in the same shape."""
        by_model, sessions = {"harness": {}, "loop": {}}, {"harness": set(), "loop": set()}
        by_day = {side: dict.fromkeys(dashboard_data.days(SINCE, TODAY), 0) for side in by_model}
        for entry in token_report.read(self.transcripts, SINCE):
            found = token_report.group(entry, self.root, self.loop)
            if found is None:
                continue
            side = "loop" if found[0] == "Loop" else "harness"
            model = entry["message"]["model"]
            by_model[side][model] = [a + b for a, b in zip(by_model[side].get(model, [0, 0, 0, 0]),
                                                           token_report.tokens(entry))]
            day = datetime.datetime.fromisoformat(entry["timestamp"].replace("Z", "+00:00")).astimezone().date().isoformat()
            if day in by_day[side]:
                by_day[side][day] += sum(token_report.tokens(entry))
            sessions[side].add(entry["sessionId"])
        return {side: {"by_model": {m: dict(zip(dashboard_data.COUNTS, v), total=sum(v))
                                    for m, v in sorted(by_model[side].items())},
                       "sessions": len(sessions[side]),
                       "by_day": [{"day": d, "tokens": n} for d, n in by_day[side].items()]} for side in by_model}

    def test_tokens_by_side_and_model_counted_as_token_report_counts_them(self):
        found = self.conversations()

        def on_the_20th(tokens):
            return [{"day": d, "tokens": tokens if d == "2026-10-20" else 0} for d in dashboard_data.days(SINCE, TODAY)]

        self.assertEqual(found, {
            "harness": {"by_model": {"m-a": {"input": 101, "output": 202, "cache_writes": 303, "cache_reads": 404,
                                             "total": 1010},
                                     "m-b": {"input": 10, "output": 20, "cache_writes": 30, "cache_reads": 40,
                                             "total": 100}},
                        "sessions": 1, "by_day": on_the_20th(1110)},
            "loop": {"by_model": {"m-a": {"input": 1000, "output": 2000, "cache_writes": 3000, "cache_reads": 4000,
                                          "total": 10000}},
                     "sessions": 1, "by_day": on_the_20th(10000)}})
        self.assertEqual(found, self.from_token_report())

    def test_a_second_run_reads_only_the_transcript_that_changed(self):
        first = self.conversations()
        stat = self.other.stat()
        os.utime(self.other, ns=(stat.st_atime_ns, stat.st_mtime_ns + 1_000_000_000))
        with mock.patch.object(dashboard_data, "read_file", wraps=token_report.read_file) as reading:
            self.assertEqual(self.conversations(), first)
        self.assertEqual([call.args[0] for call in reading.call_args_list], [self.other])

    def stop_on_read(self, n):
        """read_file, raising Stop on the nth transcript read."""
        calls = []

        def reading(path, *args):
            calls.append(path)
            if len(calls) == n:
                raise Stop(path)
            return token_report.read_file(path, *args)
        return reading

    def test_a_read_stopped_part_way_keeps_what_it_read_and_the_next_read_finishes_it(self):
        with mock.patch.object(dashboard_data, "SAVE_EVERY", 1), \
                mock.patch.object(dashboard_data, "read_file", self.stop_on_read(3)):
            self.assertRaises(Stop, self.conversations)
        kept = json.loads(self.cache.read_text())
        self.assertEqual(len(kept), 2)
        self.assertNotIn(str(self.other), kept)
        with mock.patch.object(dashboard_data, "read_file", wraps=token_report.read_file) as reading:
            self.assertEqual(self.conversations(), self.from_token_report())
        self.assertEqual([call.args[0] for call in reading.call_args_list], [self.other])

    def test_a_save_part_way_keeps_the_earlier_caches_entries(self):
        self.conversations()
        before = json.loads(self.cache.read_text())[str(self.other)]
        for path in (self.transcripts / "a" / "s1.jsonl", self.other):
            stat = path.stat()
            os.utime(path, ns=(stat.st_atime_ns, stat.st_mtime_ns + 1_000_000_000))
        with mock.patch.object(dashboard_data, "SAVE_EVERY", 1), \
                mock.patch.object(dashboard_data, "read_file", self.stop_on_read(2)):
            self.assertRaises(Stop, self.conversations)
        self.assertEqual(json.loads(self.cache.read_text())[str(self.other)], before)

    def test_an_unchanged_read_leaves_the_cache_file_alone(self):
        self.conversations()
        inode = self.cache.stat().st_ino
        self.conversations()
        self.assertEqual(self.cache.stat().st_ino, inode)

    def test_a_cache_that_cant_be_read_or_has_the_wrong_shape_is_rebuilt(self):
        for junk in ("not json", "[1, 2]", json.dumps({str(self.other): {"size": "big", "replies": [[1]]}})):
            write(self.cache.parent, self.cache.name, junk)
            self.assertEqual(self.conversations(), self.from_token_report(), junk)
            self.assertIn(str(self.other), json.loads(self.cache.read_text()))

    def test_a_deleted_transcript_drops_out_of_the_cache_and_the_counts(self):
        self.conversations()
        self.other.unlink()
        found = self.conversations()
        self.assertNotIn(str(self.other), json.loads(self.cache.read_text()))
        self.assertEqual(found["loop"]["by_model"], {})
        self.assertEqual(found["loop"]["sessions"], 0)
        self.assertTrue(all(d["tokens"] == 0 for d in found["loop"]["by_day"]))
        self.assertEqual(found, self.from_token_report())

    def test_tokens_by_day_count_a_copied_reply_once_and_add_up_to_the_models(self):
        lines(self.transcripts, "c/s4.jsonl", [reply(self.root, 2, "5", "s4", ts="2026-10-25T08:00:00Z")])
        found = self.conversations()
        for side in ("harness", "loop"):
            self.assertEqual([d["day"] for d in found[side]["by_day"]], dashboard_data.days(SINCE, TODAY))
            self.assertEqual(sum(d["tokens"] for d in found[side]["by_day"]),
                             sum(m["total"] for m in found[side]["by_model"].values()), side)
        harness = {d["day"]: d["tokens"] for d in found["harness"]["by_day"]}
        # Reply 1 is in a/s1.jsonl twice and b/s2.jsonl once: 10 tokens, counted once.
        self.assertEqual(harness["2026-10-20"], 10 + 100 + 1000)
        self.assertEqual(harness["2026-10-25"], 20)
        self.assertEqual(harness["2026-10-21"], 0)
        self.assertEqual(harness["2026-10-15"], 0)
        self.assertEqual(found, self.from_token_report())

    def test_an_evening_reply_west_of_utc_counts_on_its_own_local_day(self):
        # 02:00 UTC on the 28th is 19:00 on the 27th in Los Angeles: today's last bar, not off the end.
        lines(self.transcripts, "c/s4.jsonl", [reply(self.root, 2, "5", "s4", ts="2026-10-28T02:00:00Z")])
        found = self.conversations()
        for side in ("harness", "loop"):
            self.assertEqual([d["day"] for d in found[side]["by_day"]], dashboard_data.days(SINCE, TODAY), side)
            self.assertEqual(sum(d["tokens"] for d in found[side]["by_day"]),
                             sum(m["total"] for m in found[side]["by_model"].values()), side)
        self.assertEqual(found["harness"]["by_day"][-1], {"day": "2026-10-27", "tokens": 20})
        self.assertEqual(found, self.from_token_report())

    def test_a_cache_from_before_local_days_is_read_again(self):
        old = [["1", "r", "2026-10-28", "harness", "m-a", "s1", 1, 2, 3, 4]]  # no local day
        stat = self.other.stat()
        write(self.cache.parent, self.cache.name,
              {str(self.other): {"size": stat.st_size, "mtime_ns": stat.st_mtime_ns, "replies": old}})
        self.assertEqual(self.conversations(), self.from_token_report())

    def test_by_day_runs_over_the_same_days_as_loop_spend(self):
        lines(self.transcripts, "c/s4.jsonl", [reply(self.root, 2, "5", "s4", ts="2026-10-28T02:00:00Z")])
        write(self.root, ".loop/issue-7/usage.json", [run("2026-10-22T09:00:00", "plan", "m", 10, 1.0)])
        found = self.build()
        spend = [d["day"] for d in found["loop_spend"]["by_day"]]
        for side in ("harness", "loop"):
            self.assertEqual([d["day"] for d in found["conversations"][side]["by_day"]], spend, side)

    def test_a_missing_transcripts_folder_gives_null_and_why(self):
        self.assertEqual(dashboard_data.conversations(self.root, SINCE, TODAY, self.transcripts / "missing",
                                                      self.cache),
                         {"value": None, "why": "no transcripts"})

    def test_no_prompt_reply_or_folder_reaches_the_output_or_the_cache(self):
        code, out = self.main()
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["conversations"]["loop"]["sessions"], 1)
        cache = self.cache.read_text()
        for text in (out, cache):
            for leak in (LEAK, str(self.root), str(self.loop)):
                self.assertNotIn(leak, text)


class Privacy(Harness):
    def test_titles_and_notes_only_under_waiting_and_no_address_prompt_reason_or_path_anywhere(self):
        self.fill()
        self.gh(PRS)
        code, out = self.main()
        self.assertEqual(code, 0)
        found = json.loads(out)
        for section in found:
            if section != "waiting":
                self.assertNotIn(LEAK, json.dumps(found[section]), section)
        for leak in (str(self.root), str(self.root.parent), "github.com"):
            self.assertNotIn(leak, out)
        # The exemption is used: waiting carries the titles and the note, nothing else of LEAK's.
        self.assertEqual([(b["title"], b["note"]) for b in found["waiting"]["blocked"]], [(LEAK, LEAK)])
        self.assertTrue(all(p["title"].endswith(LEAK) for p in found["waiting"]["pull_requests"]))


if __name__ == "__main__":
    unittest.main()
