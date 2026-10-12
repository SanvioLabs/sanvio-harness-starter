"""Run with: python3 -m unittest discover -s tests"""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Stelliad's Ticket Authoring Standard: its checker blocks a ticket missing any of these.
REQUIRED = ["Objective", "Why", "Acceptance Criteria", "Scope", "Risk"]


def headings(text):
    """The ## headings outside HTML comments, in order."""
    text = re.sub(r"<!--.*?-->", "", text, flags=re.S)
    return re.findall(r"^## (.+?)\s*$", text, flags=re.M)


class Tickets(unittest.TestCase):
    def test_the_issue_template_has_the_standards_required_sections_in_order(self):
        template = (ROOT / ".github" / "ISSUE_TEMPLATE" / "loop-task.md").read_text()
        self.assertEqual(headings(template), REQUIRED)

    def test_the_template_scope_has_both_halves(self):
        template = (ROOT / ".github" / "ISSUE_TEMPLATE" / "loop-task.md").read_text()
        self.assertIn("**In:**", template)
        self.assertIn("**Out:**", template)

    def test_the_steering_names_every_required_section(self):
        steering = (ROOT / "steering" / "tickets.md").read_text()
        for section in REQUIRED:
            self.assertIn("| **{}** |".format(section), steering)

    def test_guidance_sits_above_the_first_section(self):
        # Stelliad's checker reads comments as section text: a heading in one becomes an empty
        # section that blocks, and words in one fill the Risk level and the word floors.
        template = (ROOT / ".github" / "ISSUE_TEMPLATE" / "loop-task.md").read_text()
        body = template[template.index("## Objective"):]
        self.assertNotIn("<!--", body)

    def test_no_heading_hides_in_a_comment(self):
        template = (ROOT / ".github" / "ISSUE_TEMPLATE" / "loop-task.md").read_text()
        for comment in re.findall(r"<!--.*?-->", template, flags=re.S):
            self.assertNotRegex(comment, r"(?m)^#+ ")


if __name__ == "__main__":
    unittest.main()
