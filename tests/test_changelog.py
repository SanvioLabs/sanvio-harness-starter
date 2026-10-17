"""Run with: python3 -m unittest discover -s tests"""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HEADING = re.compile(r"^## (\d{4}-\d{2}-\d{2}): (\S.*)$", re.M)


def entries(text):
    """(date, name, body) for each entry, in file order."""
    found = list(HEADING.finditer(text))
    out = []
    for i, match in enumerate(found):
        end = found[i + 1].start() if i + 1 < len(found) else len(text)
        out.append((match.group(1), match.group(2), text[match.end():end]))
    return out


def problems(text):
    """Every reason skills/whats-new couldn't read this log. Empty means it can."""
    found = []
    items = entries(text)
    if not items:
        found.append("no entries: each starts with '## YYYY-MM-DD: Name'")
    names = [name for _, name, _ in items]
    for name in sorted({n for n in names if names.count(n) > 1}):
        found.append("two entries named '{}': headings are how copies are compared".format(name))
    for (date, name, _), (next_date, next_name, _) in zip(items, items[1:]):
        if next_date > date:
            found.append("'{}' is above the newer '{}': newest first".format(name, next_name))
    for _, name, body in items:
        if "**Do:**" not in body:
            found.append("'{}' has no **Do:** line".format(name))
    return found


GOOD = """# What's new

## 2026-10-08: Second

Adds a thing.

**Do:** nothing.

## 2026-10-08: First

**Do:** run the setup check.
"""


class Changelog(unittest.TestCase):
    def test_the_log_the_starter_ships_is_readable(self):
        self.assertEqual(problems((ROOT / "CHANGELOG.md").read_text()), [])

    def test_a_good_log_passes(self):
        self.assertEqual(problems(GOOD), [])

    def test_an_entry_without_a_do_line_fails(self):
        self.assertIn("'First' has no **Do:** line", problems(GOOD.replace("**Do:** run the setup check.", "")))

    def test_an_older_entry_above_a_newer_one_fails(self):
        self.assertTrue(problems(GOOD.replace("2026-10-08: First", "2026-10-09: First")))

    def test_two_entries_with_one_name_fail(self):
        self.assertTrue(problems(GOOD.replace("2026-10-08: Second", "2026-10-08: First")))

    def test_a_log_with_no_entries_fails(self):
        self.assertTrue(problems("# What's new\n\nNothing yet.\n"))


class WhatsNewCommands(unittest.TestCase):
    """The listing commands in skills/whats-new/SKILL.md, run as written against a sample log."""

    LOG = "# What's new\n\nIntro.\n\n## 2026-10-13: Third\n\nx\n\n## 2026-10-13: Second\n\nx\n\n## 2026-10-12: First\n\nx\n\n## 2026-10-11: Older\n\nx\n"

    def command(self, starts):
        skill = (ROOT / "skills" / "whats-new" / "SKILL.md").read_text()
        found = [line.strip() for line in skill.splitlines() if line.strip().startswith(starts)]
        self.assertEqual(len(found), 1, "one command starting " + starts)
        return found[0]

    def run_in(self, folder, cmd, env=None):
        import subprocess
        done = subprocess.run(["bash", "-c", cmd], cwd=folder, capture_output=True, text=True, env=env)
        return [line for line in done.stdout.splitlines() if line]

    def test_since_a_date_lists_every_entry_on_or_after_it(self):
        import tempfile
        cmd = self.command("grep '^## ' CHANGELOG.md | awk")
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "CHANGELOG.md").write_text(self.LOG)
            got = self.run_in(tmp, cmd)
        self.assertEqual(got, ["## 2026-10-13: Third", "## 2026-10-13: Second", "## 2026-10-12: First"])

    def test_whats_new_lists_the_starters_headings_missing_here_in_order(self):
        import os
        import tempfile
        cmd = self.command("""grep '^## ' "${TMPDIR:-/tmp}/whats-new/CHANGELOG.md" | grep""")
        mine = self.LOG.replace("## 2026-10-13: Third\n\nx\n\n## 2026-10-13: Second\n\nx\n\n", "")
        with tempfile.TemporaryDirectory() as tmp:
            for folder, log in (("whats-new", self.LOG), ("copy", mine)):
                (Path(tmp) / folder).mkdir()
                (Path(tmp) / folder / "CHANGELOG.md").write_text(log)
            got = self.run_in(Path(tmp) / "copy", cmd, env=dict(os.environ, TMPDIR=tmp))
        self.assertEqual(got, ["## 2026-10-13: Third", "## 2026-10-13: Second"])


if __name__ == "__main__":
    unittest.main()
