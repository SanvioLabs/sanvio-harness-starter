"""Run with: python3 -m unittest discover -s tests"""
import json
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EXAMPLE = ROOT / "examples" / "typescript"


def version(text):
    """(major, minor, patch) from 'v22.18.0' or '>=22.18.0', or None."""
    match = re.search(r"(\d+)\.(\d+)\.(\d+)", text)
    return tuple(int(n) for n in match.groups()) if match else None


def why_node_cannot_run_it():
    """Why this machine can't run the example's tests, or None when it can."""
    floor = json.loads((EXAMPLE / "package.json").read_text())["engines"]["node"]
    if not shutil.which("node") or not shutil.which("npm"):
        return "needs Node {} and npm on the PATH".format(floor)
    found = subprocess.run(["node", "--version"], capture_output=True, text=True).stdout.strip()
    if version(found) is None or version(found) < version(floor):
        return "needs Node {}, found {}".format(floor, found or "no version")
    return None


class Dependencies(unittest.TestCase):
    """npm ci needs a lockfile, and npm run typecheck needs typescript pinned in it."""

    def test_typescript_is_pinned_and_locked(self):
        package = json.loads((EXAMPLE / "package.json").read_text())
        pinned = package.get("devDependencies", {}).get("typescript")
        self.assertIsNotNone(pinned, "package.json has no devDependencies.typescript, so there's no tsc")
        self.assertIsNotNone(version(pinned), "typescript isn't at a version: {}".format(pinned))
        self.assertRegex(pinned, r"^\d+\.\d+\.\d+$", "typescript isn't pinned to an exact version")
        lockfile = EXAMPLE / "package-lock.json"
        self.assertTrue(lockfile.is_file(), "no package-lock.json, so npm ci fails")
        locked = json.loads(lockfile.read_text())["packages"].get("node_modules/typescript", {})
        self.assertEqual(locked.get("version"), pinned, "package-lock.json doesn't lock the typescript package.json pins")


class TypeScriptExample(unittest.TestCase):
    """npm test in a copy of examples/typescript passes, and fails once the code is wrong."""

    def setUp(self):
        reason = why_node_cannot_run_it()
        if reason:
            self.skipTest(reason)
        self.copy = Path(tempfile.mkdtemp()) / "typescript"
        self.addCleanup(shutil.rmtree, self.copy.parent)
        shutil.copytree(EXAMPLE, self.copy, ignore=shutil.ignore_patterns("node_modules"))

    def npm_test(self):
        return subprocess.run(["npm", "test"], cwd=self.copy, capture_output=True, text=True, timeout=120)

    def test_the_tests_pass_as_shipped(self):
        result = self.npm_test()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_the_tests_fail_when_the_function_is_wrong(self):
        (self.copy / "src" / "slug.ts").write_text(
            "export function slug(title: string): string {\n  return title;\n}\n")
        result = self.npm_test()
        self.assertNotEqual(result.returncode, 0, "npm test passed with slug returning its input unchanged")


if __name__ == "__main__":
    unittest.main()
