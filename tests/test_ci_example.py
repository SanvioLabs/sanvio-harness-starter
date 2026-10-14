"""Run with: python3 -m unittest discover -s tests"""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WORKFLOW = ROOT / "examples" / "ci" / "loop.yml"

# The one way a secret may be named: ${{ secrets.NAME }}.
SECRET_REF = re.compile(r"^\$\{\{\s*secrets\.[A-Z][A-Z0-9_]*\s*\}\}$")


def top_level_block(text, key):
    """The indented lines under a top-level `key:`, or None."""
    match = re.search(r"^{}:[ \t]*\n((?:[ \t]+\S.*\n?|[ \t]*\n)*)".format(re.escape(key)), text, re.M)
    return match.group(1) if match else None


def bad_secret_references(text):
    """Every `secrets` mention that isn't a whole ${{ secrets.NAME }} expression."""
    code = "\n".join(line for line in text.splitlines() if not line.lstrip().startswith("#"))
    inside = [m.group(0) for m in re.finditer(r"\$\{\{.*?\}\}", code)]
    bad = [e for e in inside if "secrets" in e and not SECRET_REF.match(e)]
    outside = re.sub(r"\$\{\{.*?\}\}", "", code)
    if re.search(r"\bsecrets\b", outside):
        bad.append("a bare 'secrets' outside an expression")
    return bad


class LoopWorkflowExample(unittest.TestCase):
    def setUp(self):
        self.assertTrue(WORKFLOW.exists(), "examples/ci/loop.yml is missing")
        self.text = WORKFLOW.read_text()

    def test_it_runs_one_pass_of_the_loop(self):
        self.assertRegex(self.text, r"(?m)^\s*python3 scripts/loop\.py run --once\s*$")

    def test_no_token_is_left_where_the_tests_could_read_it(self):
        self.assertRegex(self.text, r"(?m)^\s*persist-credentials:\s*false\s*$")
        self.assertRegex(self.text, r"(?m)^\s*gh auth setup-git\s*$")

    def test_the_agent_cli_is_pinned(self):
        self.assertRegex(self.text, r"@anthropic-ai/claude-code@\d+\.\d+\.\d+")

    def test_it_runs_on_a_schedule_and_by_hand(self):
        triggers = top_level_block(self.text, "on")
        self.assertIsNotNone(triggers, "no on: block")
        self.assertRegex(triggers, r"(?m)^\s+schedule:")
        self.assertRegex(triggers, r"(?m)^\s+workflow_dispatch:")

    def test_it_asks_only_for_what_one_pass_uses(self):
        block = top_level_block(self.text, "permissions")
        self.assertIsNotNone(block, "no top-level permissions: block")
        granted = dict(re.findall(r"^\s+([a-z-]+):\s*(\S+)\s*$", block, re.M))
        self.assertEqual(granted, {"contents": "write", "issues": "write", "pull-requests": "write"})

    def test_it_keeps_the_loop_folder_after_the_runner_is_gone(self):
        self.assertRegex(self.text, r"(?m)^\s*uses:\s*actions/upload-artifact@")
        self.assertRegex(self.text, r"(?m)^\s*path:\s*\.loop/?\s*$")
        # a .loop folder is hidden, and the action skips hidden files unless told not to
        self.assertRegex(self.text, r"(?m)^\s*include-hidden-files:\s*true\s*$")

    def test_secrets_are_named_never_written(self):
        self.assertEqual(bad_secret_references(self.text), [])
        self.assertIn("${{ secrets.ANTHROPIC_API_KEY }}", self.text)
        self.assertNotRegex(self.text, r"sk-ant-|ghp_|github_pat_")

    def test_the_reference_check_catches_a_pasted_key(self):
        self.assertEqual(bad_secret_references("ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}"), [])
        self.assertTrue(bad_secret_references("KEY: ${{ toJSON(secrets) }}"))
        self.assertTrue(bad_secret_references("KEY: ${{ secrets['ANTHROPIC_API_KEY'] }}"))
        self.assertTrue(bad_secret_references("run: echo $secrets"))

    def test_how_it_works_says_where_it_runs_and_the_limits(self):
        text = (ROOT / "HOW-IT-WORKS.md").read_text()
        self.assertIn("### Off your laptop", text)
        self.assertIn("examples/ci/loop.yml", text)
        self.assertIn("GITHUB_TOKEN", text)


WORKFLOWS = sorted((ROOT / ".github" / "workflows").glob("*.yml")) + sorted((ROOT / "examples" / "ci").glob("*.yml"))


def unpinned_actions(text):
    """Every `uses:` that names an action by tag or branch rather than a full commit SHA."""
    refs = re.findall(r"^\s*(?:-\s*)?uses:\s*([^\s#]+)", text, re.M)
    return [r for r in refs if not r.startswith("./") and not re.search(r"@[0-9a-f]{40}$", r)]


def unquoted_heredocs(text):
    """Every heredoc opened with a bare delimiter, whose body the shell would expand."""
    return re.findall(r"<<-?\s*([A-Za-z_]\w*)\b", text)


class EveryWorkflow(unittest.TestCase):
    def test_every_action_is_pinned_to_a_commit(self):
        # A tag can be moved to other code; a commit can't.
        for path in WORKFLOWS:
            self.assertEqual(unpinned_actions(path.read_text()), [], path.name)

    def test_the_pin_check_catches_a_tag(self):
        self.assertEqual(unpinned_actions("      - uses: actions/checkout@v4\n"), ["actions/checkout@v4"])
        self.assertEqual(unpinned_actions("      - uses: actions/checkout@" + "a" * 40 + " # v4\n"), [])

    def test_every_heredoc_is_quoted(self):
        for path in WORKFLOWS:
            self.assertEqual(unquoted_heredocs(path.read_text()), [], path.name)

    def test_the_heredoc_check_catches_a_bare_delimiter(self):
        self.assertEqual(unquoted_heredocs('cat > f <<EOF\n'), ["EOF"])
        self.assertEqual(unquoted_heredocs("cat > f <<'EOF'\n"), [])


if __name__ == "__main__":
    unittest.main()
