"""Run with: python3 -m unittest discover -s tests"""
import getpass
import shutil
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import draw_dashboard  # noqa: E402 (needs scripts/ on the path first)

NEEDS_CLAUDE = "needs Claude Code (claude) on the PATH"
RUN = "run: python3 scripts/draw_dashboard.py"


class Picture(unittest.TestCase):
    """The dashboard README's picture and its text are what the pane draws now, and name no one."""

    @classmethod
    def setUpClass(cls):
        if not shutil.which("claude"):
            raise unittest.SkipTest(NEEDS_CLAUDE)
        cls.svg, cls.text = draw_dashboard.drawn()

    def test_the_svg_is_current(self):
        self.assertTrue(draw_dashboard.SVG.read_text() == self.svg,
                        "docs/harness-dashboard.svg isn't what the pane draws; " + RUN)

    def test_the_readme_text_is_current(self):
        self.assertTrue(draw_dashboard.details(draw_dashboard.README.read_text()) == self.text,
                        "the README's text version isn't what the pane draws; " + RUN)

    def test_the_svg_holds_no_path_or_user(self):
        for leak in (str(ROOT), str(Path.home()), getpass.getuser(), "/Users/", "/home/"):
            self.assertNotIn(leak, self.svg)


if __name__ == "__main__":
    unittest.main()
