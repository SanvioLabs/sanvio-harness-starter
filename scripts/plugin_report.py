#!/usr/bin/env python3
"""List the Claude Code plugins and mods this harness runs with, as Markdown.

    python3 scripts/plugin_report.py
    python3 scripts/plugin_report.py --previous reports/usage/2026-10-10-pat.md

Runs `claude plugin list --json` and keeps the enabled plugins and mods that
apply here: installed for the user, or for this harness's folder. Each prints as
its id, version and scope, and nothing else: no install folder and no path. With
--previous, a harness report from an earlier sprint, it also says which plugins
changed version, arrived or went since that report's date, read from the
report's own table. Claude Code only. If claude isn't installed or its answer
isn't JSON, it prints one line saying so and still exits 0, so a report can be
written without it. The skills/harness-report/ skill runs this next to
token_report.py.
"""
import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HEADING = "## Plugins and mods"


def installed():
    """[(id, version, scope)] for the enabled plugins that apply to this harness, sorted by id."""
    try:
        result = subprocess.run(["claude", "plugin", "list", "--json"], capture_output=True, text=True, timeout=60)
    except FileNotFoundError:
        raise ValueError("claude isn't installed")
    except (OSError, subprocess.SubprocessError) as error:
        raise ValueError("claude didn't answer ({})".format(type(error).__name__))
    if result.returncode != 0:
        raise ValueError("claude exited with {}".format(result.returncode))
    try:
        found = json.loads(result.stdout)
    except ValueError:
        raise ValueError("claude's answer wasn't JSON")
    if not isinstance(found, list):
        raise ValueError("claude's answer wasn't a list")
    rows = {}
    for record in found:
        if not isinstance(record, dict) or record.get("enabled") is not True or not applies(record.get("projectPath")):
            continue
        name = record.get("id")
        if isinstance(name, str) and name:
            rows[name] = (name, text(record.get("version")), text(record.get("scope")))
    return [rows[name] for name in sorted(rows)]


def applies(project_path):
    """True for a plugin with no project folder, or whose project folder is this harness."""
    if project_path is None:
        return True
    if not isinstance(project_path, str):
        return False
    try:
        return Path(project_path).resolve() == ROOT
    except (OSError, RuntimeError, ValueError):
        return False


def text(value):
    return value if isinstance(value, str) and value else "unknown"


def table(rows):
    if not rows:
        return ["None.", ""]
    out = ["| Plugin | Version | Scope |", "|---|---|---|"]
    return out + ["| {} | {} | {} |".format(*row) for row in rows] + [""]


def earlier(path):
    """(date, {id: version}) from a harness report's plugin table, or None when it has none."""
    match = re.match(r"(\d{4}-\d{2}-\d{2})", Path(path).name)
    try:
        lines = Path(path).read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return None
    if not match or HEADING not in lines:
        return None
    versions = {}
    for line in lines[lines.index(HEADING) + 1:]:
        if line.startswith("#"):
            break
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if line.startswith("|") and len(cells) == 3 and cells[0] != "Plugin" and not set(cells[0]) <= {"-", ":"}:
            versions[cells[0]] = cells[1]
    return match.group(1), versions


def changes(before, rows):
    """The plugins that changed version, are new, or are gone, as short phrases in id order."""
    now = {name: version for name, version, _ in rows}
    out = []
    for name in sorted(set(before) | set(now)):
        if name not in before:
            out.append("{} (new)".format(name))
        elif name not in now:
            out.append("{} (gone)".format(name))
        elif before[name] != now[name]:
            out.append("{} {} → {}".format(name, before[name], now[name]))
    return out


def report(rows, previous):
    out = [HEADING, ""] + table(rows)
    found = earlier(previous) if previous else None
    if found is None:
        out.append("No earlier report to compare with.")
    else:
        date, before = found
        changed = changes(before, rows)
        out.append("Changed since {}: {}".format(date, ", ".join(changed)) if changed
                   else "Nothing changed since {}.".format(date))
    return "\n".join(out)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--previous", help="an earlier harness report, to say what changed since")
    args = parser.parse_args(argv)
    try:
        print(report(installed(), args.previous))
    except ValueError as error:
        print("Couldn't read plugin versions: {}.".format(error))
    return 0


if __name__ == "__main__":
    sys.exit(main())
