"""Run with: python3 -m unittest discover -s tests"""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WORKFLOW = ROOT / "examples" / "ci" / "review-pr.yml"
SECRET_REF = re.compile(r"\$\{\{ secrets\.[A-Z][A-Z0-9_]* \}\}")
KEY_SHAPES = re.compile(r"sk-ant|ghp_|gho_|github_pat_|AKIA[0-9A-Z]{8}|-----BEGIN")


def code(text):
    """The file without its comments, which explain the rules and so name them."""
    return "\n".join(line for line in text.splitlines() if not line.lstrip().startswith("#"))


def block(text, key):
    """The indented lines under a top-level `key:`, as a list of stripped lines."""
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if re.match(r"^{}:\s*$".format(re.escape(key)), line):
            out = []
            for follow in lines[i + 1:]:
                if follow.strip() and not follow.startswith(" "):
                    break
                if follow.strip():
                    out.append(follow.strip())
            return out
    return None


def run_lines(text):
    """Every line inside a `run:` block, where an expression is a script injection."""
    out, indent = [], None
    for line in text.splitlines():
        if indent is not None:
            if not line.strip() or len(line) - len(line.lstrip()) > indent:
                out.append(line)
                continue
            indent = None
        if re.match(r"^\s*run:\s*[|>]", line):
            indent = len(line) - len(line.lstrip())
    return out


class ReviewPrWorkflow(unittest.TestCase):
    def setUp(self):
        self.assertTrue(WORKFLOW.is_file(), "examples/ci/review-pr.yml doesn't exist")
        self.text = WORKFLOW.read_text()
        self.code = code(self.text)

    def test_it_runs_on_pull_request_and_never_the_target_variant(self):
        self.assertNotIn("pull_request_target", self.text)
        on = block(self.code, "on")
        self.assertIsNotNone(on, "no top-level on: block")
        self.assertIn("pull_request:", on)
        types = [line for line in on if line.startswith("types:")]
        self.assertEqual(len(types), 1, "pull_request needs one types: list")
        for kind in ("opened", "synchronize", "reopened"):
            self.assertIn(kind, types[0])

    def test_it_runs_on_nothing_but_pull_request(self):
        on = block(self.code, "on")
        triggers = [line for line in on if re.match(r"^[a-z_]+:", line) and not line.startswith("types:")]
        self.assertEqual(triggers, ["pull_request:"])

    def test_permissions_are_read_contents_and_write_comments_only(self):
        permissions = block(self.code, "permissions")
        self.assertIsNotNone(permissions, "no top-level permissions: block")
        self.assertEqual(sorted(permissions), ["contents: read", "pull-requests: write"])
        self.assertNotIn("contents: write", self.text)
        self.assertNotIn("write-all", self.text)

    def test_no_job_widens_the_permissions(self):
        self.assertEqual(len(re.findall(r"^\s*permissions:", self.code, re.M)), 1)

    def test_secrets_are_only_ever_referenced_by_name(self):
        for number, line in enumerate(self.text.splitlines(), 1):
            leftover = SECRET_REF.sub("", line)
            self.assertNotIn("secrets.", leftover,
                             "line {}: reference a secret as ${{{{ secrets.NAME }}}}".format(number))
        self.assertTrue(SECRET_REF.search(self.code), "the workflow references no secret")
        self.assertIsNone(KEY_SHAPES.search(self.text), "something in the file looks like a key")

    def test_a_pull_request_from_a_fork_skips_with_a_notice(self):
        self.assertIn("github.event.pull_request.head.repo.full_name", self.code)
        self.assertIn("::notice::", self.code)

    def test_no_expression_is_expanded_inside_a_script(self):
        self.assertTrue(run_lines(self.code), "found no run: blocks to check")
        for line in run_lines(self.code):
            self.assertNotIn("${{", line, "pass it through env: and read it as a variable")

    def test_the_skill_points_at_the_example(self):
        skill = (ROOT / "skills" / "review-pr" / "SKILL.md").read_text()
        self.assertIn("examples/ci/review-pr.yml", skill)


if __name__ == "__main__":
    unittest.main()
