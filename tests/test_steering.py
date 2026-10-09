"""Run with: python3 -m unittest discover -s tests"""
import re
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
AGENTS = (ROOT / "AGENTS.md").read_text()
IMPORT = re.compile(r"^@(\S+)$", re.M)
EM_DASH = chr(0x2014)  # written as a code point so this file passes its own check


class Steering(unittest.TestCase):
    def test_every_steering_file_is_named_in_agents_md(self):
        files = sorted((ROOT / "steering").glob("*.md"))
        self.assertTrue(files)
        for path in files:
            self.assertIn("steering/" + path.name, AGENTS, path.name)

    def test_every_import_in_agents_md_resolves(self):
        imports = IMPORT.findall(AGENTS)
        self.assertTrue(imports)
        for target in imports:
            self.assertTrue((ROOT / target).is_file(), target)

    def test_kiro_loads_the_same_files_claude_code_imports(self):
        imported = {Path(target).name for target in IMPORT.findall(AGENTS)}
        linked = {p.name for p in (ROOT / ".kiro" / "steering").glob("*.md") if p.name != "project.md"}
        self.assertEqual(imported, linked)
        for name in linked:
            link = ROOT / ".kiro" / "steering" / name
            self.assertEqual(link.resolve(), (ROOT / "steering" / name).resolve(), name)


# What the starter ships. Your own files (AGENTS.md, your skills, gates and briefs)
# aren't held to the house style: an agent's em dash shouldn't fail your suite.
SHIPPED = ["steering/*.md", "examples/**/*", "skills/orientation/*", "skills/learn/*",
           "skills/review-pr/*", "skills/review-tests/*", "skills/review-skill/*",
           "skills/whats-new/*", "CHANGELOG.md",
           "agents/reviewer.md", "gates/README.md", "company/README.md",
           "company/COMPANY.example.md", "projects/README.md", "README.md", "HOW-IT-WORKS.md",
           "EXERCISES.md", "STARTER-SKILLS.md", "scripts/*", "tests/*", ".claude/**/*",
           ".githooks/*", ".github/**/*"]


def ignored_by_git(paths):
    """The paths git ignores: not shipped, whatever lands there. Claude Code lays a
    mod's types into examples/mods/*/.claude-plugin/types/ when it loads one."""
    try:
        out = subprocess.run(["git", "check-ignore", "--stdin"], cwd=ROOT, capture_output=True, text=True,
                             input="\n".join(str(p.relative_to(ROOT)) for p in paths)).stdout
    except OSError:
        return set()
    return {ROOT / line for line in out.splitlines() if line}


class HouseStyle(unittest.TestCase):
    def test_no_em_dashes_in_what_the_starter_ships(self):
        found = []
        paths = sorted({p for pattern in SHIPPED for p in ROOT.glob(pattern)})
        self.assertTrue(paths)
        ignored = ignored_by_git(paths)
        for path in paths:
            if not path.is_file() or path.is_symlink() or path in ignored:
                continue
            try:
                text = path.read_text()
            except (UnicodeDecodeError, OSError):
                continue
            for number, line in enumerate(text.splitlines(), 1):
                if EM_DASH in line:
                    found.append("{}:{}".format(path.relative_to(ROOT), number))
        self.assertEqual(found, [], "em dashes: use a colon, commas, parentheses or two sentences")


if __name__ == "__main__":
    unittest.main()
