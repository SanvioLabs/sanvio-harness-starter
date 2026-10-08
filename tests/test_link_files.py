"""Run with: python3 -m unittest discover -s tests"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from link_files import link_text  # noqa: E402 (the import needs scripts/ on the path first)

FILES = {"LICENSE", "AGENTS.md", "steering/gates.md", "steering/operating.md", "skills/learn/SKILL.md"}
DIRS = {"steering", "skills", "skills/learn"}


def link(md, text):
    return link_text(md, text, FILES, DIRS)


class LinkFiles(unittest.TestCase):
    def test_a_tracked_file_becomes_a_link(self):
        self.assertEqual(link("README.md", "Read `AGENTS.md` first."),
                         ("Read [`AGENTS.md`](AGENTS.md) first.", 1))

    def test_the_link_is_relative_to_the_file(self):
        text, _ = link("steering/gates.md", "See `AGENTS.md` and `operating.md`.")
        self.assertEqual(text, "See [`AGENTS.md`](../AGENTS.md) and [`operating.md`](operating.md).")

    def test_a_folder_keeps_its_slash(self):
        self.assertEqual(link("README.md", "`skills/learn/`")[0], "[`skills/learn/`](skills/learn/)")

    def test_a_file_with_no_extension_becomes_a_link(self):
        self.assertEqual(link("README.md", "See `LICENSE`.")[0], "See [`LICENSE`](LICENSE).")

    def test_a_bare_folder_name_stays_plain(self):
        self.assertEqual(link("README.md", "the `steering` idea"), ("the `steering` idea", 0))

    def test_an_untracked_name_stays_plain(self):
        self.assertEqual(link("README.md", "`company/COMPANY.md` and `.env`"), ("`company/COMPANY.md` and `.env`", 0))

    def test_another_projects_file_stays_plain(self):
        text = "A project's own `AGENTS.md` adds to these.\nRead its\n`AGENTS.md`."
        self.assertEqual(link("README.md", text), (text, 0))

    def test_code_blocks_headings_and_frontmatter_stay_plain(self):
        text = "---\ndescription: reads `AGENTS.md`\n---\n# `AGENTS.md`\n```\ncat `AGENTS.md`\n```"
        self.assertEqual(link("skills/learn/SKILL.md", text), (text, 0))

    def test_running_twice_changes_nothing(self):
        once, _ = link("README.md", "Read `AGENTS.md` and `steering/`.")
        self.assertEqual(link("README.md", once), (once, 0))


if __name__ == "__main__":
    unittest.main()
