"""Run with: python3 -m unittest discover -s tests"""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "gates"))
from proposal_gate import check  # noqa: E402 (the import needs gates/ on the path first)

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

    def test_an_unknown_role_fails(self):
        text = GOOD.replace("| Designer |", "| Intern |")
        self.assertTrue(any("not a role" in p for p in self.problems(text)))

    def test_under_the_minimum_fee_fails(self):
        text = GOOD.replace("| Engineer | 10 | $175 | $1,750 |\n", "").replace("$2,050", "$300")
        self.assertTrue(any("minimum fee" in p for p in self.problems(text)))


if __name__ == "__main__":
    unittest.main()
