"""Run with: python3 -m unittest discover -s tests"""
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MODS_DIR = ROOT / "examples" / "mods"
MODS = sorted(p for p in MODS_DIR.iterdir() if (p / ".claude-plugin" / "plugin.json").is_file())
TIMEOUT = 60
NEEDS_CLAUDE = "needs Claude Code (claude) on the PATH"


def check_mod(folder):
    """Validate and test the mod in folder. None when both pass, else why not."""
    for verb in ("validate", "test"):
        command = ["claude", "plugin", verb, folder.name]
        try:
            result = subprocess.run(command, cwd=folder.parent, capture_output=True, text=True, timeout=TIMEOUT)
        except subprocess.TimeoutExpired:
            return "claude plugin {} {} didn't finish within {}s".format(verb, folder.name, TIMEOUT)
        if result.returncode != 0:
            tail = "\n".join((result.stdout + result.stderr).splitlines()[-40:])
            return "{} failed (exit {}):\n{}".format(" ".join(command), result.returncode, tail)
    return None


class Mods(unittest.TestCase):
    """Each mod under examples/mods/ validates and passes its own tests."""

    def setUp(self):
        if not shutil.which("claude"):
            self.skipTest(NEEDS_CLAUDE)


def add_mod_test(folder):
    def test(self):
        failure = check_mod(folder)
        self.assertIsNone(failure, failure)
    setattr(Mods, "test_" + folder.name.replace("-", "_"), test)


for _folder in MODS:
    add_mod_test(_folder)


class CheckModCatchesFailures(unittest.TestCase):
    """check_mod passes a mod as shipped, and fails one whose test fails."""

    def setUp(self):
        if not shutil.which("claude"):
            self.skipTest(NEEDS_CLAUDE)
        self.copy = Path(tempfile.mkdtemp()) / "harness-lens"
        self.addCleanup(shutil.rmtree, self.copy.parent)
        shutil.copytree(MODS_DIR / "harness-lens", self.copy)

    def test_a_mod_as_shipped_passes(self):
        self.assertIsNone(check_mod(self.copy))

    def test_a_failing_test_is_reported(self):
        with open(self.copy / "hooks" / "logic.test.ts", "a") as tests:
            tests.write("\ndescribe('broken', () => {\n"
                        "  test('deliberately fails', () => expect(1).toBe(2))\n})\n")
        failure = check_mod(self.copy)
        self.assertIsNotNone(failure, "check_mod passed a mod with a failing test")
        self.assertIn("harness-lens", failure)
        self.assertIn("deliberately fails", failure)


if __name__ == "__main__":
    unittest.main()
