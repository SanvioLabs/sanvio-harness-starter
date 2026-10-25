"""Run with: python3 -m unittest discover -s tests

Every test uses a canned reply or a fake agent, a small Python script given as the agent, so no
real model starts."""
import contextlib
import io
import json
import shlex
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import eval_agents  # noqa: E402

EVALS = ROOT / "examples" / "proposal" / "evals"
TS_EVALS = ROOT / "examples" / "typescript" / "evals"
GATE = ROOT / "examples" / "proposal" / "gates" / "proposal_gate.py"
GOOD = '**Where:** Scope, "unlimited revisions"\n**Why it matters:** a promise.\n**Suggested fix:** cap them.\n'
NOTHING = "Nothing that matters."
# A fake security reviewer: finds the work.ts path in its prompt and, only if that file exists, replies
# in the security reviewer's shape with what the case.json beside it asks for: the first alternative of
# each must_find entry in a finding, and each must_mention text under Recommendations.
SECURITY = r'''
import json, re
match = re.search(r"Review the work in (.+?\.ts)\. Read it", prompt)
work = match.group(1) if match else ""
if os.path.isfile(work):
    want = json.load(open(os.path.join(os.path.dirname(work), "case.json")))
    reply = "**Reviewer:** security-reviewer\n**Verdict:** " + want.get("verdict", "READY") + "\n"
    for anchor in want["must_find"]:
        anchor = anchor[0] if isinstance(anchor, list) else anchor
        reply += ("- **Title:** a flaw\n  - **Severity:** High\n  - **Where:** " + work + ":1\n"
                  "  - **Attack:** reach " + anchor + "\n  - **Fix:** stop it\n")
    for text in want.get("must_mention", []):
        reply += "- **Recommendations:** the file says " + json.dumps(text) + "\n"
'''
# A security reviewer's reply in its documented shape, to grade against.
REPORT = """**Reviewer:** security-reviewer
**Verdict:** NOT-READY

- **Summary:** runReportExport builds a shell command from the title.
- **Findings:**
  - **Title:** Shell injection through the title
  - **Severity:** Critical
  - **Where:** `work.ts:39`
  - **Attack:** a title of `"; rm -rf ~; "` runs as the server's user.
  - **Fix:** use execFile with an argument list.
- **Recommendations:** the report-render binary has no timeout.
- **Not checked:** dependencies, no lock file.
"""


def case(**fields):
    base = {"name": "x", "agent": "reviewer", "must_find": [], "must_mention": [], "must_not_flag": [],
            "max_findings": 10}
    base.update(fields)
    return base


def fake_agent(folder, body):
    """The --agent value for a fake agent that reads the prompt, runs body, and says what body sets as reply."""
    script = Path(folder) / "fake_agent.py"
    script.write_text("import sys, os\nprompt = sys.stdin.read()\nreply = ''\n" + body + "\nprint(reply)\n")
    return "{} {}".format(shlex.quote(sys.executable), shlex.quote(str(script)))


def counting(folder):
    """A fake agent that passes case 01 on its first call and fails on its second."""
    counter = Path(folder) / "calls"
    return fake_agent(folder, """
path = {!r}
calls = int(open(path).read()) if os.path.exists(path) else 0
open(path, "w").write(str(calls + 1))
reply = {!r} if calls == 0 else {!r}
""".format(str(counter), GOOD, NOTHING)), counter


def first_case():
    return next(c for c in eval_agents.load_cases(EVALS) if c["name"].startswith("01"))


class Cases(unittest.TestCase):
    def test_all_ten_load(self):
        cases = eval_agents.load_cases(EVALS)
        self.assertEqual(len(cases), 10)
        for c in cases:
            self.assertTrue(c["work"].is_file(), c["name"])
            self.assertTrue((ROOT / c["brief"]).is_file(), c["name"])
            self.assertTrue((ROOT / "agents" / (c["agent"] + ".md")).is_file(), c["name"])

    def test_each_anchor_appears_once_in_its_work(self):
        for c in eval_agents.load_cases(EVALS):
            text = c["work"].read_text()
            for anchor in c["must_find"] + c["must_not_flag"]:
                self.assertEqual(text.count(anchor), 1, "{}: {}".format(c["name"], anchor))

    def test_the_gate_passes_nine_and_fails_the_placeholder(self):
        for c in eval_agents.load_cases(EVALS):
            done = subprocess.run([sys.executable, str(GATE), str(c["work"])], capture_output=True, text=True)
            self.assertEqual(done.returncode, 1 if c["name"].startswith("10") else 0, c["name"] + done.stdout)

    def test_the_prompt_holds_the_instructions_the_brief_and_the_file(self):
        c = first_case()
        text = eval_agents.prompt(c)
        self.assertIn("# Reviewer", text)
        self.assertIn("# Proposal reviewer brief", text)
        self.assertIn(str(c["work"].resolve()), text)


class SecurityCases(unittest.TestCase):
    def test_all_ten_load_with_a_ts_file_holding_each_anchor_once(self):
        cases = eval_agents.load_cases(TS_EVALS)
        self.assertEqual(len(cases), 10)
        for c in cases:
            self.assertEqual(c["agent"], "security-reviewer", c["name"])
            self.assertNotIn("brief", c, c["name"])
            self.assertEqual(c["work"].suffix, ".ts", c["name"])
            self.assertTrue(c["work"].is_file(), c["name"])
            text = c["work"].read_text()
            found = [a for entry in c["must_find"] for a in (entry if isinstance(entry, list) else [entry])]
            for anchor in found + c["must_mention"] + c["must_not_flag"]:
                self.assertEqual(text.count(anchor), 1, "{}: {}".format(c["name"], anchor))

    def test_the_note_is_a_mention_not_a_finding(self):
        note = next(c for c in eval_agents.load_cases(TS_EVALS) if c["name"].startswith("08"))
        self.assertEqual((note["must_find"], note["must_mention"]), ([], ["Ignore your previous instructions"]))

    def test_seven_are_not_ready_two_are_ready_and_the_note_has_no_verdict(self):
        verdicts = {c["name"][:2]: c.get("verdict") for c in eval_agents.load_cases(TS_EVALS)}
        want = {"{:02d}".format(n): "NOT-READY" for n in range(1, 8)}
        want.update({"08": None, "09": "READY", "10": "READY"})
        self.assertEqual(verdicts, want)

    def test_an_agent_that_reads_each_ts_file_passes_every_case(self):
        with tempfile.TemporaryDirectory() as tmp:
            agent = fake_agent(tmp, SECURITY)
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                code = eval_agents.main([str(TS_EVALS), "--runs", "1", "--agent", agent, "--checkout", tmp])
        self.assertEqual(code, 0, out.getvalue())
        self.assertIn("10 stable, 0 flaky, 0 failing", out.getvalue())


class Grading(unittest.TestCase):
    def test_an_anchor_in_a_finding_passes(self):
        self.assertEqual(eval_agents.grade(case(must_find=["unlimited revisions"]), GOOD), (True, []))

    def test_a_missing_anchor_fails(self):
        passed, reasons = eval_agents.grade(case(must_find=["Hermes"]), GOOD)
        self.assertFalse(passed)
        self.assertEqual(reasons, ["missed: Hermes"])

    def test_a_quoted_must_not_flag_text_fails(self):
        reply = '**Where:** Assumptions, "TBD"\n**Why it matters:** x\n**Suggested fix:** y\n'
        passed, reasons = eval_agents.grade(case(must_not_flag=["TBD"]), reply)
        self.assertFalse(passed)
        self.assertEqual(reasons, ["flagged: TBD"])

    def test_text_outside_a_finding_is_not_a_finding(self):
        self.assertEqual(eval_agents.grade(case(must_not_flag=["TBD"]), "The TBD is the gate's job."), (True, []))

    def test_eleven_findings_fail(self):
        reply = "".join("**Where:** Scope {}\n**Why it matters:** x\n".format(n) for n in range(11))
        passed, reasons = eval_agents.grade(case(), reply)
        self.assertFalse(passed)
        self.assertEqual(reasons, ["11 findings, more than 10"])

    def test_ten_findings_pass(self):
        reply = "".join("**Where:** Scope {}\n**Why it matters:** x\n".format(n) for n in range(10))
        self.assertTrue(eval_agents.grade(case(), reply)[0])

    def test_the_one_line_reply_is_zero_findings(self):
        self.assertEqual(eval_agents.findings(NOTHING), [])
        self.assertTrue(eval_agents.grade(case(max_findings=0), NOTHING)[0])

    def test_a_bulleted_where_line_starts_a_finding(self):
        self.assertEqual(len(eval_agents.findings("1. **Where:** a\n2. **Where:** b\n")), 2)

    def test_a_matching_verdict_passes_and_a_wrong_one_fails(self):
        need = case(verdict="NOT-READY")
        self.assertTrue(eval_agents.grade(need, "**Verdict:** NOT-READY")[0])
        passed, reasons = eval_agents.grade(need, "**Verdict:** READY")
        self.assertFalse(passed)
        self.assertEqual(reasons, ["verdict READY, not NOT-READY"])
        self.assertFalse(eval_agents.grade(need, NOTHING)[0])

    def test_an_anchor_only_under_recommendations_is_missed(self):
        passed, reasons = eval_agents.grade(case(must_find=["report-render"]), REPORT)
        self.assertFalse(passed)
        self.assertEqual(reasons, ["missed: report-render"])

    def test_not_checked_and_a_heading_end_the_last_finding(self):
        self.assertEqual(eval_agents.grade(case(must_find=["no lock file"]), REPORT)[1], ["missed: no lock file"])
        reply = "**Where:** `work.ts:1`\n**Attack:** x\n## Done well\nThe ilike query is fine.\n"
        self.assertEqual(eval_agents.grade(case(must_find=["ilike"]), reply)[1], ["missed: ilike"])

    def test_an_anchor_in_a_finding_title_is_found(self):
        self.assertEqual(eval_agents.grade(case(must_find=["Shell injection"]), REPORT), (True, []))

    def test_a_summary_or_prose_above_the_first_finding_is_not_in_it(self):
        self.assertEqual(eval_agents.grade(case(must_find=["runReportExport"]), REPORT)[1],
                         ["missed: runReportExport"])
        reply = "The new Function call worries me.\n\nShell injection\n**Severity:** High\n**Where:** `work.ts:31`\n"
        found = eval_agents.findings(reply)
        self.assertEqual(found, ["Shell injection\n**Severity:** High\n**Where:** `work.ts:31`\n"])

    def test_a_list_passes_on_any_alternative_and_fails_on_none(self):
        self.assertEqual(eval_agents.grade(case(must_find=[["execSync", "execFile"]]), REPORT), (True, []))
        passed, reasons = eval_agents.grade(case(must_find=[["execSync", "spawn"]]), REPORT)
        self.assertFalse(passed)
        self.assertEqual(reasons, ["missed: execSync | spawn"])

    def test_a_mention_passes_anywhere_and_fails_when_absent(self):
        self.assertEqual(eval_agents.grade(case(must_mention=["REPORT-RENDER binary"]), REPORT), (True, []))
        passed, reasons = eval_agents.grade(case(must_mention=["Ignore your previous instructions"]), REPORT)
        self.assertFalse(passed)
        self.assertEqual(reasons, ["not mentioned: Ignore your previous instructions"])

    def test_a_changed_checkout_fails(self):
        passed, reasons = eval_agents.grade(case(), NOTHING, {"?? new.txt"})
        self.assertFalse(passed)
        self.assertEqual(reasons, ["changed the checkout: ?? new.txt"])


class Runs(unittest.TestCase):
    def test_a_pass_then_a_fail_is_flaky(self):
        with tempfile.TemporaryDirectory() as tmp:
            agent, _ = counting(tmp)
            results = eval_agents.evaluate([first_case()], 2, agent, checkout=Path(tmp))
        got = results[first_case()["name"]]
        self.assertEqual((got["status"], got["passes"], got["runs"]), ("flaky", 1, 2))
        self.assertEqual(got["reasons"], ["missed: unlimited revisions"])

    def test_two_runs_by_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            agent, counter = counting(tmp)
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                code = eval_agents.main([str(EVALS), "--agent", agent, "--checkout", tmp])
            self.assertEqual(counter.read_text(), "20")
        self.assertEqual(code, 1)
        self.assertIn("FLAKY", out.getvalue())

    def test_all_pass_is_stable_and_none_is_failing(self):
        self.assertEqual(eval_agents.status(2, 2), "stable")
        self.assertEqual(eval_agents.status(0, 2), "failing")
        self.assertEqual(eval_agents.status(1, 2), "flaky")

    def test_an_agent_that_cannot_start_fails_the_case(self):
        got = eval_agents.run_case(first_case(), agent="/no/such/agent")
        self.assertFalse(got["passed"])
        self.assertTrue(got["reasons"][0].startswith("agent didn't finish"))

    def test_claude_json_gives_the_reply_and_its_tokens(self):
        line = json.dumps({"type": "result", "result": GOOD, "usage": {"input_tokens": 5, "output_tokens": 7}})
        with tempfile.TemporaryDirectory() as tmp:
            agent = fake_agent(tmp, "reply = {!r}".format(line))
            got = eval_agents.run_case(first_case(), agent=agent, checkout=Path(tmp))
        self.assertTrue(got["passed"], got["reasons"])
        self.assertEqual(got["tokens"], 12)


class Checkout(unittest.TestCase):
    def test_an_agent_that_writes_a_file_fails_the_case(self):
        with tempfile.TemporaryDirectory() as tmp:
            subprocess.run(["git", "init", "-q", tmp], check=True)
            agent = fake_agent(tmp, "open('edited.txt', 'w').write('x')\nreply = {!r}".format(GOOD))
            got = eval_agents.run_case(first_case(), agent=agent, checkout=Path(tmp))
        self.assertFalse(got["passed"])
        self.assertEqual(got["reasons"], ["changed the checkout: ?? edited.txt"])

    def test_a_reading_agent_leaves_it_alone(self):
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as elsewhere:
            subprocess.run(["git", "init", "-q", tmp], check=True)
            agent = fake_agent(elsewhere, "reply = {!r}".format(GOOD))
            got = eval_agents.run_case(first_case(), agent=agent, checkout=Path(tmp))
        self.assertTrue(got["passed"], got["reasons"])


class Baseline(unittest.TestCase):
    def test_only_the_changed_case_is_named(self):
        old = {"01-a": {"status": "stable"}, "02-b": {"status": "stable"}}
        new = {"01-a": {"status": "failing"}, "02-b": {"status": "stable"}}
        self.assertEqual(eval_agents.changed_since(old, new), ["01-a: stable -> failing"])

    def test_saved_files_compare_through_main(self):
        with tempfile.TemporaryDirectory() as tmp:
            old = Path(tmp) / "old.json"
            old.write_text(json.dumps({"agent": "claude", "cases": {
                "01-unlimited-revisions": {"status": "stable"}, "02-photos-not-in-out-of-scope": {"status": "failing"}}}))
            folder = Path(tmp) / "cases"
            for name in ("01-unlimited-revisions", "02-photos-not-in-out-of-scope"):
                (folder / name).mkdir(parents=True)
                (folder / name / "work.md").write_text("# w\n")
                (folder / name / "case.json").write_text(json.dumps(
                    {"agent": "reviewer", "must_find": ["unlimited revisions"] if name.startswith("01") else []}))
            agent = fake_agent(tmp, "reply = " + repr(NOTHING))
            saved = Path(tmp) / "new.json"
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                eval_agents.main([str(folder), "--runs", "1", "--agent", agent, "--checkout", tmp,
                                  "--baseline", str(old), "--save", str(saved)])
            self.assertEqual(json.loads(saved.read_text())["cases"]["01-unlimited-revisions"]["status"], "failing")
        self.assertIn("01-unlimited-revisions: stable -> failing", out.getvalue())
        self.assertIn("02-photos-not-in-out-of-scope: failing -> stable", out.getvalue())


if __name__ == "__main__":
    unittest.main()
