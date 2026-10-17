"""Run with: python3 -m unittest discover -s tests"""
import datetime
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INBOX = ROOT / "skills" / "inbox" / "inbox.py"


class Inbox(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name) / "inbox"

    def run_inbox(self, *args):
        return subprocess.run([sys.executable, str(INBOX), "--dir", str(self.dir)] + list(args),
                              capture_output=True, text=True)

    def add(self, *args):
        done = self.run_inbox("add", *args)
        self.assertEqual(done.returncode, 0, done.stderr)
        return done.stdout.strip()

    def item(self, item_id):
        return json.loads((self.dir / "{}.json".format(item_id)).read_text())

    def days_ago(self, days):
        when = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=days, hours=1)
        return when.strftime("%Y-%m-%dT%H:%M:%SZ")

    def test_add_writes_one_file(self):
        item_id = self.add("--text", "Try a weekly digest", "--source", "session")
        self.assertEqual([p.name for p in self.dir.iterdir()], ["{}.json".format(item_id)])
        item = self.item(item_id)
        self.assertEqual((item["text"], item["source"], item["status"]), ("Try a weekly digest", "session", "open"))

    def test_seen_is_false_before_add_and_true_after(self):
        self.assertEqual(self.run_inbox("seen", "<a1@example.com>").returncode, 1)
        self.add("--text", "x", "--source", "email", "--message-id", "<a1@example.com>")
        self.assertEqual(self.run_inbox("seen", "<a1@example.com>").returncode, 0)
        self.assertEqual(self.run_inbox("seen", "<b2@example.com>").returncode, 1)

    def test_the_same_message_is_imported_once(self):
        self.add("--text", "x", "--source", "email", "--message-id", "<a1@example.com>")
        again = self.run_inbox("add", "--text", "x", "--source", "email", "--message-id", "<a1@example.com>")
        self.assertNotEqual(again.returncode, 0)
        self.assertEqual(len(list(self.dir.glob("*.json"))), 1)

    def test_list_filters_by_status_and_shows_the_age(self):
        old = self.add("--text", "Old idea", "--source", "email", "--captured", self.days_ago(3))
        new = self.add("--text", "New idea", "--source", "session")
        self.run_inbox("set", new, "status=parked")
        open_lines = self.run_inbox("list", "--status", "open").stdout.splitlines()
        self.assertEqual(len(open_lines), 1)
        self.assertTrue(open_lines[0].startswith(old + " "))
        self.assertIn(" 3d ", open_lines[0])
        self.assertIn("Old idea", open_lines[0])
        self.assertEqual(len(self.run_inbox("list").stdout.splitlines()), 2)

    def test_set_changes_a_field(self):
        item_id = self.add("--text", "x", "--source", "session")
        done = self.run_inbox("set", item_id, "urgency=this week", "kind=feature")
        self.assertEqual(done.returncode, 0, done.stderr)
        item = self.item(item_id)
        self.assertEqual((item["urgency"], item["kind"]), ("this week", "feature"))

    def test_set_refuses_an_unknown_status_and_a_new_id(self):
        item_id = self.add("--text", "x", "--source", "session")
        self.assertNotEqual(self.run_inbox("set", item_id, "status=maybe").returncode, 0)
        self.assertNotEqual(self.run_inbox("set", item_id, "id=7").returncode, 0)
        self.assertNotEqual(self.run_inbox("set", "../x", "status=open").returncode, 0)
        self.assertEqual(self.item(item_id)["status"], "open")

    def test_close_records_the_fate_and_the_item_leaves_the_open_list(self):
        item_id = self.add("--text", "x", "--source", "session")
        done = self.run_inbox("close", item_id, "--fate", "issue", "--note", "opened an issue")
        self.assertEqual(done.returncode, 0, done.stderr)
        item = self.item(item_id)
        self.assertEqual((item["status"], item["fate"], item["note"]), ("closed", "issue", "opened an issue"))
        self.assertNotIn(item_id + " ", self.run_inbox("list", "--status", "open").stdout)


if __name__ == "__main__":
    unittest.main()
