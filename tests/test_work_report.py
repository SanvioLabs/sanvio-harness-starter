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

# A stand-in for gh, found on PATH. It answers the GraphQL search from search.json's pages, one printed
# per line as --paginate does, the milestones API, release list and repo view from milestones.json,
# releases.json and repo.json, and exits 1 while a file named fail exists.
GH = """#!PYTHON
import json, os, sys
folder = FOLDER
args = sys.argv[1:]
if os.path.exists(os.path.join(folder, "fail")):
    sys.exit(1)
def read(name, empty):
    path = os.path.join(folder, name + ".json")
    return json.load(open(path)) if os.path.exists(path) else empty
if args[:2] == ["api", "graphql"]:
    for page in read("search", [{"data": {"search": {"issueCount": 0, "nodes": []}}}]):
        print(json.dumps(page))
elif args[:1] == ["api"] and "milestones" in args[1]:
    print(json.dumps(read("milestones", [])))
elif args[:2] == ["release", "list"]:
    print(json.dumps(read("releases", [])))
elif args[:2] == ["repo", "view"]:
    print(json.dumps(read("repo", {"nameWithOwner": "o/r"})))
else:
    sys.exit(1)
"""


def review(who, state="APPROVED", kind="User"):
    return {"state": state, "author": {"__typename": kind, "login": who}, "body": LEAK}


def pr(number, merged, branch="fix", author="ana", reviews=(), closes=(), milestone=None, opened=None):
    """One pull request node from the GraphQL search, with the fields work_report asks for and a body it mustn't keep."""
    return {"number": number, "title": "PR {}".format(number), "url": "https://github.com/o/r/pull/{}".format(number),
            "author": {"__typename": "User", "login": author}, "createdAt": opened or merged, "mergedAt": merged,
            "headRefName": branch, "milestone": {"title": milestone} if milestone else None,
            "closingIssuesReferences": {"nodes": [c if isinstance(c, dict) else {"number": c, "body": LEAK} for c in closes]},
            "reviews": {"nodes": list(reviews)}, "body": LEAK}


def pages(prs, matched=None, size=2):
    """The search's pages as --paginate prints them, size pull requests a page."""
    chunks = [prs[i:i + size] for i in range(0, len(prs), size)] or [[]]
    return [{"data": {"search": {"issueCount": len(prs) if matched is None else matched, "nodes": chunk}}} for chunk in chunks]


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

    def answer(self, prs=None, matched=None, **files):
        if prs is not None:
            files["search"] = pages(prs, matched)
        for name, content in files.items():
            (self.bin / (name + ".json")).write_text(json.dumps(content))

    def build(self):
        return work_report.build(self.root, SINCE, TODAY, now=NOW)

    def test_a_pull_request_on_a_loop_branch_is_loop_built(self):
        self.answer([pr(1, "2026-10-21T10:00:00Z", branch="loop/issue-5"),
                     pr(2, "2026-10-21T11:00:00Z", branch="loop/issue-5-old"),
                     pr(3, "2026-10-22T11:00:00Z", branch="docs")])
        doc = self.build()
        self.assertEqual([r["loop_built"] for r in doc["pull_requests"]], [True, False, False])
        self.assertEqual((doc["totals"]["loop_built"], doc["totals"]["hand_built"]), (1, 2))

    def test_only_another_persons_approval_counts_as_one(self):
        self.answer([pr(1, "2026-10-21T10:00:00Z", reviews=[review("ana")]),
                     pr(2, "2026-10-21T10:00:00Z", reviews=[review("copilot-pull-request-reviewer", kind="Bot"),
                                                            review("github-actions[bot]")]),
                     pr(3, "2026-10-21T10:00:00Z", reviews=[review("ben", "COMMENTED"), review("cy", "DISMISSED")]),
                     pr(4, "2026-10-21T10:00:00Z", reviews=[review("ben", "COMMENTED"), review("ben")])])
        doc = self.build()
        self.assertEqual([(r["reviewers"], r["approved_by"]) for r in doc["pull_requests"]],
                         [([], []), ([], []), (["ben"], []), (["ben"], ["ben"])])
        self.assertEqual(doc["totals"]["approved_by_another"], 1)
        self.assertIn("3 of 4 merged pull requests weren't approved by anyone but their author.", doc["watch"])

    def test_reviews_given_count_for_someone_who_merged_nothing(self):
        self.answer([pr(1, "2026-10-21T10:00:00Z", reviews=[review("lead", "COMMENTED")]),
                     pr(2, "2026-10-22T10:00:00Z", branch="loop/issue-3", closes=[9], reviews=[review("lead")])])
        people = {p["login"]: p for p in self.build()["by_person"]}
        self.assertEqual((people["ana"]["merged"], people["ana"]["loop_built"], people["ana"]["issues_closed"]), (2, 1, 1))
        self.assertEqual((people["lead"]["merged"], people["lead"]["reviews_given"]), (0, 2))

    def test_a_closed_issue_links_its_pull_request_to_a_spec_and_nothing_else_of_its_body(self):
        body = "## References\n\nSpec: docs/specs/004-search REQ-002\n\n" + LEAK
        self.answer([pr(1, "2026-10-21T10:00:00Z", closes=[{"number": 7, "body": body}]),
                     pr(2, "2026-10-21T10:00:00Z", closes=[{"number": 8, "body": "Spec: docs/specs/004-search REQ-003"}]),
                     pr(3, "2026-10-21T10:00:00Z", milestone="D2"), pr(4, "2026-10-21T10:00:00Z")])
        doc = self.build()
        self.assertEqual(doc["specs"], [{"spec": "docs/specs/004-search", "pull_requests": [1, 2]}])
        self.assertEqual(doc["totals"]["on_a_milestone_or_spec"], 3)
        self.assertIn("1 of 4 merged pull requests are on no milestone and name no spec.", doc["watch"])
        self.assertIn("- docs/specs/004-search: 2 pull requests", work_report.markdown(doc))
        self.assertNotIn(LEAK, json.dumps(doc))
        self.assertNotIn(LEAK, work_report.markdown(doc))

    def test_milestones_are_what_github_closed_in_the_period_with_what_was_left(self):
        self.answer(milestones=[
            {"title": "D1", "state": "closed", "closed_at": "2026-10-10T00:00:00Z", "closed_issues": 3, "open_issues": 0},
            {"title": "D2", "state": "closed", "closed_at": "2026-10-24T00:00:00Z", "closed_issues": 4, "open_issues": 2,
             "due_on": "2026-10-20T07:00:00Z", "html_url": "https://github.com/o/r/milestone/2"},
            {"title": "D3", "state": "open", "closed_issues": 1, "open_issues": 2, "due_on": "2026-10-27T07:00:00Z"},
            {"title": "D4", "state": "open", "closed_issues": 0, "open_issues": 1, "due_on": "2026-11-12T07:00:00Z"}],
            releases=[{"name": "v1", "tagName": "v1", "publishedAt": "2026-10-22T00:00:00Z", "isDraft": False},
                      {"name": "v0", "tagName": "v0", "publishedAt": "2026-10-01T00:00:00Z", "isDraft": False},
                      {"name": "v2", "tagName": "v2", "publishedAt": "2026-10-23T00:00:00Z", "isDraft": True}])
        doc = self.build()
        self.assertEqual([m["title"] for m in doc["milestones"]["closed"]], ["D2"])
        self.assertEqual([r["name"] for r in doc["releases"]], ["v1"])
        self.assertEqual(doc["watch"], ["D2 closed with 2 of its 6 issues still open.",
                                        "D2 closed on Oct 24 2026, after its due date of Oct 20 2026.",
                                        "D3 is past its due date of Oct 27 2026, with 2 of its 3 issues open."])
        text = work_report.markdown(doc)
        self.assertIn("- Oct 22 2026 · Release v1", text)
        self.assertIn("- Oct 24 2026 · D2 closed: 4 of 6 issues, due Oct 20 2026 https://github.com/o/r/milestone/2", text)
        self.assertIn("- D4: 0 of 1 issues closed, due Nov 12 2026", text)

    def test_a_changelog_entry_is_what_shipped_not_a_milestone(self):
        (self.root / "CHANGELOG.md").write_text("# What's new\n\n## 2026-10-25: Loop run history\n\nx\n\n"
                                                "## 2026-10-12: Before the period\n")
        doc = self.build()
        self.assertEqual(doc["changelog"], [{"date": "2026-10-25", "name": "Loop run history"}])
        self.assertEqual(doc["milestones"]["closed"], [])
        self.assertIn("None reached in this period.", work_report.markdown(doc))

    def test_every_day_of_the_period_has_a_count(self):
        self.answer([pr(1, "2026-10-21T10:00:00Z", branch="loop/issue-1", opened="2026-10-21T09:00:00Z"),
                     pr(2, "2026-10-21T23:30:00Z", opened="2026-10-21T23:00:00Z"),
                     pr(3, "2026-10-29T08:00:00Z", opened="2026-10-29T07:00:00Z")])
        doc = self.build()
        self.assertEqual(len(doc["by_day"]), 10)
        self.assertEqual(doc["by_day"][1], {"day": "2026-10-21", "merged": 2, "loop_built": 1})
        self.assertEqual(sum(d["merged"] for d in doc["by_day"]), doc["totals"]["merged"])
        self.assertEqual(doc["totals"]["median_minutes_to_merge"], 60.0)
        text = work_report.markdown(doc)
        self.assertIn("    bar [0, 2, 0, 0, 0, 0, 0, 0, 0, 1]", text)
        self.assertIn("    line [0, 1, 0, 0, 0, 0, 0, 0, 0, 0]", text)

    def test_the_report_lists_each_pull_request_with_who_reviewed_it(self):
        self.answer([pr(1, "2026-10-21T10:00:00Z", reviews=[review("ben")]),
                     pr(2, "2026-10-22T10:00:00Z", branch="loop/issue-2")], repo={"nameWithOwner": "acme/app"})
        text = work_report.markdown(self.build())
        self.assertTrue(text.startswith("# Work report: acme/app, Oct 20 2026 to Oct 29 2026\n"))
        self.assertIn("| [2](https://github.com/o/r/pull/2) | PR 2 | ana | loop | nobody else | 2026-10-22 |", text)
        self.assertIn("| [1](https://github.com/o/r/pull/1) | PR 1 | ana | hand | ben (approved) | 2026-10-21 |", text)

    def test_a_search_with_more_than_github_returns_says_its_counts_are_low(self):
        self.answer([pr(1, "2026-10-21T10:00:00Z")], matched=work_report.LIMIT + 1)
        doc = self.build()
        self.assertTrue(doc["truncated"])
        self.assertIn("stopped at", doc["watch"][0])

    def test_gh_failing_leaves_each_section_saying_why_and_still_exits_0(self):
        (self.bin / "fail").write_text("")
        (self.root / "CHANGELOG.md").write_text("## 2026-10-25: Loop run history\n")
        doc = self.build()
        for key in ("pull_requests", "totals", "by_person", "by_day", "specs", "milestones", "releases"):
            self.assertEqual(doc[key], {"value": None, "why": "gh unavailable"}, key)
        self.assertEqual((doc["repo"], len(doc["changelog"]), doc["watch"]), ("harness", 1, []))
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(work_report.main(["--since", SINCE], root=self.root), 0)
        self.assertIn("Not available: gh unavailable.", out.getvalue())

    def test_a_project_that_isnt_a_repo_is_refused(self):
        for name in ("nope", "../harness"):
            with self.subTest(name=name), contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                work_report.main(["--project", name], root=self.root)


if __name__ == "__main__":
    unittest.main()
