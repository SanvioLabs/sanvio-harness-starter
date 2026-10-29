#!/usr/bin/env python3
"""What got done in a repo over a period, from GitHub and its CHANGELOG, for a work report.

    python3 scripts/work_report.py                       # the harness, the last 14 days, as Markdown
    python3 scripts/work_report.py --since 2026-10-01
    python3 scripts/work_report.py --project app         # a repo under projects/ instead
    python3 scripts/work_report.py --json

It reads, through gh, in the harness root or the repo under projects/:

    pull_requests  each pull request merged on or after --since: its number, title, address, author's
                   login, when it opened and merged, the issues it closes, its milestone, the logins of
                   whoever else reviewed it, and the spec its closed issues name. loop_built is true when
                   its branch is loop/issue-N, the branch the loop opens. A review counts as a second
                   reviewer's when its login isn't the author's and doesn't end in [bot]
    totals         counts over those, and the median minutes from opened to merged
    by_person      the same counts for each author's login
    by_day         every UTC day from --since to today, oldest first, with merged and loop_built
    milestones     GitHub milestones: met, the ones closed on or after --since, and open, each with its
                   issues closed and still open and its due date
    releases       releases published on or after --since, drafts left out
    specs          for each spec named on a closed issue's "Spec:" line, the pull requests that closed one
    changelog      CHANGELOG.md's entries dated on or after --since, newest first: what shipped, in words

Milestones are only what GitHub records: a release or a closed milestone. It never picks one, and a
CHANGELOG entry is not a milestone.

Unlike the other reports here, this one names people. It prints each pull request's author and
reviewers by GitHub login, with its number, title and address, because a lead reads it to see who did
what. It never prints an issue's or a pull request's body, beyond the one "Spec:" line, nor a commit
message, a diff, an email or a file path.

A section whose source is missing or can't be read is {"value": null, "why": ...}, and the script still
exits 0. gh's search returns at most LIMIT pull requests and LIMIT issues; truncated says when either
reached it, and then the counts are low.
"""
import argparse
import datetime
import json
import re
import statistics
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from dashboard_data import LOOP_BRANCH, gh, missing  # noqa: E402 (needs scripts/ on the path first)
from usage_report import since_date  # noqa: E402 (same reason)

SCHEMA = 1  # the document's shape; goes up when a section's shape changes
LIMIT = 1000  # gh's search stops here
PR_FIELDS = "number,title,url,author,createdAt,mergedAt,headRefName,closingIssuesReferences,milestone,reviews"
SPEC_LINE = re.compile(r"^\s*Spec:\s*(\S.*?)\s*$", re.M)
CHANGELOG_HEADING = re.compile(r"^## (\d{4}-\d{2}-\d{2}): (\S.*)$", re.M)
SHIPPED_SHOWN = 15  # changelog entries the Markdown lists before "and N more"


def flat(pages):
    """The items of gh's pages, one array per page, or None when any page isn't a list."""
    if pages is None or not all(isinstance(page, list) for page in pages):
        return None
    return [item for page in pages for item in page if isinstance(item, dict)]


def login(person):
    return person.get("login") if isinstance(person, dict) and isinstance(person.get("login"), str) else "ghost"


def when(text):
    try:
        return datetime.datetime.fromisoformat(text.replace("Z", "+00:00"))
    except (AttributeError, ValueError):
        return None


def spec_of(issue):
    """The first "Spec:" line's value in an issue's body, or None. Nothing else of the body is kept."""
    body = issue.get("body") if isinstance(issue.get("body"), str) else ""
    found = SPEC_LINE.search(body)
    return found.group(1)[:120] if found else None


def pull_request_rows(prs, specs):
    """One row per merged pull request, oldest merge first. specs is {issue number: spec}."""
    rows = []
    for pr in prs:
        opened, merged = when(pr.get("createdAt")), when(pr.get("mergedAt"))
        if not isinstance(pr.get("number"), int) or merged is None:
            continue
        author = login(pr.get("author"))
        closes = sorted(i["number"] for i in pr.get("closingIssuesReferences") or []
                        if isinstance(i, dict) and isinstance(i.get("number"), int))
        reviewers = sorted({login(r.get("author")) for r in pr.get("reviews") or [] if isinstance(r, dict)}
                           - {author, "ghost"})
        milestone = pr.get("milestone") if isinstance(pr.get("milestone"), dict) else {}
        branch = pr.get("headRefName") if isinstance(pr.get("headRefName"), str) else ""
        rows.append({
            "number": pr["number"],
            "title": pr.get("title") if isinstance(pr.get("title"), str) else "",
            "url": pr.get("url") if isinstance(pr.get("url"), str) else None,
            "author": author,
            "merged": merged.date().isoformat(),
            "minutes_to_merge": round((merged - opened).total_seconds() / 60, 1) if opened else None,
            "closes": closes,
            "milestone": milestone.get("title") if isinstance(milestone.get("title"), str) else None,
            "loop_built": bool(LOOP_BRANCH.match(branch)),
            "second_reviewers": [r for r in reviewers if not r.endswith("[bot]")],
            "specs": sorted({specs[n] for n in closes if specs.get(n)}),
        })
    return sorted(rows, key=lambda r: (r["merged"], r["number"]))


def counts(rows):
    minutes = [r["minutes_to_merge"] for r in rows if r["minutes_to_merge"] is not None]
    return {"merged": len(rows),
            "loop_built": sum(1 for r in rows if r["loop_built"]),
            "hand_built": sum(1 for r in rows if not r["loop_built"]),
            "issues_closed": len({n for r in rows for n in r["closes"]}),
            "second_reviewer": sum(1 for r in rows if r["second_reviewers"]),
            "on_a_milestone_or_spec": sum(1 for r in rows if r["milestone"] or r["specs"]),
            "median_minutes_to_merge": round(statistics.median(minutes), 1) if minutes else None}


def by_person(rows):
    people = defaultdict(list)
    for row in rows:
        people[row["author"]].append(row)
    return [dict(counts(mine), login=who) for who, mine in sorted(people.items(), key=lambda kv: (-len(kv[1]), kv[0]))]


def by_day(rows, since, today):
    days = {}
    day = datetime.date.fromisoformat(since)
    while day <= today:
        days[day.isoformat()] = {"day": day.isoformat(), "merged": 0, "loop_built": 0}
        day += datetime.timedelta(days=1)
    for row in rows:
        if row["merged"] in days:
            days[row["merged"]]["merged"] += 1
            days[row["merged"]]["loop_built"] += int(row["loop_built"])
    return list(days.values())


def milestone_rows(raw, since):
    met, open_ = [], []
    for m in raw:
        row = {"title": m.get("title") if isinstance(m.get("title"), str) else "",
               "url": m.get("html_url") if isinstance(m.get("html_url"), str) else None,
               "issues_closed": m.get("closed_issues") if isinstance(m.get("closed_issues"), int) else 0,
               "issues_open": m.get("open_issues") if isinstance(m.get("open_issues"), int) else 0,
               "due": m["due_on"][:10] if isinstance(m.get("due_on"), str) else None}
        if m.get("state") == "closed" and isinstance(m.get("closed_at"), str):
            if m["closed_at"][:10] >= since:
                met.append(dict(row, closed=m["closed_at"][:10]))
        elif m.get("state") == "open":
            open_.append(row)
    return {"met": sorted(met, key=lambda r: r["closed"]), "open": sorted(open_, key=lambda r: (r["due"] or "~", r["title"]))}


def release_rows(raw, since):
    out = [{"name": r.get("name") or r.get("tagName") or "", "tag": r.get("tagName"), "published": r["publishedAt"][:10]}
           for r in raw if isinstance(r.get("publishedAt"), str) and r["publishedAt"][:10] >= since and not r.get("isDraft")]
    return sorted(out, key=lambda r: r["published"])


def changelog_rows(text, since):
    return [{"date": d, "name": n.strip()} for d, n in CHANGELOG_HEADING.findall(text) if d >= since]


def spec_rows(rows):
    specs = defaultdict(list)
    for row in rows:
        for spec in row["specs"]:
            specs[spec].append(row["number"])
    return [{"spec": s, "pull_requests": numbers} for s, numbers in sorted(specs.items())]


def build(root, since, today, name="harness", now=None):
    now = now or datetime.datetime.now().astimezone()
    search = "merged:>={}".format(since)
    prs = flat(gh(root, "pr", "list", "--state", "merged", "--search", search, "--json", PR_FIELDS, "--limit", str(LIMIT)))
    issues = flat(gh(root, "issue", "list", "--state", "closed", "--search", "closed:>={}".format(since),
                     "--json", "number,body", "--limit", str(LIMIT)))
    specs = {i["number"]: spec_of(i) for i in issues or [] if isinstance(i.get("number"), int)}
    doc = {"schema": SCHEMA, "generated": now.isoformat(timespec="seconds"), "repo": name,
           "since": since, "until": today.isoformat(),
           "truncated": len(prs or []) >= LIMIT or len(issues or []) >= LIMIT}
    if prs is None:
        for key in ("pull_requests", "totals", "by_person", "by_day", "specs"):
            doc[key] = missing("gh unavailable")
    else:
        rows = pull_request_rows(prs, specs)
        doc.update(pull_requests=rows, totals=counts(rows), by_person=by_person(rows), by_day=by_day(rows, since, today),
                   specs=spec_rows(rows) if issues is not None else missing("gh unavailable"))
    raw = flat(gh(root, "api", "repos/{owner}/{repo}/milestones?state=all&per_page=100", "--paginate"))
    doc["milestones"] = milestone_rows(raw, since) if raw is not None else missing("gh unavailable")
    raw = flat(gh(root, "release", "list", "--json", "name,tagName,publishedAt,isDraft", "--limit", "100"))
    doc["releases"] = release_rows(raw, since) if raw is not None else missing("gh unavailable")
    try:
        doc["changelog"] = changelog_rows((Path(root) / "CHANGELOG.md").read_text(encoding="utf-8"), since)
    except OSError:
        doc["changelog"] = missing("no CHANGELOG.md")
    return doc


def unavailable(section):
    return isinstance(section, dict) and section.get("value") is None and "why" in section


def duration(minutes):
    if minutes is None:
        return "n/a"
    return "{} min".format(round(minutes)) if minutes < 60 else "{:.1f} h".format(minutes / 60)


def short(day):
    return datetime.date.fromisoformat(day).strftime("%b %-d")


def chart(days):
    """A Mermaid bar chart of merges, a day a bar up to 31 days and a week a bar after that, with a line for the loop's."""
    if len(days) > 31:
        weeks = []
        for i in range(0, len(days), 7):
            chunk = days[i:i + 7]
            weeks.append({"day": chunk[0]["day"], "merged": sum(d["merged"] for d in chunk),
                          "loop_built": sum(d["loop_built"] for d in chunk)})
        days, unit = weeks, "week from"
    else:
        unit = "day"
    top = max([d["merged"] for d in days] + [1])
    return "\n".join([
        "```mermaid",
        "xychart-beta",
        '    x-axis [{}]'.format(", ".join('"{}"'.format(short(d["day"])) for d in days)),
        '    y-axis "Merged" 0 --> {}'.format(top),
        "    bar [{}]".format(", ".join(str(d["merged"]) for d in days)),
        "    line [{}]".format(", ".join(str(d["loop_built"]) for d in days)),
        "```",
        "",
        "Bars are every merged pull request a {}; the line is the ones the loop built.".format(unit),
    ])


def markdown(doc):
    out = ["# Work report: {}, {} to {}".format(doc["repo"], doc["since"], doc["until"]), ""]
    if doc["truncated"]:
        out += ["gh's search stopped at {} results, so the counts below are low.".format(LIMIT), ""]
    out += ["## In numbers", ""]
    totals = doc["totals"]
    if unavailable(totals):
        out += ["Not available: {}.".format(totals["why"]), ""]
    else:
        n = totals["merged"]
        out += ["| | |", "|---|---:|",
                "| Pull requests merged | {} |".format(n),
                "| Built by the loop | {} |".format(totals["loop_built"]),
                "| Built by hand | {} |".format(totals["hand_built"]),
                "| Issues closed by a merge | {} |".format(totals["issues_closed"]),
                "| Reviewed by a second person | {} of {} |".format(totals["second_reviewer"], n),
                "| On a milestone or a spec | {} of {} |".format(totals["on_a_milestone_or_spec"], n),
                "| Median time from opened to merged | {} |".format(duration(totals["median_minutes_to_merge"])),
                "", "## Merges", "", chart(doc["by_day"]), ""]
    out += ["## Milestones", ""]
    releases, milestones = doc["releases"], doc["milestones"]
    met = [] if unavailable(releases) else ["- {} · Release {}".format(short(r["published"]), r["name"]) for r in releases]
    if not unavailable(milestones):
        met += ["- {} · {} ({} issues){}".format(short(m["closed"]), m["title"], m["issues_closed"],
                                                 " " + m["url"] if m["url"] else "") for m in milestones["met"]]
    out += met or ["None reached in this period."]
    for section, what in ((releases, "Releases"), (milestones, "GitHub milestones")):
        if unavailable(section):
            out += ["", "{} not available: {}.".format(what, section["why"])]
    if not unavailable(milestones) and milestones["open"]:
        out += ["", "In flight:", ""]
        out += ["- {}: {} of {} issues closed{}".format(m["title"], m["issues_closed"], m["issues_closed"] + m["issues_open"],
                                                        ", due " + short(m["due"]) if m["due"] else "") for m in milestones["open"]]
    out += ["", "## By person", ""]
    if unavailable(doc["by_person"]):
        out += ["Not available: {}.".format(doc["by_person"]["why"])]
    elif not doc["by_person"]:
        out += ["Nobody merged a pull request in this period."]
    else:
        out += ["| Login | Merged | By hand | By the loop | Issues closed | Second reviewer | Median to merge |",
                "|---|---:|---:|---:|---:|---:|---:|"]
        out += ["| {login} | {merged} | {hand_built} | {loop_built} | {issues_closed} | {second_reviewer} | {m} |".format(
            m=duration(p["median_minutes_to_merge"]), **p) for p in doc["by_person"]]
    out += ["", "## Specs", ""]
    if unavailable(doc["specs"]):
        out += ["Not available: {}.".format(doc["specs"]["why"])]
    elif not doc["specs"]:
        out += ["No closed issue named a spec. An issue names one with a `Spec:` line in its References."]
    else:
        out += ["- {}: {} pull requests".format(s["spec"], len(s["pull_requests"])) for s in doc["specs"]]
    out += ["", "## What shipped", ""]
    shipped = doc["changelog"]
    if unavailable(shipped):
        out += ["Not available: {}.".format(shipped["why"])]
    elif not shipped:
        out += ["No CHANGELOG.md entries in this period."]
    else:
        out += ["- {} · {}".format(short(e["date"]), e["name"]) for e in shipped[:SHIPPED_SHOWN]]
        if len(shipped) > SHIPPED_SHOWN:
            out += ["- and {} more in CHANGELOG.md".format(len(shipped) - SHIPPED_SHOWN)]
    return "\n".join(out) + "\n"


def main(argv=None, root=ROOT):
    now = datetime.datetime.now().astimezone()
    today = now.date()
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--since", type=since_date, default=(today - datetime.timedelta(days=14)).isoformat(),
                        help="the first day to count, as YYYY-MM-DD (default: 14 days ago)")
    parser.add_argument("--project", help="a repo under projects/ to report on instead of the harness")
    parser.add_argument("--json", action="store_true", help="print the numbers as JSON instead of Markdown")
    args = parser.parse_args(argv)
    repo, name = Path(root), "harness"
    if args.project:
        repo, name = Path(root) / "projects" / args.project, args.project
        if "/" in args.project or not (repo / ".git").exists():
            parser.error("no repo at projects/{}".format(args.project))
    doc = build(repo, args.since, today, name, now)
    print(json.dumps(doc, indent=2) if args.json else markdown(doc), end="" if not args.json else "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
