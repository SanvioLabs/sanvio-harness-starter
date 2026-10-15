"""Run with: python3 -m unittest discover -s tests"""
import contextlib
import io
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "examples" / "proposal" / "gates"))
import phase_gate  # noqa: E402 (the import needs the example's gates/ on the path first)
import stamp  # noqa: E402 (same)

SAMPLE = (ROOT / "examples" / "proposal" / "proposals" / "juniper-bakery.md").read_text()


class Proposal(unittest.TestCase):
    """A copy of the sample proposal in a temporary folder, and a way to run each script's main."""

    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.path = Path(self.dir.name) / "juniper-bakery.md"
        self.path.write_text(SAMPLE)

    def tearDown(self):
        self.dir.cleanup()

    def run_main(self, module, *argv):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = module.main(list(argv))
        return code, out.getvalue()

    def states(self):
        return dict(stamp.state(self.path.read_text()))


class Stamps(Proposal):
    def test_an_unstamped_proposal_is_not_ready(self):
        self.assertEqual(self.states(), {"gate": "missing", "reviewed": "missing"})
        code, out = self.run_main(stamp, "status", str(self.path))
        self.assertEqual(code, 1)
        self.assertIn("Run again, in order: gate, reviewed", out)

    def test_both_stamps_in_order_make_it_ready(self):
        self.assertEqual(self.run_main(stamp, "gate", str(self.path))[0], 0)
        self.assertEqual(self.run_main(stamp, "reviewed", str(self.path))[0], 0)
        code, out = self.run_main(stamp, "status", str(self.path))
        self.assertEqual(code, 0)
        self.assertIn("Ready to send.", out)

    def test_reviewed_is_refused_before_the_gate(self):
        code, out = self.run_main(stamp, "reviewed", str(self.path))
        self.assertEqual(code, 1)
        self.assertIn("BLOCKED: gate is missing", out)
        self.assertNotIn("stamps:", self.path.read_text())

    def test_a_failing_gate_writes_no_stamp(self):
        self.path.write_text(SAMPLE.replace("$1,800", "TBD"))
        code, out = self.run_main(stamp, "gate", str(self.path))
        self.assertEqual(code, 1)
        self.assertIn("FAIL", out)
        self.assertEqual(self.states()["gate"], "missing")

    def test_an_edit_after_the_stamps_makes_every_stamp_stale(self):
        self.run_main(stamp, "gate", str(self.path))
        self.run_main(stamp, "reviewed", str(self.path))
        self.path.write_text(self.path.read_text().replace("a mobile app.", "a mobile app, or gift cards."))
        self.assertEqual(self.states(), {"gate": "stale", "reviewed": "stale"})
        code, out = self.run_main(stamp, "reviewed", str(self.path))
        self.assertEqual(code, 1)
        self.assertIn("BLOCKED: gate is stale", out)

    def test_the_gate_again_leaves_the_review_stale(self):
        self.run_main(stamp, "gate", str(self.path))
        self.run_main(stamp, "reviewed", str(self.path))
        self.path.write_text(self.path.read_text().replace("a mobile app.", "a mobile app, or gift cards."))
        self.run_main(stamp, "gate", str(self.path))
        self.assertEqual(self.states(), {"gate": "fresh", "reviewed": "stale"})

    def test_a_frontmatter_change_does_not_stale_the_stamps(self):
        self.run_main(stamp, "gate", str(self.path))
        self.path.write_text(self.path.read_text().replace("status: draft", "status: sent\nsigned: 2026-10-20"))
        self.assertEqual(self.states()["gate"], "fresh")

    def test_a_file_without_frontmatter_gets_one(self):
        body = stamp.split(SAMPLE)[1]
        self.path.write_text(body)
        self.assertEqual(self.run_main(stamp, "gate", str(self.path))[0], 0)
        text = self.path.read_text()
        self.assertTrue(text.startswith("---\nstamps: gate "))
        self.assertEqual(stamp.split(text)[1], body)

    def test_stamping_twice_keeps_one_stamps_line(self):
        self.run_main(stamp, "gate", str(self.path))
        self.run_main(stamp, "gate", str(self.path))
        self.assertEqual(self.path.read_text().count("stamps:"), 1)

    def test_an_unknown_command_prints_usage(self):
        self.assertEqual(self.run_main(stamp, "approved", str(self.path))[0], 2)


class PhaseGate(Proposal):
    def test_an_unstamped_unsigned_proposal_has_three_gaps_before_build(self):
        code, out = self.run_main(phase_gate, "build", str(self.path))
        self.assertEqual(code, 1)
        self.assertIn("Gate passed on this text", out)
        self.assertIn("closes it: skill draft-proposal", out)
        self.assertIn("Signed by the client", out)
        self.assertIn("no skill closes this", out)
        self.assertIn("Still in Shape: 3 gaps before Build.", out)

    def test_only_the_signature_left_is_yours(self):
        self.run_main(stamp, "gate", str(self.path))
        self.run_main(stamp, "reviewed", str(self.path))
        code, out = self.run_main(phase_gate, "build", str(self.path))
        self.assertEqual(code, 1)
        self.assertIn("Still in Shape: 1 gap, and only you can close it.", out)

    def test_nothing_missing_passes_and_moves_nothing(self):
        self.run_main(stamp, "gate", str(self.path))
        self.run_main(stamp, "reviewed", str(self.path))
        self.path.write_text(self.path.read_text().replace("status: draft", "status: draft\nsigned: 2026-10-20"))
        before = self.path.read_text()
        code, out = self.run_main(phase_gate, "build", str(self.path))
        self.assertEqual(code, 0)
        self.assertIn("Nothing missing for Build. Moving the phase on is yours.", out)
        self.assertEqual(self.path.read_text(), before)

    def test_an_empty_problem_blocks_shape(self):
        self.path.write_text(SAMPLE.replace(stamp.split(SAMPLE)[1].split("## Scope")[0],
                                            "\n# Proposal\n\n## Problem\n\n"))
        code, out = self.run_main(phase_gate, "shape", str(self.path))
        self.assertEqual(code, 1)
        self.assertIn("Problem written down", out)
        self.assertIn("Still in Discover", out)

    def test_a_missing_proposal_names_the_skill(self):
        code, out = self.run_main(phase_gate, "build", str(Path(self.dir.name) / "nobody.md"))
        self.assertEqual(code, 1)
        self.assertIn("skill draft-proposal", out)

    def test_a_phase_a_person_decides_is_refused(self):
        self.assertEqual(self.run_main(phase_gate, "validate", str(self.path))[0], 2)


if __name__ == "__main__":
    unittest.main()
