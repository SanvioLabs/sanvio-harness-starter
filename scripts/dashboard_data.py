#!/usr/bin/env python3
"""The numbers a harness dashboard shows, as JSON.

    python3 scripts/dashboard_data.py --json                    # the last 14 days
    python3 scripts/dashboard_data.py --json --since 2026-10-01

--json is the only output, and the script refuses to run without it. It prints one object:

    generated        when it ran, an ISO time with the local offset
    since            the first day counted
    loop_spend       tokens and estimated dollars from the loop's .loop/**/usage.json records: today,
                     the last 7 days and since --since, each keyed on when the loop picked the issue
                     up, then the --since totals by issue, step and model. A run that recorded no
                     model is under "null". cost_per_pr is, over the issues that ran since --since
                     and are in status.json, their cost over how many have a pull request,
                     or null when none has one
    loop_throughput  the issues in .loop/status.json and each project's: how many are in each
                     state, each one's round, and how many took more than one
    activity         your usage log, .harness/usage/<you>.jsonl, since --since: skills, agents and
                     slash commands by name, guard refusals by rule, and how many times it asked
    evals            the newest file in .harness/evals/ for each reviewer: when it was saved, how
                     many cases were stable, flaky and failing, and the failing cases' names
    conversations    Claude Code's tokens since --since from ~/.claude/projects, counted as
                     token_report.py counts them: "harness" for conversations at the root and in
                     projects/, "loop" for the loop's worktrees, each by model (input, output, cache
                     writes, cache reads and total) with how many sessions. What each transcript
                     held is kept in .harness/cache/conversations.json and read again only when the
                     file's size or time changes: per reply, its message and request ids, day, side,
                     model, session id and counts, under the transcript's path, and nothing else

A section whose source is missing or can't be read is {"value": null, "why": ...}, and the why names
the kind of problem, never a path or an error's text. The script still exits 0. status.json keeps
only the loop's 20 most recent issues, so throughput covers those whatever --since says, and
cost_per_pr leaves out an issue that ran in the period but has dropped off the list. Nothing it prints holds a title, a note, a pull request's address, a
prompt, an eval's reasons or a file path: counts, dollars, dates, issue names, step, model, skill,
agent, rule and case names. The dollars are the loop's estimate at API prices, not what was billed.
"""
import argparse
import contextlib
import datetime
import json
import os
import sys
import tempfile
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from loop import USAGE_TOKENS, usage_totals  # noqa: E402 (needs scripts/ on the path first)
from token_report import group, loop_dir, loop_runs, natural, read_file, tokens, usage_files  # noqa: E402 (same reason)
from usage_report import count, log_path, read, since_date  # noqa: E402 (same reason)

WEEK = 7  # days in the last-7-days window, today included
TRANSCRIPTS = Path.home() / ".claude" / "projects"
CACHE = Path(".harness") / "cache" / "conversations.json"
SIDES = {"Conversations": "harness", "projects/": "harness", "Loop": "loop"}  # token_report's groups, two sides
COUNTS = ("input", "output", "cache_writes", "cache_reads")  # token_report's FIELDS, in order


def missing(why):
    return {"value": None, "why": why}


def number(value):
    """value when it's an int or float that isn't a bool, else None."""
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def totals(entries):
    """{tokens, cost_usd} over usage.json entries, reading only the numbers in them, each None when no entry had one."""
    tokens, cost = usage_totals([{name: number(e.get(name)) for name in USAGE_TOKENS + ("cost_usd",)} for e in entries])
    return {"tokens": tokens, "cost_usd": None if cost is None else round(cost, 4)}


def readable(path):
    try:
        return isinstance(json.loads(path.read_text()), list)
    except (OSError, ValueError):
        return False


def status_rows(root):
    """({issue: row}, None) from .loop/status.json and each project's, or (None, why) when none can be read.

    Issues are named as loop_runs() names them: issue-N for the harness, <name>/issue-N for a project.
    """
    state = Path(root) / ".loop"
    paths = [("", state / "status.json")]
    paths += [(p.parent.name + "/", p) for p in sorted(state.glob("projects/*/status.json"))]
    paths = [(prefix, path) for prefix, path in paths if path.is_file()]
    if not paths:
        return None, "no status.json"
    rows, read_any = {}, False
    for prefix, path in paths:
        try:
            found = json.loads(path.read_text())
        except (OSError, ValueError):
            continue
        if not isinstance(found, dict) or not isinstance(found.get("issues"), list):
            continue
        read_any = True
        for row in found["issues"]:
            if isinstance(row, dict) and isinstance(number(row.get("number")), int):
                rows["{}issue-{}".format(prefix, row["number"])] = row
    return (rows, None) if read_any else (None, "unreadable")


def loop_spend(root, since, today):
    files = usage_files(root)
    if not files:
        return missing("no loop records")
    day, week = today.isoformat(), (today - datetime.timedelta(days=WEEK - 1)).isoformat()
    runs = loop_runs(root, min(since, week))
    if not runs and not any(readable(path) for _, path in files):
        return missing("unreadable")
    every = [(issue, e) for issue, entries in runs.items() for e in entries]
    counted = [(issue, e) for issue, e in every if e["run_started"][:10] >= since]

    def by(key):
        groups = {}
        for issue, e in counted:
            groups.setdefault(key(issue, e), []).append(e)
        return {name: totals(groups[name]) for name in sorted(groups, key=natural)}

    def named(value):
        return value if isinstance(value, str) and value else "null"

    out = {"today": totals([e for _, e in every if e["run_started"][:10] == day]),
           "last_7_days": totals([e for _, e in every if e["run_started"][:10] >= week]),
           "since": totals([e for _, e in counted]),
           "by_issue": by(lambda issue, e: issue),
           "by_step": by(lambda issue, e: named(e.get("step"))),
           "by_model": by(lambda issue, e: named(e.get("model")))}
    for name, value in out["by_model"].items():
        value["label"] = "model not recorded" if name == "null" else name
    # Both sides over the same issues: ones that ran in the period and status.json still lists.
    rows = status_rows(root)[0] or {}
    tracked = {issue for issue in out["by_issue"] if issue in rows}
    prs = sum(1 for issue in tracked if rows[issue].get("pr"))
    cost = totals([e for issue, e in counted if issue in tracked])["cost_usd"]
    out["cost_per_pr"] = round(cost / prs, 4) if prs and cost is not None else None
    return out


def loop_throughput(root):
    rows, why = status_rows(root)
    if rows is None:
        return missing(why)
    states = Counter(row["state"] if isinstance(row.get("state"), str) and row["state"] else "unknown"
                     for row in rows.values())
    rounds = {name: number(rows[name].get("round")) or 0 for name in sorted(rows, key=natural)}
    return {"issues": len(rows), "by_state": dict(states.most_common()), "rounds": rounds,
            "more_than_one_round": sum(1 for n in rounds.values() if n > 1)}


def activity(root, since):
    path = log_path(root)
    if not path.is_file():
        return missing("no usage log")
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, ValueError):
        return missing("unreadable")
    if text.strip() and not read(path, ""):
        return missing("unreadable")
    # The hook writes strings; a line with anything else in these fields can't be counted by name.
    lines = [l for l in read(path, since) if all(isinstance(l.get(k, ""), str) for k in ("event", "name", "rule"))]
    return {"skills": dict(count(lines, "skill", "name").most_common()),
            "agents": dict(count(lines, "agent", "name").most_common()),
            "commands": dict(count(lines, "command", "name").most_common()),
            "guard_refusals": dict(count(lines, "guard_deny", "rule").most_common()),
            "asks": sum(1 for l in lines if l.get("event") == "guard_ask")}


def evals(root):
    """The newest saved result for each reviewer. The same loop as eval_agents.latest(): names start with
    the time they were saved, so name order newest first, matched on the "reviewer" field, not the name.
    It's repeated here because latest() reads the harness's own folder and finds one reviewer's file."""
    paths = sorted((Path(root) / ".harness" / "evals").glob("*.json"), reverse=True)
    if not paths:
        return missing("no saved evals")
    out = {}
    for path in paths:
        try:
            found = json.loads(path.read_text())
        except (OSError, ValueError):
            continue
        if not isinstance(found, dict) or not isinstance(found.get("cases"), dict):
            continue
        reviewer = found.get("reviewer")
        if not isinstance(reviewer, str) or not reviewer or reviewer in out:
            continue
        statuses = {name: case.get("status") if isinstance(case, dict) else None
                    for name, case in found["cases"].items()}
        out[reviewer] = {"saved": found["saved"] if isinstance(found.get("saved"), str) else None,
                         "stable": sum(1 for s in statuses.values() if s == "stable"),
                         "flaky": sum(1 for s in statuses.values() if s == "flaky"),
                         "failing": sum(1 for s in statuses.values() if s == "failing"),
                         "failing_cases": sorted(name for name, s in statuses.items() if s == "failing")}
    return {name: out[name] for name in sorted(out)} if out else missing("unreadable")


def text_or_none(value):
    return value if isinstance(value, str) and value else None


def replies(entries, root, loop):
    """One record per reply in a transcript's entries, for the cache, leaving out replies outside the harness:
    [message id, request id, day, side, model, session id, input, output, cache writes, cache reads].

    A reply written as several lines keeps only its first line for each day. read() keeps the first line
    on or after its since date, so that's the same line whatever the date.
    """
    out, kept, sides = [], set(), {}
    for entry in entries:
        cwd = text_or_none(entry.get("cwd"))
        if cwd not in sides:
            found = group(entry, root, loop)
            sides[cwd] = SIDES[found[0]] if found else None
        if sides[cwd] is None:
            continue
        message = entry["message"]
        record = [text_or_none(message.get("id")), text_or_none(entry.get("requestId")),
                  str(entry.get("timestamp", ""))[:10], sides[cwd],
                  text_or_none(message.get("model")) or "unknown", text_or_none(entry.get("sessionId"))] + tokens(entry)
        if record[:2] != [None, None]:
            if tuple(record[:3]) in kept:
                continue
            kept.add(tuple(record[:3]))
        out.append(record)
    return out


def whole(n):
    return isinstance(n, int) and not isinstance(n, bool) and n >= 0


def cached(entry):
    """True when a cache entry has the shape conversations() writes."""
    if not isinstance(entry, dict) or not whole(entry.get("size")) or not whole(entry.get("mtime_ns")):
        return False
    records = entry.get("replies")
    return isinstance(records, list) and all(
        isinstance(r, list) and len(r) == 6 + len(COUNTS) and all(v is None or isinstance(v, str) for v in r[:2])
        and isinstance(r[2], str) and r[3] in SIDES.values() and isinstance(r[4], str)
        and (r[5] is None or isinstance(r[5], str)) and all(whole(n) for n in r[6:]) for r in records)


def save(path, data):
    """Write data as JSON through a temporary file beside path, so a reader never sees half of it.
    A cache that can't be written is left as it was."""
    path, temp = Path(path), None
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile("w", dir=path.parent, prefix=path.name + ".", suffix=".tmp",
                                         delete=False, encoding="utf-8") as handle:
            temp = handle.name
            json.dump(data, handle, separators=(",", ":"))
        os.replace(temp, path)
    except OSError:
        if temp:
            with contextlib.suppress(OSError):
                os.unlink(temp)


def conversations(root, since, projects_dir, cache_path):
    """Tokens since `since` in the transcripts under projects_dir, by side and model, the way token_report.py
    counts them: each reply once, the first copy in path order, judged by the folder it ran in.

    A transcript whose size and time match its cache entry isn't read again. The cache drops transcripts
    that are gone, and one that can't be read or isn't the right shape is rebuilt.
    """
    projects_dir = Path(projects_dir)
    if not projects_dir.is_dir():
        return missing("no transcripts")
    try:
        loop = loop_dir(root)
    except (OSError, ValueError):
        return missing("unreadable")
    try:
        cache = json.loads(Path(cache_path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        cache = {}
    if not isinstance(cache, dict):
        cache = {}
    fresh = {}
    for path in sorted(projects_dir.rglob("*.jsonl")):
        try:
            stat = path.stat()  # before the read, so a file that grows during it is read again next time
            entry = cache.get(str(path))
            if not (cached(entry) and entry["size"] == stat.st_size and entry["mtime_ns"] == stat.st_mtime_ns):
                entry = {"size": stat.st_size, "mtime_ns": stat.st_mtime_ns,
                         "replies": replies(read_file(path, False), root, loop)}
        except OSError:
            continue
        fresh[str(path)] = entry
    save(cache_path, fresh)

    by_model = {"harness": {}, "loop": {}}
    sessions = {"harness": set(), "loop": set()}
    seen = set()
    for entry in fresh.values():
        for message_id, request_id, day, side, model, session, *counts in entry["replies"]:
            if day < since:
                continue
            if (message_id, request_id) != (None, None):
                if (message_id, request_id) in seen:
                    continue
                seen.add((message_id, request_id))
            by_model[side][model] = [a + b for a, b in zip(by_model[side].get(model, [0] * len(COUNTS)), counts)]
            if session:
                sessions[side].add(session)
    return {side: {"by_model": {model: dict(zip(COUNTS, values), total=sum(values))
                                for model, values in sorted(by_model[side].items(), key=lambda kv: natural(kv[0]))},
                   "sessions": len(sessions[side])}
            for side in ("harness", "loop")}


def build(root, since, today, now=None, projects_dir=TRANSCRIPTS):
    now = now or datetime.datetime.now().astimezone()
    return {"generated": now.isoformat(timespec="seconds"), "since": since,
            "loop_spend": loop_spend(root, since, today),
            "loop_throughput": loop_throughput(root),
            "activity": activity(root, since),
            "evals": evals(root),
            "conversations": conversations(root, since, projects_dir, Path(root) / CACHE)}


def main(argv=None, root=ROOT, projects_dir=TRANSCRIPTS):
    now = datetime.datetime.now().astimezone()
    today = now.date()
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--json", action="store_true", required=True, help="print the numbers as JSON")
    parser.add_argument("--since", type=since_date, default=(today - datetime.timedelta(days=14)).isoformat(),
                        help="the first day to count, as YYYY-MM-DD (default: 14 days ago)")
    args = parser.parse_args(argv)
    print(json.dumps(build(root, args.since, today, now, projects_dir), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
