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


PROJECT_CHECKS = ROOT / "examples" / "ci" / "project-checks.yml"


def step_run_block(text, name):
    """The lines of the `run: |` block under the step called `name`, or None."""
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if re.match(r"^\s*-\s*name:\s*{}\s*$".format(re.escape(name)), line):
            break
    else:
        return None
    for j in range(i + 1, len(lines)):
        match = re.match(r"^(\s*)run:\s*\|\s*$", lines[j])
        if match:
            indent = len(match.group(1))
            block = []
            for body in lines[j + 1:]:
                if body.strip() and len(body) - len(body.lstrip()) <= indent:
                    break
                block.append(body)
            return block
        if re.match(r"^\s*-\s", lines[j]):
            return None
    return None


class ProjectChecksExample(unittest.TestCase):
    def setUp(self):
        self.assertTrue(PROJECT_CHECKS.exists(), "examples/ci/project-checks.yml is missing")
        self.text = PROJECT_CHECKS.read_text()

    def test_coverage_runs_only_behind_the_pytest_cov_check(self):
        block = step_run_block(self.text, "Tests")
        self.assertIsNotNone(block, "no Tests step with a run: block")
        guard = next((i for i, line in enumerate(block) if "import pytest_cov" in line), None)
        self.assertIsNotNone(guard, "the Tests step doesn't check for pytest-cov")
        indent = len(block[guard]) - len(block[guard].lstrip())
        end = next(
            (i for i in range(guard + 1, len(block))
             if block[i].strip() in ("else", "fi") and len(block[i]) - len(block[i].lstrip()) == indent),
            None,
        )
        self.assertIsNotNone(end, "the pytest-cov check has no else or fi")
        uses = [i for i, line in enumerate(block) if "--cov" in line]
        self.assertTrue(uses, "the Tests step never runs coverage")
        for i in uses:
            self.assertTrue(guard < i < end, "--cov outside the pytest-cov check: " + block[i].strip())

    def test_the_workflow_sets_no_coverage_threshold(self):
        # The bar is the project's, in its own pyproject.toml.
        code = "\n".join(line for line in self.text.splitlines() if not line.lstrip().startswith("#"))
        self.assertNotIn("--cov-fail-under", code)
        self.assertNotIn("fail_under", code)


WORKFLOWS = sorted((ROOT / ".github" / "workflows").glob("*.yml")) + sorted((ROOT / "examples" / "ci").glob("*.yml"))


def unpinned_actions(text):
    """Every `uses:` that names an action by tag or branch rather than a full commit SHA."""
    refs = re.findall(r"^\s*(?:-\s*)?uses:\s*([^\s#]+)", text, re.M)
    return [r for r in refs if not r.startswith("./") and not re.search(r"@[0-9a-f]{40}$", r)]


def unquoted_heredocs(text):
    """Every heredoc opened with a bare delimiter, whose body the shell would expand."""
    return re.findall(r"<<-?\s*([A-Za-z_]\w*)\b", text)


def unchecked_downloads(text):
    """Every curl or wget that fetches something to run, in a workflow with no pinned sha256 check."""
    commands = re.findall(r"\b(?:curl|wget)\b[^\n]*", text.replace("\\\n", " "))
    fetched = [c for c in commands if re.search(r"\|\s*(?:tar|sh|bash)\b|\s-[oO]\s|\.(?:tar\.gz|tgz|zip|deb)\b", c)]
    checked = re.search(r"sha256sum\s+(?:-c|--check)\b", text) and re.search(r"\b[0-9a-f]{64}\b", text)
    return [] if checked else fetched


class EveryWorkflow(unittest.TestCase):
    def test_every_download_is_checked_against_a_pinned_sha256(self):
        # A release asset can be replaced after it's published; a checksum
        # written here can't.
        for path in WORKFLOWS:
            self.assertEqual(unchecked_downloads(path.read_text()), [], path.name)

    def test_the_download_check_catches_an_unchecked_binary(self):
        unchecked = 'curl -sSfL "https://example.com/tool_1.0_linux_x64.tar.gz" \\\n  | tar -xz -C /tmp tool\n'
        self.assertEqual(len(unchecked_downloads(unchecked)), 1)
        checked = (
            "SHA256=" + "a" * 64 + "\n"
            'curl -sSfL -o /tmp/tool.tar.gz "https://example.com/tool_1.0_linux_x64.tar.gz"\n'
            'echo "${SHA256}  /tmp/tool.tar.gz" | sha256sum -c -\n'
        )
        self.assertEqual(unchecked_downloads(checked), [])
        self.assertEqual(unchecked_downloads('curl -sSf "https://api.github.com/repos/o/r"\n'), [])


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
