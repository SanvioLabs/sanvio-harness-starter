"""Run with: python3 -m unittest discover -s tests"""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "examples" / "proposal" / "gates"))
from proposal_gate import check  # noqa: E402 (the import needs the example's gates/ on the path first)

RATES = {"roles": {"Engineer": 175, "Designer": 150}, "minimum_fee": 1000}

GOOD = """# Proposal

## Problem

Orders go missing.

## Scope

A pre-order page.

## Out of scope

Delivery.

## Fees

| Role | Hours | Rate | Amount |
|---|---|---|---|
| Engineer | 10 | $175 | $1,750 |
| Designer | 2 | $150 | $300 |

**Total: $2,050**

## Assumptions

The menu arrives before build.
"""


class ProposalGate(unittest.TestCase):
    def problems(self, text):
        with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False) as f:
            f.write(text)
        return check(f.name, RATES)

    def test_a_finished_proposal_passes(self):
        self.assertEqual(self.problems(GOOD), [])

    def test_a_placeholder_fails(self):
        found = self.problems(GOOD.replace("Delivery.", "{{what is out}}"))
        self.assertTrue(any("unfinished" in p for p in found))

    def test_a_made_up_rate_fails(self):
        text = GOOD.replace("| 10 | $175 | $1,750 |", "| 10 | $160 | $1,600 |").replace("$2,050", "$1,900")
        self.assertTrue(any("rate card" in p for p in self.problems(text)))

    def test_bad_arithmetic_fails(self):
        text = GOOD.replace("$1,750 |", "$1,850 |").replace("$2,050", "$2,150")
        self.assertTrue(any("not 1,850.00" in p for p in self.problems(text)))

    def test_a_total_that_does_not_add_up_fails(self):
        found = self.problems(GOOD.replace("$2,050", "$2,000"))
        self.assertTrue(any("add to 2,050.00" in p for p in found))

    def test_a_missing_section_fails(self):
        found = self.problems(GOOD.replace("## Out of scope", "## Extras"))
        self.assertIn("missing section: Out of scope", found)

    def test_an_empty_section_fails(self):
        found = self.problems(GOOD.replace("A pre-order page.\n", ""))
        self.assertIn("empty section: Scope", found)

    def test_a_whitespace_only_section_fails(self):
        found = self.problems(GOOD.replace("A pre-order page.\n", "   \n\t\n"))
        self.assertIn("empty section: Scope", found)

    def test_a_comment_only_section_fails(self):
        found = self.problems(GOOD.replace("A pre-order page.", "<!-- what we will build -->"))
        self.assertIn("empty section: Scope", found)

    def test_a_multi_line_comment_only_section_fails(self):
        found = self.problems(GOOD.replace("A pre-order page.", "<!--\nwhat we will\nbuild\n-->"))
        self.assertIn("empty section: Scope", found)

    def test_each_empty_section_gets_its_own_line(self):
        found = self.problems(GOOD.replace("Orders go missing.\n", "").replace("A pre-order page.\n", ""))
        self.assertEqual([p for p in found if p.startswith("empty section:")],
                         ["empty section: Problem", "empty section: Scope"])

    def test_an_empty_fees_section_is_reported_once_as_no_fee_rows(self):
        text = GOOD[:GOOD.index("## Fees")] + "## Fees\n\n" + GOOD[GOOD.index("## Assumptions"):]
        found = self.problems(text)
        self.assertIn("no fee rows under Fees", found)
        self.assertNotIn("empty section: Fees", found)

    def test_a_missing_section_is_not_also_reported_empty(self):
        found = self.problems(GOOD.replace("## Out of scope", "## Extras"))
        self.assertIn("missing section: Out of scope", found)
        self.assertFalse([p for p in found if p.startswith("empty section:")])

    def test_an_unknown_role_fails(self):
        text = GOOD.replace("| Designer |", "| Intern |")
        self.assertTrue(any("not a role" in p for p in self.problems(text)))

    def test_under_the_minimum_fee_fails(self):
        text = GOOD.replace("| Engineer | 10 | $175 | $1,750 |\n", "").replace("$2,050", "$300")
        self.assertTrue(any("minimum fee" in p for p in self.problems(text)))


if __name__ == "__main__":
    unittest.main()
