"""Run with: python3 -m unittest discover -s tests"""
import datetime
import io
import json
import os
import stat
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import dashboard_data  # noqa: E402 (needs scripts/ on the path first)
from usage_report import log_path  # noqa: E402 (same reason)

TODAY = datetime.date(2026, 10, 27)
SINCE = "2026-10-15"
LEAK = "sentinel-zq7"  # put in every field the output must never carry

# A stand-in for gh, found on PATH. It logs each call, answers pr list from prs.json ([] when there's
# none) and pulls/<n>/commits from commits.json's pages for n, and exits 1 while a file named fail exists.
GH = """#!/usr/bin/env python3
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
        # No test reaches the real gh: this one answers from files in self.gh, outside the root.
        self.gh = Path(tmp.name).resolve() / "gh"
        self.gh.mkdir()
        script = self.gh / "gh"
        script.write_text(GH.replace("FOLDER", repr(str(self.gh))))
        script.chmod(script.stat().st_mode | stat.S_IEXEC)
        self.addCleanup(os.environ.__setitem__, "PATH", os.environ["PATH"])
        os.environ["PATH"] = str(self.gh) + os.pathsep + os.environ["PATH"]

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
        return dashboard_data.build(self.root, since, TODAY)

    def main(self, *args):
        out = io.StringIO()
        with redirect_stdout(out):
            code = dashboard_data.main(["--json", "--since", SINCE, *args], root=self.root)
        return code, out.getvalue()


class Layout(Harness):
    def test_the_top_level_keys(self):
        self.fill()
        code, out = self.main()
        self.assertEqual(code, 0)
        found = json.loads(out)
        self.assertEqual(list(found), ["generated", "since", "loop_spend", "loop_throughput", "activity", "evals",
                                       "loop_rework"])
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
        self.assertEqual(self.build()["evals"], {
            "reviewer": {"saved": "2026-10-25T09:00:00+00:00", "stable": 1, "flaky": 1, "failing": 1,
                         "failing_cases": ["03-c"]},
            "security-reviewer": {"saved": "2026-10-26T09:00:00+00:00", "stable": 1, "flaky": 0, "failing": 0,
                                  "failing_cases": []}})


def commit(message, parents=1):
    """One item from the pulls/<n>/commits API, the parts loop_rework reads and an author it mustn't keep."""
    return {"sha": "abc", "commit": {"message": message, "author": {"name": LEAK}},
            "parents": [{"sha": "p{}".format(i)} for i in range(parents)]}


class Rework(Harness):
    def setUp(self):
        super().setUp()
        loop = commit("Build it\n\nLoop: issue #1, round 1.")
        write(self.gh, "prs.json", [
            {"number": 101, "title": "All the loop's", "headRefName": "loop/issue-1", "mergedAt": "2026-10-20T12:00:00Z"},
            {"number": 102, "title": "Fixed by hand", "headRefName": "loop/issue-2", "mergedAt": "2026-10-21T12:00:00Z"},
            {"number": 103, "title": "Not the loop's", "headRefName": "feature/x", "mergedAt": "2026-10-22T12:00:00Z"},
            {"number": 104, "title": "Too old", "headRefName": "loop/issue-4", "mergedAt": "2026-10-01T12:00:00Z"}])
        # 102's commits come in two pages, as gh --paginate prints them.
        write(self.gh, "commits.json", {
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
        calls = [c for c in (self.gh / "calls").read_text().splitlines() if "/commits" in c]
        self.assertEqual(sorted(c.split("/")[-2] for c in calls), ["101", "102"])
        cache = (self.root / ".harness" / "cache" / "loop_rework.json").read_text()
        self.assertEqual(sorted(json.loads(cache)), ["101", "102"])
        self.assertNotIn(LEAK, cache)

    def test_gh_failing_gives_null_and_why_and_exits_0(self):
        write(self.gh, "fail", "")
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


class Privacy(Harness):
    def test_no_title_note_pr_prompt_reason_or_path_is_printed(self):
        self.fill()
        code, out = self.main()
        self.assertEqual(code, 0)
        for leak in (LEAK, str(self.root), str(self.root.parent), "github.com"):
            self.assertNotIn(leak, out)


if __name__ == "__main__":
    unittest.main()
