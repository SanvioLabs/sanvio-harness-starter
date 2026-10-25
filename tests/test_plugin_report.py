"""Run with: python3 -m unittest discover -s tests"""
import json
import os
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "plugin_report.py"

INSTALL = "/Users/someone/.claude/plugins/cache/secret-install-folder"
OTHER = "/Users/someone/elsewhere/other-folder"
FIXTURE = [
    {"id": "stelliad@sanvio-harness-starter", "version": "1.3", "scope": "project", "enabled": True,
     "projectPath": str(ROOT), "installPath": INSTALL + "/stelliad"},
    {"id": "loop-pane@inline", "version": "0.2", "scope": "session", "enabled": True,
     "installPath": INSTALL + "/loop-pane"},
    {"id": "off@market", "version": "9.9", "scope": "user", "enabled": False, "installPath": INSTALL + "/off"},
    {"id": "elsewhere@market", "version": "4.0", "scope": "project", "enabled": True,
     "projectPath": OTHER, "installPath": INSTALL + "/elsewhere"},
]
TABLE = ["| Plugin | Version | Scope |", "|---|---|---|",
         "| loop-pane@inline | 0.2 | session |", "| stelliad@sanvio-harness-starter | 1.3 | project |"]


def run(args=(), stdout=None, path=None):
    """Run the script with a fake `claude` that prints `stdout`, or with `path` as PATH when given."""
    with tempfile.TemporaryDirectory() as folder:
        bin_dir = Path(folder) / "bin"
        bin_dir.mkdir()
        if stdout is not None:
            fake = bin_dir / "claude"
            fake.write_text("#!/bin/sh\ncat <<'EOF'\n{}\nEOF\n".format(stdout))
            fake.chmod(fake.stat().st_mode | stat.S_IEXEC)
        env = dict(os.environ, PATH=path if path is not None else str(bin_dir))
        return subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True,
                              timeout=60, env=env)


def previous(folder, rows, name="2026-10-10-pat.md"):
    """A harness report holding a plugin table with `rows` as (id, version, scope)."""
    lines = ["# Report", "", "## Plugins and mods", "", "| Plugin | Version | Scope |", "|---|---|---|"]
    lines += ["| {} | {} | {} |".format(*row) for row in rows] + ["", "## Proposals", "", "| x | y | z |"]
    path = Path(folder) / name
    path.write_text("\n".join(lines) + "\n")
    return str(path)


class PluginReportTest(unittest.TestCase):
    def test_table_lists_enabled_plugins_for_this_harness(self):
        result = run(stdout=json.dumps(FIXTURE))
        self.assertEqual(result.returncode, 0, result.stderr)
        lines = result.stdout.splitlines()
        self.assertEqual(lines[0], "## Plugins and mods")
        self.assertEqual(lines[2:6], TABLE)
        self.assertNotIn("off@market", result.stdout)
        self.assertNotIn("elsewhere@market", result.stdout)

    def test_changed_new_and_gone_show_on_one_line(self):
        with tempfile.TemporaryDirectory() as folder:
            old = previous(folder, [("stelliad@sanvio-harness-starter", "1.2", "project"), ("gone@market", "1.0", "user")])
            result = run(["--previous", old], stdout=json.dumps(FIXTURE))
        self.assertIn("Changed since 2026-10-10: gone@market (gone), loop-pane@inline (new), "
                      "stelliad@sanvio-harness-starter 1.2 → 1.3", result.stdout.splitlines())

    def test_nothing_changed(self):
        with tempfile.TemporaryDirectory() as folder:
            old = previous(folder, [("loop-pane@inline", "0.2", "session"), ("stelliad@sanvio-harness-starter", "1.3", "project")])
            result = run(["--previous", old], stdout=json.dumps(FIXTURE))
        self.assertEqual(result.stdout.splitlines()[-1], "Nothing changed since 2026-10-10.")

    def test_no_earlier_report(self):
        self.assertEqual(run(stdout=json.dumps(FIXTURE)).stdout.splitlines()[-1], "No earlier report to compare with.")
        with tempfile.TemporaryDirectory() as folder:
            bare = Path(folder) / "2026-10-10-pat.md"
            bare.write_text("# Report\n\nNo plugin table here.\n")
            result = run(["--previous", str(bare)], stdout=json.dumps(FIXTURE))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.splitlines()[-1], "No earlier report to compare with.")

    def test_claude_missing(self):
        result = run(path="/nonexistent")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(result.stdout.splitlines()), 1)
        self.assertTrue(result.stdout.startswith("Couldn't read plugin versions: "))

    def test_claude_prints_something_that_is_not_json(self):
        result = run(stdout="not json at all")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(result.stdout.splitlines()), 1)
        self.assertTrue(result.stdout.startswith("Couldn't read plugin versions: "))

    def test_no_install_or_project_path_in_the_output(self):
        with tempfile.TemporaryDirectory() as folder:
            old = previous(folder, [("gone@market", "1.0", "user")])
            result = run(["--previous", old], stdout=json.dumps(FIXTURE))
        for value in (INSTALL, OTHER, str(ROOT), "installPath", "projectPath"):
            self.assertNotIn(value, result.stdout)


if __name__ == "__main__":
    unittest.main()
