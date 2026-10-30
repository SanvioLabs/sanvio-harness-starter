"""Run with: python3 -m unittest discover -s tests"""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "check_mod_versions.py"

# Keep the person's own git config, and any repo a calling hook points at, out of these repos.
ISOLATED = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
ISOLATED.update(GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1")


class ModVersions(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.git("init", "-q", "-b", "main")
        self.mod("lens", "0.4.1")
        self.commit("base")
        self.git("checkout", "-q", "-b", "change")

    def git(self, *args):
        done = subprocess.run(["git", "-c", "user.name=Test", "-c", "user.email=test@example.com",
                               "-C", str(self.root)] + list(args),
                              env=ISOLATED, capture_output=True, text=True)
        self.assertEqual(done.returncode, 0, done.stderr)
        return done.stdout

    def write(self, name, text):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)

    def mod(self, name, version):
        """Write a mod with this version, one code file, a README and a test."""
        base = "examples/mods/{}/".format(name)
        self.write(base + ".claude-plugin/plugin.json", json.dumps({"name": name, "version": version}))
        self.write(base + "hooks/logic.ts", "export const n = 1;\n")
        self.write(base + "hooks/logic.test.ts", "// test\n")
        self.write(base + "hooks/view.test.tsx", "// test\n")
        self.write(base + "README.md", "# {}\n".format(name))

    def bump(self, name, version):
        self.write("examples/mods/{}/.claude-plugin/plugin.json".format(name),
                   json.dumps({"name": name, "version": version}))

    def commit(self, message="change"):
        self.git("add", "-A")
        self.git("commit", "-q", "-m", message)

    def check(self, base="main"):
        done = subprocess.run([sys.executable, str(SCRIPT), base], cwd=str(self.root),
                              env=ISOLATED, capture_output=True, text=True)
        return done.returncode, done.stdout + done.stderr

    def test_a_code_change_at_the_same_version_fails(self):
        self.write("examples/mods/lens/hooks/logic.ts", "export const n = 2;\n")
        self.commit()
        code, out = self.check()
        self.assertEqual(code, 1, out)
        self.assertIn("lens: behaviour changed but version 0.4.1 (base 0.4.1) is not higher", out)

    def test_a_code_change_with_a_higher_version_passes(self):
        self.write("examples/mods/lens/hooks/logic.ts", "export const n = 2;\n")
        self.bump("lens", "0.4.2")
        self.commit()
        self.assertEqual(self.check(), (0, ""))

    def test_a_readme_change_passes_at_the_same_version(self):
        self.write("examples/mods/lens/README.md", "# lens\n\nMore.\n")
        self.commit()
        self.assertEqual(self.check(), (0, ""))

    def test_a_test_change_passes_at_the_same_version(self):
        self.write("examples/mods/lens/hooks/logic.test.ts", "// more\n")
        self.write("examples/mods/lens/hooks/view.test.tsx", "// more\n")
        self.commit()
        self.assertEqual(self.check(), (0, ""))

    def test_a_rewritten_sample_passes_at_the_same_version(self):
        self.write("examples/mods/lens/hooks/sample.ts", "export const SAMPLE = 2;\n")
        self.commit()
        self.assertEqual(self.check(), (0, ""))

    def test_a_file_only_named_like_the_sample_still_counts(self):
        self.write("examples/mods/lens/hooks/notsample.ts", "export const n = 2;\n")
        self.commit()
        code, out = self.check()
        self.assertEqual(code, 1, out)
        self.assertIn("lens: behaviour changed", out)

    def test_versions_compare_as_numbers(self):
        self.git("checkout", "-q", "main")
        self.bump("lens", "0.9.0")
        self.commit("base at 0.9.0")
        self.git("checkout", "-q", "-b", "minor")
        self.write("examples/mods/lens/hooks/logic.ts", "export const n = 2;\n")
        self.bump("lens", "0.10.0")
        self.commit()
        self.assertEqual(self.check(), (0, ""))

    def test_a_lower_version_fails(self):
        self.write("examples/mods/lens/hooks/logic.ts", "export const n = 2;\n")
        self.bump("lens", "0.3.9")
        self.commit()
        code, out = self.check()
        self.assertEqual(code, 1, out)
        self.assertIn("lens: behaviour changed but version 0.3.9 (base 0.4.1) is not higher", out)

    def test_a_version_that_is_not_three_numbers_fails(self):
        self.write("examples/mods/lens/hooks/logic.ts", "export const n = 2;\n")
        self.bump("lens", "1.0")
        self.commit()
        code, out = self.check()
        self.assertEqual(code, 1, out)
        self.assertIn('lens: version "1.0" is not three whole numbers', out)

    def test_a_new_mod_passes_at_any_version(self):
        self.mod("pane", "0.0.0")
        self.commit()
        self.assertEqual(self.check(), (0, ""))

    def test_a_removed_mod_passes(self):
        self.git("rm", "-q", "-r", "examples/mods/lens")
        self.commit()
        self.assertEqual(self.check(), (0, ""))

    def test_a_base_git_cannot_resolve_exits_2(self):
        code, out = self.check("origin/nowhere")
        self.assertEqual(code, 2, out)
        self.assertIn("cannot resolve base: origin/nowhere", out)

    def test_several_commits_are_judged_as_one_change(self):
        self.write("examples/mods/lens/hooks/logic.ts", "export const n = 2;\n")
        self.bump("lens", "0.4.2")
        self.commit("raise")
        self.write("examples/mods/lens/hooks/logic.ts", "export const n = 3;\n")
        self.commit("more code at the same version")
        self.assertEqual(self.check(), (0, ""))
        self.git("checkout", "-q", "-b", "again", "main")
        self.write("examples/mods/lens/README.md", "# lens\n\nMore.\n")
        self.commit("docs")
        self.write("examples/mods/lens/hooks/logic.ts", "export const n = 4;\n")
        self.commit("code, no raise")
        code, out = self.check()
        self.assertEqual(code, 1, out)
        self.assertIn("lens: behaviour changed", out)


if __name__ == "__main__":
    unittest.main()
