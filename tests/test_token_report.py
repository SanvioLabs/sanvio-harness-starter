"""Run with: python3 -m unittest discover -s tests"""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "token_report.py"
sys.path.insert(0, str(ROOT / "scripts"))
import token_report  # noqa: E402 (needs scripts/ on the path first)

SINCE = "2026-10-01"
USAGE = {"input_tokens": 10, "output_tokens": 20, "cache_creation_input_tokens": 30, "cache_read_input_tokens": 40}
_ids = iter(range(1, 1_000_000))


def entry(cwd, usage=None, id=None, req=None, session="s1", ts="2026-10-05T12:00:00.000Z",
          model="claude-test-1", sidechain=False, content="a reply"):
    """One transcript line for a reply, the shape Claude Code writes."""
    n = next(_ids)
    return {"type": "assistant", "cwd": str(cwd), "sessionId": session, "timestamp": ts,
            "requestId": req or "req_{}".format(n), "isSidechain": sidechain,
            "message": {"id": id or "msg_{}".format(n), "model": model, "role": "assistant",
                        "usage": dict(USAGE) if usage is None else usage,
                        "content": [{"type": "text", "text": content}]}}


def write(folder, relative, lines):
    path = Path(folder) / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join((l if isinstance(l, str) else json.dumps(l)) + "\n" for l in lines))
    return path


def run(*args):
    return subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True, timeout=60)


class Harness(unittest.TestCase):
    """A temporary harness root, a loop folder beside it, and a transcripts folder."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        base = Path(tmp.name).resolve()
        self.root = base / "harness"
        self.loop = base / "loop-checkouts"
        self.transcripts = base / "transcripts"
        for folder in (self.root / "projects" / "app", self.loop / "issue-7", self.transcripts):
            folder.mkdir(parents=True)

    def rows(self, lines):
        return [token_report.group(e, self.root, self.loop) for e in lines]


class Discovery(Harness):
    def test_subagent_files_in_a_session_subfolder_are_found(self):
        write(self.transcripts, "proj/s1.jsonl", [entry(self.root)])
        write(self.transcripts, "proj/s1/subagents/agent-a.jsonl", [entry(self.root)])
        found = token_report.read(self.transcripts, SINCE)
        self.assertEqual(len(found), 2)
        self.assertEqual(sorted(e["_subagent"] for e in found), [False, True])

    def test_a_sidechain_line_counts_as_a_subagent(self):
        write(self.transcripts, "proj/s1.jsonl", [entry(self.root, sidechain=True)])
        self.assertTrue(token_report.read(self.transcripts, SINCE)[0]["_subagent"])

    def test_the_projects_flag_is_where_it_reads(self):
        write(self.transcripts, "proj/s1.jsonl", [entry(ROOT, content="flag-test")])
        result = run("--projects", str(self.transcripts), "--since", SINCE)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Total: 100 tokens across 1 sessions.", result.stdout)


class JudgedByCwd(Harness):
    def test_a_session_that_leaves_the_root_counts_only_its_lines_inside(self):
        outside = self.root.parent / "elsewhere"
        lines = [entry(self.root), entry(outside), entry(self.root / "notes")]
        out = token_report.report(lines, SINCE, "2026-10-22", self.root, self.loop)
        self.assertIn("Total: 200 tokens across 1 sessions.", out)

    def test_a_sibling_sharing_the_roots_name_is_outside(self):
        sibling = self.root.parent / (self.root.name + "-other")
        self.assertIsNone(token_report.group(entry(sibling), self.root, self.loop))
        self.assertIsNone(token_report.group(entry(sibling / "projects" / "app"), self.root, self.loop))

    def test_a_line_without_a_cwd_is_outside(self):
        line = entry(self.root)
        del line["cwd"]
        self.assertIsNone(token_report.group(line, self.root, self.loop))


class Grouping(Harness):
    def test_root_projects_and_loop(self):
        self.assertEqual(self.rows([entry(self.root), entry(self.root / "skills"), entry(self.root / "projects"),
                                    entry(self.root / "projects" / "app" / "src"), entry(self.loop / "issue-7" / "x")]),
                         [("Conversations", ""), ("Conversations", ""), ("Conversations", ""),
                          ("projects/", "app"), ("Loop", "issue-7")])

    def test_without_worktree_dir_the_loop_folder_is_beside_home(self):
        self.assertEqual(token_report.loop_dir(self.root), Path.home() / ".harness-loop" / "harness")

    def test_worktree_dir_from_loop_json_is_used(self):
        (self.root / "loop.json").write_text(json.dumps({"worktree_dir": str(self.loop)}))
        self.assertEqual(token_report.loop_dir(self.root), self.loop)

    def test_a_worktree_dir_inside_the_root_counts_as_the_loop(self):
        inside = self.root / "checkouts"
        (self.root / "loop.json").write_text(json.dumps({"worktree_dir": str(inside)}))
        loop = token_report.loop_dir(self.root)
        self.assertEqual(token_report.group(entry(inside / "issue-3"), self.root, loop), ("Loop", "issue-3"))
        self.assertEqual(token_report.group(entry(self.root), self.root, loop), ("Conversations", ""))


class Repeats(Harness):
    def test_a_reply_written_as_several_lines_counts_once(self):
        line = entry(self.root, id="msg_same", req="req_same")
        write(self.transcripts, "proj/s1.jsonl", [line, line, entry(self.root, id="msg_same", req="req_other")])
        self.assertEqual(len(token_report.read(self.transcripts, SINCE)), 2)


class Since(Harness):
    def test_replies_before_the_date_are_left_out(self):
        write(self.transcripts, "proj/s1.jsonl", [entry(self.root, ts="2026-09-30T23:59:59Z"),
                                                  entry(self.root, ts="2026-10-01T00:00:00Z")])
        found = token_report.read(self.transcripts, SINCE)
        self.assertEqual([e["timestamp"] for e in found], ["2026-10-01T00:00:00Z"])

    def test_a_bad_date_is_refused_as_usage_report_refuses_it(self):
        mine = run("--since", "last week")
        theirs = subprocess.run([sys.executable, str(ROOT / "scripts" / "usage_report.py"), "--since", "last week"],
                                capture_output=True, text=True, timeout=60)
        self.assertEqual((mine.returncode, theirs.returncode), (2, 2))
        self.assertIn("use YYYY-MM-DD, e.g. 2026-10-01", mine.stderr)
        self.assertEqual(mine.stderr.splitlines()[-1].split(": ", 1)[1], theirs.stderr.splitlines()[-1].split(": ", 1)[1])


class Output(Harness):
    def test_every_section_is_there(self):
        lines = [entry(self.root, session="a"), entry(self.root / "projects" / "app", session="b", model="claude-other"),
                 entry(self.loop / "issue-7", session="c", sidechain=True, ts="2026-10-03T08:00:00Z"),
                 entry(self.loop / "issue-12", session="d")]
        for line in lines:
            line["_subagent"] = bool(line["isSidechain"])
        out = token_report.report(lines, SINCE, "2026-10-22", self.root, self.loop)
        for heading in ("# Claude Code tokens, 2026-10-01 to 2026-10-22", "## Conversations", "## projects/",
                        "## Loop", "## By model", "## Subagents", "## Top sessions", "## Top loop issues"):
            self.assertIn(heading, out)
        self.assertIn("| Repo | Input | Output | Cache writes | Cache reads | Total |", out)
        self.assertIn("| app | 10 | 20 | 30 | 40 | 100 |", out)
        self.assertIn("| This harness | 10 | 20 | 30 | 40 | 100 |", out)
        self.assertLess(out.index("| issue-7 |"), out.index("| issue-12 |"))
        self.assertIn("| claude-other | 100 |", out)
        self.assertIn("100 of 400 tokens (25%) were spent by subagents.", out)
        self.assertIn("`c`, first 2026-10-03", out)
        self.assertIn("## Loop cost", out)
        self.assertTrue(out.endswith("Claude Code sessions only. Dollars only for the loop's runs, as the loop "
                                     "recorded them at API prices."))

    def test_nothing_under_the_harness_says_so(self):
        out = token_report.report([entry(self.root.parent / "elsewhere")], SINCE, "2026-10-22", self.root, self.loop)
        self.assertEqual(out, "No Claude Code usage under this harness since 2026-10-01.")


class LoopCost(Harness):
    """The loop's own estimates, from each issue's usage.json under the harness's .loop/."""

    def record(self, relative, entries):
        write(self.root / ".loop", relative, [json.dumps(entries)])

    def test_costs_come_from_the_loops_records_since_the_date(self):
        self.record("issue-7/usage.json", [
            {"step": "plan", "run_started": "2026-10-05T09:00:00", "cost_usd": 1.25},
            {"step": "build", "run_started": "2026-10-06T09:00:00", "cost_usd": 0.5},
            {"step": "review", "run_started": "2026-10-06T09:00:00", "cost_usd": None},
            {"step": "plan", "run_started": "2026-09-30T09:00:00", "cost_usd": 9.0}])
        self.record("issue-12/usage.json", [{"step": "plan", "run_started": "2026-10-05T09:00:00", "cost_usd": None}])
        self.record("projects/app/issue-3/usage.json", [
            {"step": "plan", "run_started": "2026-10-05T09:00:00", "cost_usd": 0.25}])
        self.assertEqual(token_report.loop_costs(self.root, SINCE),
                         {"issue-7": (1.75, 1), "issue-12": (None, 1), "app/issue-3": (0.25, 0)})

    def test_a_run_with_no_start_date_is_in_no_period(self):
        self.record("issue-7/usage.json", [{"step": "plan", "run_started": None, "cost_usd": 4.0},
                                           {"step": "plan", "cost_usd": 4.0}])
        self.assertEqual(token_report.loop_costs(self.root, SINCE), {})

    def test_unreadable_records_and_odd_values_are_skipped(self):
        write(self.root / ".loop", "issue-1/usage.json", ["not json"])
        self.record("issue-2/usage.json", {"cost_usd": 3})
        self.record("issue-3/usage.json", [["x"], {"run_started": "2026-10-05", "cost_usd": "lots"},
                                           {"run_started": "2026-10-05", "cost_usd": True},
                                           {"run_started": "2026-10-05", "cost_usd": 2}])
        self.assertEqual(token_report.loop_costs(self.root, SINCE), {"issue-3": (2, 2)})

    def test_no_loop_folder_reads_as_no_costs(self):
        self.assertEqual(token_report.loop_costs(self.root, SINCE), {})

    def test_the_report_lists_them_with_a_total_and_the_runs_without_one(self):
        out = token_report.report([entry(self.root)], SINCE, "2026-10-22", self.root, self.loop,
                                  costs={"issue-12": (0.25, 0), "issue-7": (1.75, 1), "issue-9": (None, 2)})
        self.assertIn("| Issue | Estimated cost | Runs without a cost |", out)
        self.assertIn("| issue-7 | $1.75 | 1 |", out)
        self.assertIn("| issue-9 | none recorded | 2 |", out)
        self.assertLess(out.index("| issue-7 |"), out.index("| issue-12 |"))
        self.assertIn("Total: $2.00, estimated at API prices, not what was billed.", out)
        self.assertIn("3 runs recorded no cost", out)
        self.assertIn("when the loop picked the issue up", out)

    def test_without_costs_it_says_none_were_recorded(self):
        out = token_report.report([entry(self.root)], SINCE, "2026-10-22", self.root, self.loop)
        self.assertIn("## Loop cost\n\nNone recorded.", out)

    def test_costs_print_when_no_transcript_is_under_the_harness(self):
        out = token_report.report([], SINCE, "2026-10-22", self.root, self.loop, costs={"issue-7": (1.75, 0)})
        self.assertIn("| issue-7 | $1.75 | 0 |", out)

    def test_a_project_issue_has_the_same_name_in_the_token_and_cost_tables(self):
        (self.loop / "app" / "issue-3").mkdir(parents=True)
        self.assertEqual(token_report.group(entry(self.loop / "app" / "issue-3"), self.root, self.loop),
                         ("Loop", "app/issue-3"))
        self.assertEqual(token_report.group(entry(self.loop / "app" / "issue-3" / "src"), self.root, self.loop),
                         ("Loop", "app/issue-3"))


class Privacy(Harness):
    def test_no_prompt_reply_path_or_code_is_printed(self):
        secret_dir = ROOT / "secret-folder-zq7"
        prompt = {"type": "user", "cwd": str(secret_dir), "sessionId": "s1", "timestamp": "2026-10-05T11:00:00Z",
                  "message": {"role": "user", "content": "prompt-text-zq7"}}
        write(self.transcripts, "proj/s1.jsonl", [
            prompt, entry(secret_dir, content="reply-text-zq7 def secret_function_zq7(): pass")])
        result = run("--projects", str(self.transcripts), "--since", SINCE)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Total: 100 tokens", result.stdout)
        for leak in ("prompt-text-zq7", "reply-text-zq7", "secret_function_zq7", "secret-folder-zq7", str(ROOT)):
            self.assertNotIn(leak, result.stdout)


class BadInput(Harness):
    def test_junk_lines_and_odd_shapes_are_skipped(self):
        bad_usage = entry(self.root)
        bad_usage["message"]["usage"] = [1, 2]
        no_message = entry(self.root)
        no_message["message"] = "text"
        odd_counts = entry(self.root, usage={"input_tokens": "lots", "output_tokens": None, "cache_read_input_tokens": 5})
        write(self.transcripts, "proj/s1.jsonl",
              ["not json", "[1, 2]", "", "{\"broken\":", bad_usage, no_message, odd_counts])
        found = token_report.read(self.transcripts, SINCE)
        self.assertEqual(len(found), 1)
        self.assertIn("Total: 5 tokens", token_report.report(found, SINCE, "2026-10-22", self.root, self.loop))

    def test_a_missing_folder_reads_as_nothing(self):
        self.assertEqual(token_report.read(self.transcripts / "missing", SINCE), [])

    def test_an_empty_run_exits_0(self):
        result = run("--projects", str(self.transcripts / "missing"), "--since", SINCE)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "No Claude Code usage under this harness since 2026-10-01.")


if __name__ == "__main__":
    unittest.main()
