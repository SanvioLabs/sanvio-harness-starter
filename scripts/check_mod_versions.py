#!/usr/bin/env python3
"""Fail when a mod changes what it does without raising its version.

    python3 scripts/check_mod_versions.py origin/main

`/plugin update` keeps an installed copy whose version hasn't changed, so a mod
under examples/mods/ that changes without a higher `version` in its
.claude-plugin/plugin.json never reaches people who already have it. This
compares each mod at the merge base with <base> against HEAD. A change only to
Markdown, to `*.test.ts`/`*.test.tsx` files or to `hooks/sample.ts`, which only
the tests read, doesn't count. A mod that's new on HEAD, or removed on it, is
skipped.

Exits 0 when every changed mod raised its version, 1 when one didn't or its
version isn't three whole numbers, and 2 when git can't resolve <base>.
"""
import json
import re
import subprocess
import sys

MODS = "examples/mods"
MANIFEST = ".claude-plugin/plugin.json"
VERSION = re.compile(r"^\d+\.\d+\.\d+$")
NOT_BEHAVIOUR = (".md", ".test.ts", ".test.tsx", "/hooks/sample.ts")


def git(*args):
    done = subprocess.run(["git"] + list(args), capture_output=True, text=True)
    if done.returncode != 0:
        raise RuntimeError("git {} failed: {}".format(" ".join(args), done.stderr.strip()))
    return done.stdout


def mods_at(rev):
    """Names of the mods with a manifest at `rev`."""
    out = git("ls-tree", "-r", "--full-tree", "--name-only", rev, "--", MODS + "/")
    names = set()
    for path in out.splitlines():
        parts = path[len(MODS) + 1:].split("/", 1)
        if len(parts) == 2 and parts[1] == MANIFEST:
            names.add(parts[0])
    return names


def version_at(rev, name):
    """The mod's version string at `rev`, as written."""
    data = json.loads(git("show", "{}:{}/{}/{}".format(rev, MODS, name, MANIFEST)))
    return data.get("version")


def parse(version):
    """The version as a tuple of ints, or None when it isn't three whole numbers."""
    if not isinstance(version, str) or not VERSION.match(version):
        return None
    return tuple(int(part) for part in version.split("."))


def failures(base):
    """One line for each mod that changed without a higher, well-formed version."""
    mb = git("merge-base", base, "HEAD").strip()
    found = []
    for name in sorted(mods_at(mb) & mods_at("HEAD")):
        changed = git("diff", "--name-only", mb, "HEAD", "--", ":(top){}/{}/".format(MODS, name))
        if not [p for p in changed.splitlines() if not p.endswith(NOT_BEHAVIOUR)]:
            continue
        old, new = version_at(mb, name), version_at("HEAD", name)
        if parse(new) is None:
            found.append("{}: version {} is not three whole numbers".format(name, json.dumps(new)))
        # A base version that isn't three numbers can't be compared, so any good one replaces it.
        elif parse(old) is not None and parse(new) <= parse(old):
            found.append("{}: behaviour changed but version {} (base {}) is not higher".format(name, new, old))
    return found


def main(argv):
    if len(argv) != 1:
        print("usage: check_mod_versions.py <base>", file=sys.stderr)
        return 2
    base = argv[0]
    try:
        git("rev-parse", "--verify", "--quiet", base + "^{commit}")
    except RuntimeError:
        print("cannot resolve base: {}".format(base))
        return 2
    found = failures(base)
    for line in found:
        print(line)
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
