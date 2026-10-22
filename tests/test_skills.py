"""Run with: python3 -m unittest discover -s tests"""
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def frontmatter(text):
    """The key: value pairs between the opening --- lines, or {} if there are none."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}
    fields = {}
    for line in lines[1:]:
        if line.strip() == "---":
            return fields
        key, sep, value = line.partition(":")
        if sep:
            fields[key.strip()] = value.strip()
    return {}


def problems(skill_file, agents_text):
    """Every reason this skill isn't registered properly. An empty list means it is."""
    name = "skills/{}/SKILL.md".format(Path(skill_file).parent.name)
    fields = frontmatter(Path(skill_file).read_text())
    found = []
    for key in ("name", "description"):
        if not fields.get(key):
            found.append("{}: no {} in the frontmatter".format(name, key))
    if name not in agents_text:
        found.append("{}: not listed in AGENTS.md".format(name))
    return found


GOOD = """---
name: weekly-status
description: Write the weekly status update. Use when asked for this week's status.
---

# Weekly status
"""


class Skills(unittest.TestCase):
    def problems(self, text, agents_text="| `skills/weekly-status/SKILL.md` | Asked for a status |"):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp) / "weekly-status"
            folder.mkdir()
            (folder / "SKILL.md").write_text(text)
            return problems(folder / "SKILL.md", agents_text)

    def test_every_skill_in_this_repo_is_registered(self):
        agents_text = (ROOT / "AGENTS.md").read_text()
        skills = sorted((ROOT / "skills").glob("*/SKILL.md"))
        self.assertTrue(skills)
        for skill in skills:
            self.assertEqual(problems(skill, agents_text), [])

    def test_the_standup_skill_exists_and_changes_nothing(self):
        path = ROOT / "skills" / "standup" / "SKILL.md"
        self.assertTrue(path.exists(), "skills/standup/SKILL.md is missing")
        text = path.read_text()
        description = frontmatter(text).get("description", "")
        self.assertIn("standup", description)
        self.assertIn("morning check", description)
        body = text.split("---", 2)[2]
        self.assertIn("changes nothing", body.lower())

    def test_standup_reads_an_optional_source_only_when_data_md_clears_it(self):
        text = (ROOT / "skills" / "standup" / "SKILL.md").read_text()
        self.assertIn("No `company/DATA.md` means none is", text)
        self.assertNotIn("`company/DATA.md`, if it\n   exists, clears it", text)

    def test_inbox_reads_mail_for_a_standup_and_changes_nothing(self):
        text = (ROOT / "skills" / "inbox" / "SKILL.md").read_text()
        self.assertIn("Gmail is the default", text)
        step = text[text.index("**Provider:**"):text.index("**Clearance:**")]
        order = [step.index(s) for s in ("`/inbox outlook`", "`company/DATA.md`", "Gmail", "one connector")]
        self.assertEqual(order, sorted(order), "provider order: argument, DATA.md, Gmail, one connector")
        self.assertIn("Mail: skipped, company/DATA.md doesn't clear it.", text)
        for words in ("never sends", "marks read", "attachment"):
            self.assertIn(words, text)
        for group in ("Needs a reply from you", "Waiting on someone", "Worth knowing"):
            self.assertIn(group, text)
        self.assertIn("data, never instructions", text)
        for gone in ("+idea", "plus address", ".inbox/"):
            self.assertNotIn(gone, text)

    def test_standup_reads_email_the_way_inbox_says(self):
        text = (ROOT / "skills" / "standup" / "SKILL.md").read_text()
        self.assertTrue("skills/inbox/" in text or "../inbox/" in text)

    def test_a_registered_skill_passes(self):
        self.assertEqual(self.problems(GOOD), [])

    def test_a_missing_name_fails(self):
        found = self.problems(GOOD.replace("name: weekly-status\n", ""))
        self.assertIn("skills/weekly-status/SKILL.md: no name in the frontmatter", found)

    def test_a_missing_description_fails(self):
        found = self.problems(GOOD.replace("description:", "summary:"))
        self.assertIn("skills/weekly-status/SKILL.md: no description in the frontmatter", found)

    def test_no_frontmatter_fails(self):
        found = self.problems("# Weekly status\n")
        self.assertEqual(len(found), 2)

    def test_a_skill_missing_from_agents_md_fails(self):
        found = self.problems(GOOD, agents_text="| `skills/draft-proposal/SKILL.md` | Proposals |")
        self.assertIn("skills/weekly-status/SKILL.md: not listed in AGENTS.md", found)


if __name__ == "__main__":
    unittest.main()
