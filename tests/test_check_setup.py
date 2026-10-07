"""Run with: python3 -m unittest discover -s tests"""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import check_setup  # noqa: E402 (the import needs scripts/ on the path first)

# Keep the person's own git config out of these repos, so an unset key is unset.
ISOLATED = dict(os.environ, GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1")


class SetupCheck(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.git("init", "-q")
        self.env = os.environ.copy()
        os.environ.update(ISOLATED)
        self.addCleanup(self.restore_env)

    def restore_env(self):
        os.environ.clear()
        os.environ.update(self.env)

    def git(self, *args):
        subprocess.run(["git", "-C", str(self.root)] + list(args), check=True, env=ISOLATED)

    def wire_links(self):
        (self.root / "skills").mkdir()
        (self.root / "AGENTS.md").write_text("# Rules\n")
        (self.root / "CLAUDE.md").write_text("@AGENTS.md\n")
        (self.root / ".claude").mkdir()
        (self.root / ".claude" / "skills").symlink_to("../skills")
        (self.root / ".kiro" / "steering").mkdir(parents=True)
        (self.root / ".kiro" / "steering" / "project.md").symlink_to("../../AGENTS.md")

    def test_python_39_passes_and_38_fails(self):
        self.assertEqual(check_setup.check_python((3, 9, 0))[0], "PASS")
        self.assertEqual(check_setup.check_python((3, 8, 18))[0], "FAIL")

    def test_unset_hooks_path_fails_with_the_fix(self):
        status, line, fix = check_setup.check_hooks(self.root)
        self.assertEqual(status, "FAIL")
        self.assertIn("not set", line)
        self.assertIn("git config core.hooksPath .githooks", fix)

    def test_githooks_passes(self):
        self.git("config", "core.hooksPath", ".githooks")
        self.assertEqual(check_setup.check_hooks(self.root)[0], "PASS")

    def test_another_hooks_path_fails_and_names_it(self):
        self.git("config", "core.hooksPath", ".husky")
        status, line, _ = check_setup.check_hooks(self.root)
        self.assertEqual(status, "FAIL")
        self.assertIn(".husky", line)

    def test_wired_links_pass(self):
        self.wire_links()
        self.assertEqual(check_setup.check_links(self.root)[0], "PASS")

    def test_a_link_that_arrived_as_text_fails(self):
        self.wire_links()
        (self.root / ".claude" / "skills").unlink()
        (self.root / ".claude" / "skills").write_text("../skills")
        status, line, _ = check_setup.check_links(self.root)
        self.assertEqual(status, "FAIL")
        self.assertIn(".claude/skills", line)

    def test_no_remote_passes(self):
        self.assertEqual(check_setup.check_remote(self.root)[0], "PASS")

    def test_the_public_starter_as_origin_warns(self):
        self.git("remote", "add", "origin", "git@github.com:SanvioLabs/sanvio-harness-starter.git")
        status, line, fix = check_setup.check_remote(self.root)
        self.assertEqual(status, "WARN")
        self.assertIn("public starter", line)
        self.assertIn("private copy", fix)

    def test_a_token_in_the_remote_url_is_never_printed(self):
        self.git("remote", "add", "origin", "https://someone:ghp_notarealtoken@github.com/acme/harness.git")
        _, line, _ = check_setup.check_remote(self.root)
        self.assertNotIn("ghp_notarealtoken", line)
        self.assertIn("https://github.com/acme/harness.git", line)

    def test_the_example_proposal_passes_the_gate_in_this_repo(self):
        self.assertEqual(check_setup.check_gate(ROOT)[0], "PASS")

    def test_a_missing_example_warns_rather_than_fails(self):
        self.assertEqual(check_setup.check_gate(self.root)[0], "WARN")

    def test_no_company_record_warns_and_points_at_orientation(self):
        status, _, fix = check_setup.check_company(self.root)
        self.assertEqual(status, "WARN")
        self.assertIn("/orientation", fix)

    def test_a_written_company_record_passes(self):
        (self.root / "company").mkdir()
        (self.root / "company" / "COMPANY.md").write_text("# Company\n")
        self.assertEqual(check_setup.check_company(self.root)[0], "PASS")

    def test_the_company_record_never_gets_committed(self):
        def ignored(path):
            return subprocess.run(["git", "-C", str(ROOT), "check-ignore", "-q", path],
                                  env=ISOLATED).returncode == 0
        self.assertTrue(ignored("company/COMPANY.md"))
        self.assertTrue(ignored("company/DATA.md"))
        self.assertFalse(ignored("company/README.md"))
        self.assertFalse(ignored("company/COMPANY.example.md"))

    def write_skill(self, folder, name):
        path = Path(folder) / name / "SKILL.md"
        path.parent.mkdir(parents=True)
        path.write_text("---\nname: {}\ndescription: x\n---\n".format(name))

    def test_a_personal_skill_with_a_repo_skills_name_warns(self):
        home = self.root / "home"
        self.write_skill(self.root / "skills", "review-pr")
        self.write_skill(home / ".claude" / "skills", "review-pr")
        status, line, _ = check_setup.check_shadowed_skills(self.root, home)
        self.assertEqual(status, "WARN")
        self.assertIn("review-pr", line)

    def test_a_personal_skill_renamed_by_frontmatter_still_counts(self):
        home = self.root / "home"
        self.write_skill(self.root / "skills", "review-pr")
        folder = home / ".claude" / "skills" / "my-pr-review"
        folder.mkdir(parents=True)
        (folder / "SKILL.md").write_text("---\nname: review-pr\ndescription: x\n---\n")
        self.assertEqual(check_setup.check_shadowed_skills(self.root, home)[0], "WARN")

    def test_different_personal_skills_pass(self):
        home = self.root / "home"
        self.write_skill(self.root / "skills", "review-pr")
        self.write_skill(home / ".claude" / "skills", "archify")
        self.assertEqual(check_setup.check_shadowed_skills(self.root, home)[0], "PASS")

    def test_no_personal_skills_folder_passes(self):
        self.write_skill(self.root / "skills", "review-pr")
        self.assertEqual(check_setup.check_shadowed_skills(self.root, self.root / "nohome")[0], "PASS")

    def test_projects_are_never_committed_but_stay_searchable(self):
        def ignored(path):
            return subprocess.run(["git", "-C", str(ROOT), "check-ignore", "-q", path],
                                  env=ISOLATED).returncode == 0
        self.assertTrue(ignored("projects/billing/app.py"))
        self.assertFalse(ignored("projects/README.md"))
        searchable = (ROOT / ".ignore").read_text()
        self.assertIn("!/projects/", searchable)
        self.assertIn("!/company/", searchable)


if __name__ == "__main__":
    unittest.main()
