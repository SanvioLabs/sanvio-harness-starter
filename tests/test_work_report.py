"""Run with: python3 -m unittest discover -s tests"""
import contextlib
import datetime
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import work_report  # noqa: E402 (needs scripts/ on the path first)

TODAY = datetime.date(2026, 10, 29)
SINCE = "2026-10-20"
NOW = datetime.datetime(2026, 10, 29, 12, 0, tzinfo=datetime.timezone.utc)
LEAK = "sentinel-wr4"  # put in every field the output must never carry
SYSTEM_PATH = "/usr/bin:/bin"  # for the fake gh's own commands; the real gh isn't on it

# A stand-in for gh, found on PATH. It answers pr list, issue list, the milestones API and release list
# from prs.json, issues.json, milestones.json and releases.json, and exits 1 while a file named fail exists.
GH = """#!PYTHON
import os, sys
folder = FOLDER
args = sys.argv[1:]
if os.path.exists(os.path.join(folder, "fail")):
    sys.exit(1)
name = {("pr", "list"): "prs", ("issue", "list"): "issues", ("release", "list"): "releases"}.get(tuple(args[:2]))
if args[:1] == ["api"] and "milestones" in args[1]:
    name = "milestones"
if name is None:
    sys.exit(1)
path = os.path.join(folder, name + ".json")
print(open(path).read() if os.path.exists(path) else "[]")
"""


def pr(number, merged, branch="fix", author="ana", reviews=(), closes=(), milestone=None, opened=None):
    """One row of gh pr list --json, with the fields work_report asks for and a body it mustn't keep."""
    return {"number": number, "title": "PR {}".format(number), "url": "https://github.com/o/r/pull/{}".format(number),
            "author": {"login": author}, "createdAt": opened or merged, "mergedAt": merged, "headRefName": branch,
            "closingIssuesReferences": [{"number": n} for n in closes],
            "milestone": {"title": milestone} if milestone else None,
            "reviews": [{"author": {"login": who}, "state": "APPROVED", "body": LEAK} for who in reviews],
            "body": LEAK}


class Report(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name).resolve() / "harness"
        self.root.mkdir()
        self.bin = Path(tmp.name).resolve() / "bin"
        self.bin.mkdir()
        fake = self.bin / "gh"
        fake.write_text(GH.replace("PYTHON", sys.executable).replace("FOLDER", repr(str(self.bin))))
        fake.chmod(0o755)
        patcher = mock.patch.dict(os.environ, {"PATH": str(self.bin) + os.pathsep + SYSTEM_PATH})
        patcher.start()
        self.addCleanup(patcher.stop)

    def answer(self, **files):
        for name, content in files.items():
            (self.bin / (name + ".json")).write_text(json.dumps(content))

    def build(self):
        return work_report.build(self.root, SINCE, TODAY, now=NOW)

    def test_a_pull_request_on_a_loop_branch_is_loop_built(self):
        self.answer(prs=[pr(1, "2026-10-21T10:00:00Z", branch="loop/issue-5"),
                         pr(2, "2026-10-21T11:00:00Z", branch="loop/issue-5-old"),
                         pr(3, "2026-10-22T11:00:00Z", branch="docs")])
        doc = self.build()
        self.assertEqual([r["loop_built"] for r in doc["pull_requests"]], [True, False, False])
        self.assertEqual((doc["totals"]["loop_built"], doc["totals"]["hand_built"]), (1, 2))

    def test_only_another_person_counts_as_a_second_reviewer(self):
        self.answer(prs=[pr(1, "2026-10-21T10:00:00Z", reviews=["ana"]),
                         pr(2, "2026-10-21T10:00:00Z", reviews=["github-actions[bot]"]),
                         pr(3, "2026-10-21T10:00:00Z", reviews=["ana", "ben", "ben"])])
        doc = self.build()
        self.assertEqual([r["second_reviewers"] for r in doc["pull_requests"]], [[], [], ["ben"]])
        self.assertEqual(doc["totals"]["second_reviewer"], 1)

    def test_a_closed_issue_links_its_pull_request_to_a_spec_and_nothing_else_of_its_body(self):
        self.answer(prs=[pr(1, "2026-10-21T10:00:00Z", closes=[7]), pr(2, "2026-10-21T10:00:00Z", milestone="D2")],
                    issues=[{"number": 7, "body": "## References\n\nSpec: specs/004-search REQ-002\n\n" + LEAK}])
        doc = self.build()
        self.assertEqual(doc["pull_requests"][0]["specs"], ["specs/004-search REQ-002"])
        self.assertEqual(doc["specs"], [{"spec": "specs/004-search REQ-002", "pull_requests": [1]}])
        self.assertEqual(doc["totals"]["on_a_milestone_or_spec"], 2)
        self.assertNotIn(LEAK, json.dumps(doc))

    def test_milestones_are_what_github_closed_in_the_period(self):
        self.answer(milestones=[
            {"title": "D1", "state": "closed", "closed_at": "2026-10-10T00:00:00Z", "closed_issues": 3, "open_issues": 0},
            {"title": "D2", "state": "closed", "closed_at": "2026-10-24T00:00:00Z", "closed_issues": 4, "open_issues": 0,
             "html_url": "https://github.com/o/r/milestone/2"},
            {"title": "D3", "state": "open", "closed_issues": 1, "open_issues": 2, "due_on": "2026-11-12T07:00:00Z"}],
            releases=[{"name": "v1", "tagName": "v1", "publishedAt": "2026-10-22T00:00:00Z", "isDraft": False},
                      {"name": "v0", "tagName": "v0", "publishedAt": "2026-10-01T00:00:00Z", "isDraft": False},
                      {"name": "v2", "tagName": "v2", "publishedAt": "2026-10-23T00:00:00Z", "isDraft": True}])
        doc = self.build()
        self.assertEqual([m["title"] for m in doc["milestones"]["met"]], ["D2"])
        self.assertEqual(doc["milestones"]["open"], [{"title": "D3", "url": None, "issues_closed": 1, "issues_open": 2,
                                                      "due": "2026-11-12"}])
        self.assertEqual([r["name"] for r in doc["releases"]], ["v1"])
        text = work_report.markdown(doc)
        self.assertIn("- Oct 22 · Release v1", text)
        self.assertIn("- Oct 24 · D2 (4 issues) https://github.com/o/r/milestone/2", text)
        self.assertIn("- D3: 1 of 3 issues closed, due Nov 12", text)

    def test_a_changelog_entry_is_what_shipped_not_a_milestone(self):
        (self.root / "CHANGELOG.md").write_text("# What's new\n\n## 2026-10-25: Loop run history\n\nx\n\n"
                                                "## 2026-10-12: Before the period\n")
        doc = self.build()
        self.assertEqual(doc["changelog"], [{"date": "2026-10-25", "name": "Loop run history"}])
        self.assertEqual(doc["milestones"]["met"], [])
        self.assertIn("None reached in this period.", work_report.markdown(doc))

    def test_every_day_of_the_period_has_a_count(self):
        self.answer(prs=[pr(1, "2026-10-21T10:00:00Z", branch="loop/issue-1", opened="2026-10-21T09:00:00Z"),
                         pr(2, "2026-10-21T23:30:00Z", opened="2026-10-21T23:00:00Z")])
        doc = self.build()
        self.assertEqual(len(doc["by_day"]), 10)
        self.assertEqual(doc["by_day"][1], {"day": "2026-10-21", "merged": 2, "loop_built": 1})
        self.assertEqual(doc["totals"]["median_minutes_to_merge"], 45.0)
        text = work_report.markdown(doc)
        self.assertIn("    bar [0, 2, 0, 0, 0, 0, 0, 0, 0, 0]", text)
        self.assertIn("    line [0, 1, 0, 0, 0, 0, 0, 0, 0, 0]", text)

    def test_each_author_gets_a_row(self):
        self.answer(prs=[pr(1, "2026-10-21T10:00:00Z", author="ben"), pr(2, "2026-10-21T10:00:00Z", author="ana"),
                         pr(3, "2026-10-22T10:00:00Z", author="ana", branch="loop/issue-3", closes=[9])])
        people = self.build()["by_person"]
        self.assertEqual([(p["login"], p["merged"], p["loop_built"], p["issues_closed"]) for p in people],
                         [("ana", 2, 1, 1), ("ben", 1, 0, 0)])

    def test_gh_failing_leaves_each_section_saying_why_and_still_exits_0(self):
        (self.bin / "fail").write_text("")
        (self.root / "CHANGELOG.md").write_text("## 2026-10-25: Loop run history\n")
        doc = self.build()
        for key in ("pull_requests", "totals", "by_person", "by_day", "specs", "milestones", "releases"):
            self.assertEqual(doc[key], {"value": None, "why": "gh unavailable"}, key)
        self.assertEqual(len(doc["changelog"]), 1)
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(work_report.main(["--since", SINCE], root=self.root), 0)
        self.assertIn("Not available: gh unavailable.", out.getvalue())

    def test_a_project_that_isnt_a_repo_is_refused(self):
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            work_report.main(["--project", "nope"], root=self.root)
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            work_report.main(["--project", "../harness"], root=self.root)


if __name__ == "__main__":
    unittest.main()
