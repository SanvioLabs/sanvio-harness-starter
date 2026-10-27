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
    waiting          what's waiting on you, in two halves that each fail on their own: pull_requests,
                     the harness repo's open pull requests from gh, each with its title, when it
                     opened, hours waited, its loop issue if its branch is loop/issue-N, whether it's
                     a draft, its checks (pass, fail, pending, or null with none) and whether it
                     conflicts (null while GitHub doesn't know); and blocked, the issues in
                     status.json whose state is blocked, each with its title, note and last update

A section whose source is missing or can't be read is {"value": null, "why": ...}, and the why names
the kind of problem, never a path or an error's text. The script still exits 0. status.json keeps
only the loop's 20 most recent issues, so throughput covers those whatever --since says, and
cost_per_pr leaves out an issue that ran in the period but has dropped off the list. Titles and notes
appear only under waiting. Nothing it prints holds a pull request's address, a prompt, an eval's
reasons or a file path, and outside waiting it holds no title or note: counts, dollars, dates, issue
names, step, model, skill, agent, rule and case names. The dollars are the loop's estimate at API
prices, not what was billed.
"""
import argparse
import datetime
import json
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from loop import USAGE_TOKENS, usage_totals  # noqa: E402 (needs scripts/ on the path first)
from token_report import loop_runs, natural, usage_files  # noqa: E402 (same reason)
from usage_report import count, log_path, read, since_date  # noqa: E402 (same reason)

WEEK = 7  # days in the last-7-days window, today included
GH_TIMEOUT = 30  # seconds before a gh call counts as unavailable
PR_FIELDS = "number,title,createdAt,headRefName,isDraft,statusCheckRollup,mergeable"
FAILED = {"FAILURE", "ERROR", "CANCELLED", "TIMED_OUT", "ACTION_REQUIRED"}
LOOP_BRANCH = re.compile(r"^loop/issue-(\d+)$")


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


def checks(rollup):
    """fail if any check failed, else pending if any hasn't finished, else pass; None with no checks.

    gh mixes two shapes: a check run has status and conclusion ("" until it ends), a commit status has state.
    """
    found = [c for c in rollup if isinstance(c, dict)] if isinstance(rollup, list) else []
    if not found:
        return None
    ends = [c.get("conclusion") or c.get("state") for c in found]
    if any(end in FAILED for end in ends):
        return "fail"
    if any(c.get("status", "COMPLETED") != "COMPLETED" or end in ("PENDING", "EXPECTED") or not end
           for c, end in zip(found, ends)):
        return "pending"
    return "pass"


def hours_since(opened, now):
    try:
        then = datetime.datetime.fromisoformat(opened.replace("Z", "+00:00"))
        return round((now - then).total_seconds() / 3600, 1)
    except (AttributeError, TypeError, ValueError):
        return None


def pull_requests(root, now):
    try:
        done = subprocess.run(["gh", "pr", "list", "--state", "open", "--limit", "100", "--json", PR_FIELDS],
                              cwd=root, capture_output=True, text=True, timeout=GH_TIMEOUT)
        found = json.loads(done.stdout) if done.returncode == 0 else None
    except (OSError, ValueError, subprocess.TimeoutExpired):
        found = None
    if not isinstance(found, list):
        return missing("gh unavailable")
    out = []
    for pr in found:
        if not isinstance(pr, dict):
            continue
        opened = pr.get("createdAt") if isinstance(pr.get("createdAt"), str) else None
        branch = LOOP_BRANCH.match(pr["headRefName"]) if isinstance(pr.get("headRefName"), str) else None
        out.append({"number": number(pr.get("number")),
                    "title": pr["title"] if isinstance(pr.get("title"), str) else None,
                    "opened": opened,
                    "hours_waited": hours_since(opened, now),
                    "loop_issue": int(branch.group(1)) if branch else None,
                    "draft": pr["isDraft"] if isinstance(pr.get("isDraft"), bool) else None,
                    "checks": checks(pr.get("statusCheckRollup")),
                    "conflicts": {"CONFLICTING": True, "MERGEABLE": False}.get(pr.get("mergeable"))})
    return out


def blocked(root):
    rows, why = status_rows(root)
    if rows is None:
        return missing(why)

    def text(row, name):
        return row[name] if isinstance(row.get(name), str) else None

    return [{"issue": name, "number": rows[name]["number"], "title": text(rows[name], "title"),
             "note": text(rows[name], "note"), "updated": text(rows[name], "updated")}
            for name in sorted(rows, key=natural) if rows[name].get("state") == "blocked"]


def waiting(root, now):
    return {"pull_requests": pull_requests(root, now), "blocked": blocked(root)}


def build(root, since, today, now=None):
    now = now or datetime.datetime.now().astimezone()
    return {"generated": now.isoformat(timespec="seconds"), "since": since,
            "loop_spend": loop_spend(root, since, today),
            "loop_throughput": loop_throughput(root),
            "activity": activity(root, since),
            "evals": evals(root),
            "waiting": waiting(root, now)}


def main(argv=None, root=ROOT):
    now = datetime.datetime.now().astimezone()
    today = now.date()
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--json", action="store_true", required=True, help="print the numbers as JSON")
    parser.add_argument("--since", type=since_date, default=(today - datetime.timedelta(days=14)).isoformat(),
                        help="the first day to count, as YYYY-MM-DD (default: 14 days ago)")
    args = parser.parse_args(argv)
    print(json.dumps(build(root, args.since, today, now), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
