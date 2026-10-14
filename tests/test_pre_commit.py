"""Run with: python3 -m unittest discover -s tests"""
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HOOK = ROOT / ".githooks" / "pre-commit"

# Built when the test runs, so this file never trips the hook or CI's gitleaks itself.
FAKE_KEY = "AKIA" + "A" * 16

# Keep the person's own git config, and any repo a calling hook points at, out of these repos.
ISOLATED = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
ISOLATED.update(GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1")


class PreCommitHook(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.git("init", "-q")
        self.git("config", "user.name", "Test")
        self.git("config", "user.email", "test@example.com")
        self.git("config", "core.hooksPath", ".githooks")
        (self.root / ".githooks").mkdir()
        shutil.copy2(HOOK, self.root / ".githooks" / "pre-commit")

    def git(self, *args):
        return subprocess.run(["git", "-C", str(self.root)] + list(args), env=ISOLATED,
                              capture_output=True, text=True)

    def stage(self, name, text):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        self.assertEqual(self.git("add", "--", name).returncode, 0)

    def commit(self):
        done = self.git("commit", "-q", "-m", "test")
        return done.returncode, done.stdout + done.stderr

    def test_a_secret_in_a_name_with_a_space_is_blocked(self):
        self.stage("a b.txt", "key = " + FAKE_KEY + "\n")
        code, out = self.commit()
        self.assertNotEqual(code, 0, out)
        self.assertIn("BLOCKED: a b.txt contains", out)

    def test_a_secret_added_to_a_renamed_file_is_blocked(self):
        self.stage("old.txt", "".join("line {}\n".format(n) for n in range(20)))
        self.assertEqual(self.commit()[0], 0)
        self.assertEqual(self.git("mv", "old.txt", "new.txt").returncode, 0)
        with open(self.root / "new.txt", "a") as f:
            f.write("key = " + FAKE_KEY + "\n")
        self.git("add", "new.txt")
        self.assertIn("R", self.git("diff", "--cached", "--name-status").stdout)
        code, out = self.commit()
        self.assertNotEqual(code, 0, out)
        self.assertIn("BLOCKED: new.txt contains", out)

    def test_a_staged_env_file_is_blocked_by_name(self):
        self.stage(".env", "NAME=value\n")
        code, out = self.commit()
        self.assertNotEqual(code, 0, out)
        self.assertIn("BLOCKED: .env looks like a credential file", out)

    def test_a_clean_file_with_a_space_commits(self):
        self.stage("notes file.txt", "Nothing secret here.\n")
        code, out = self.commit()
        self.assertEqual(code, 0, out)

    def test_an_unfinished_proposal_is_blocked_by_its_gate(self):
        example = self.root / "examples" / "proposal"
        shutil.copytree(ROOT / "examples" / "proposal" / "gates", example / "gates")
        shutil.copytree(ROOT / "examples" / "proposal" / "data", example / "data")
        self.stage("examples/proposal/proposals/draft.md", "# Proposal\n\n" + "TO" + "DO\n")
        code, out = self.commit()
        self.assertNotEqual(code, 0, out)
        self.assertIn("FAIL examples/proposal/proposals/draft.md", out)


if __name__ == "__main__":
    unittest.main()
