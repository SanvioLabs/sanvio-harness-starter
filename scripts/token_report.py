#!/usr/bin/env python3
"""Summarize the Claude Code tokens spent under this harness, as Markdown.

    python3 scripts/token_report.py                    # the last 14 days
    python3 scripts/token_report.py --since 2026-10-01
    python3 scripts/token_report.py --projects /some/other/.claude/projects

Reads Claude Code's own transcripts, ~/.claude/projects/**/*.jsonl, subagents
included, and counts the tokens on each reply whose working folder is this
harness: conversations at its root, each repo under projects/, and each issue
the loop built in its worktrees. Nothing it prints holds a prompt, a reply, a
file path or a line of code: counts, model names, session ids, issue names,
and for the loop, estimated dollars. Claude Code only: Codex, Kiro and other
tools keep their own logs. The dollars are the estimate at API prices each loop
run recorded in .loop/**/usage.json, not what was billed; a conversation's
transcript carries no cost, so it stays in tokens. The skills/harness-report/
skill runs this next to usage_report.py.
"""
import argparse
import datetime
import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from loop import load_config, usage_totals  # noqa: E402 (needs scripts/ on the path first)
from usage_report import since_date  # noqa: E402 (same reason)

# The four counts on a reply's message.usage, with the names the tables give them.
FIELDS = (("input_tokens", "Input"), ("output_tokens", "Output"),
          ("cache_creation_input_tokens", "Cache writes"), ("cache_read_input_tokens", "Cache reads"))
GROUPS = (("Conversations", "Where"), ("projects/", "Repo"), ("Loop", "Issue"))
TOP = 5


def loop_dir(root):
    """Where the loop puts its worktrees: worktree_dir from loop.json, or ~/.harness-loop/<root's name>."""
    configured = load_config(root).get("worktree_dir")
    if configured:
        return Path(configured).expanduser()
    return Path.home() / ".harness-loop" / Path(root).name


def loop_costs(root, since):
    """{issue: (estimated dollars or None, runs without a cost)} from the loop's usage.json records.

    A harness issue is issue-N, a project's is <name>/issue-N. A run counts when its run_started, the
    time the loop picked the issue up, is on or after `since`; a run with no run_started is in no
    period. A run without a numeric cost_usd (it ended early, its agent isn't Claude, or it predates the
    loop recording cost) is counted as one without. A record that can't be read is skipped.
    """
    state = Path(root) / ".loop"
    paths = [(p.parent.name, p) for p in state.glob("issue-*/usage.json")]
    paths += [("{}/{}".format(p.parent.parent.name, p.parent.name), p) for p in state.glob("projects/*/issue-*/usage.json")]
    out = {}
    for name, path in paths:
        try:
            found = json.loads(path.read_text())
        except (OSError, ValueError):
            continue
        if not isinstance(found, list):
            continue
        runs = [e for e in found if isinstance(e, dict) and isinstance(e.get("run_started"), str)
                and e["run_started"][:10] >= since]
        priced = [e for e in runs if isinstance(e.get("cost_usd"), (int, float)) and not isinstance(e.get("cost_usd"), bool)]
        if runs:
            out[name] = (usage_totals(priced)[1], len(runs) - len(priced))
    return out


def cost_table(costs):
    if not costs:
        return ["None recorded.", ""]
    out = ["| Issue | Estimated cost | Runs without a cost |", "|---|---|---|"]
    for name in sorted(costs, key=natural):
        cost, without = costs[name]
        out.append("| {} | {} | {} |".format(name, "none recorded" if cost is None else "${:,.2f}".format(cost), without))
    total = sum(cost for cost, _ in costs.values() if cost is not None)
    without = sum(n for _, n in costs.values())
    note = ["Total: ${:,.2f}, estimated at API prices, not what was billed.".format(total)]
    if without:
        note.append("{} run{} recorded no cost, so the issues they belong to cost more than shown.".format(
            without, "" if without == 1 else "s"))
    note.append("Runs are counted by when the loop picked the issue up.")
    return out + ["", " ".join(note), ""]


def read(projects_dir, since):
    """Every reply with a usage on or after `since` (YYYY-MM-DD), each counted once.

    Claude Code writes one reply as several lines, one per content block, each with the same
    message id and request id, so a pair seen before is skipped. A reply from a subagent, marked
    isSidechain or written to a file in a session's subfolder, gets `_subagent` set. Lines that
    aren't JSON, files that can't be read and a folder that isn't there are skipped.
    """
    projects_dir = Path(projects_dir)
    if not projects_dir.is_dir():
        return []
    entries, seen = [], set()
    for path in sorted(projects_dir.rglob("*.jsonl")):
        nested = len(path.relative_to(projects_dir).parts) > 2
        try:
            with open(path, encoding="utf-8", errors="replace") as handle:
                lines = handle.readlines()
        except OSError:
            continue
        for raw in lines:
            try:
                entry = json.loads(raw)
            except ValueError:
                continue
            if not isinstance(entry, dict):
                continue
            message = entry.get("message")
            if not isinstance(message, dict) or not isinstance(message.get("usage"), dict):
                continue
            if str(entry.get("timestamp", ""))[:10] < since:
                continue
            key = (message.get("id"), entry.get("requestId"))
            if key != (None, None):
                if key in seen:
                    continue
                seen.add(key)
            entry["_subagent"] = bool(entry.get("isSidechain")) or nested
            entries.append(entry)
    return entries


def group(entry, root, loop_dir):
    """(group, row) for the folder this reply ran in, or None when it ran outside the harness.

    The loop's folder is checked first, because a worktree_dir set in loop.json can sit inside
    the root.
    """
    cwd = entry.get("cwd")
    if not isinstance(cwd, str) or not cwd:
        return None
    try:
        here = Path(cwd).resolve()
        root, loop_dir = Path(root).resolve(), Path(loop_dir).resolve()
    except (OSError, RuntimeError, ValueError):
        return None
    if here != loop_dir and here.is_relative_to(loop_dir):
        parts = here.relative_to(loop_dir).parts
        # A project's worktrees sit one folder down, in <project>/issue-N.
        if not parts[0].startswith("issue-") and len(parts) > 1:
            return ("Loop", "{}/{}".format(parts[0], parts[1]))
        return ("Loop", parts[0])
    projects = root / "projects"
    if here != projects and here.is_relative_to(projects):
        return ("projects/", here.relative_to(projects).parts[0])
    if here.is_relative_to(root):
        return ("Conversations", "")
    return None


def tokens(entry):
    """The four usage counts on a reply, with anything that isn't a whole number taken as 0."""
    usage = entry["message"]["usage"]
    out = []
    for field, _ in FIELDS:
        n = usage.get(field)
        out.append(n if isinstance(n, int) and not isinstance(n, bool) and n > 0 else 0)
    return out


def natural(name):
    """A sort key that puts issue-9 before issue-10."""
    return [(0, int(part), "") if part.isdigit() else (1, 0, part) for part in re.split(r"(\d+)", name)]


def counts_table(rows, header):
    if not rows:
        return ["None.", ""]
    out = ["| {} | {} | Total |".format(header, " | ".join(label for _, label in FIELDS)),
           "|---|" + "---|" * (len(FIELDS) + 1)]
    for name in sorted(rows, key=natural):
        values = rows[name]
        out.append("| {} | {} | {:,} |".format(name, " | ".join("{:,}".format(v) for v in values), sum(values)))
    return out + [""]


def top_table(counter, header, label=None, limit=TOP):
    if not counter:
        return ["None.", ""]
    out = ["| {} | Tokens |".format(header), "|---|---|"]
    out += ["| {} | {:,} |".format(label(name) if label else name, n) for name, n in counter.most_common(limit)]
    return out + [""]


def report(entries, since, until, root, loop_dir, costs=None):
    groups = {name: {} for name, _ in GROUPS}
    models, sessions, issues = Counter(), Counter(), Counter()
    first_seen = {}
    total = subagents = 0
    where = {}
    for entry in entries:
        cwd = entry.get("cwd")
        key = cwd if isinstance(cwd, str) else None
        if key not in where:
            where[key] = group(entry, root, loop_dir)
        found = where[key]
        if found is None:
            continue
        values = tokens(entry)
        n = sum(values)
        name, row = found
        rows = groups[name]
        row = row or "This harness"
        rows[row] = [a + b for a, b in zip(rows.get(row, [0] * len(FIELDS)), values)]
        total += n
        model = entry["message"].get("model")
        models[model if isinstance(model, str) and model else "unknown"] += n
        if entry.get("_subagent"):
            subagents += n
        session = entry.get("sessionId")
        if isinstance(session, str) and session:
            sessions[session] += n
            day = str(entry.get("timestamp", ""))[:10]
            first_seen[session] = min(first_seen.get(session, day), day)
        if name == "Loop":
            issues[row] += n

    if not any(groups.values()) and not costs:
        return "No Claude Code usage under this harness since {}.".format(since)

    out = ["# Claude Code tokens, {} to {}".format(since, until), "",
           "Total: {:,} tokens across {} sessions.".format(total, len(sessions)), ""]
    for name, header in GROUPS:
        out += ["## {}".format(name), ""] + counts_table(groups[name], header)
    out += ["## By model", ""] + top_table(models, "Model", limit=None)
    share = 100 * subagents / total if total else 0
    out += ["## Subagents", "", "{:,} of {:,} tokens ({:.0f}%) were spent by subagents.".format(
        subagents, total, share), ""]
    out += ["## Top sessions", ""] + top_table(
        sessions, "Session", lambda s: "`{}`, first {}".format(s, first_seen[s]))
    out += ["## Top loop issues", ""] + top_table(issues, "Issue")
    out += ["## Loop cost", ""] + cost_table(costs)
    out.append("Claude Code sessions only. Dollars only for the loop's runs, as the loop recorded them at API prices.")
    return "\n".join(out)


def main(argv=None):
    today = datetime.date.today()
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--since", type=since_date, default=(today - datetime.timedelta(days=14)).isoformat())
    parser.add_argument("--projects", default=str(Path.home() / ".claude" / "projects"),
                        help="Claude Code's transcripts folder, if not ~/.claude/projects")
    args = parser.parse_args(argv)
    entries = read(Path(args.projects).expanduser(), args.since)
    print(report(entries, args.since, today.isoformat(), ROOT, loop_dir(ROOT), loop_costs(ROOT, args.since)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
