#!/usr/bin/env python3
"""What got done in a repo over a period, from GitHub and its CHANGELOG, for a work report.

    python3 scripts/work_report.py                       # the harness, since 14 days ago, as Markdown
    python3 scripts/work_report.py --since 2026-10-01
    python3 scripts/work_report.py --project app         # a repo under projects/ instead
    python3 scripts/work_report.py --json

It reads, through gh, in the harness root or the repo under projects/:

    pull_requests  each pull request merged on or after --since, through one GraphQL search: its number,
                   title, address, author's login, when it opened and merged, the issues it closes, its
                   milestone, who else reviewed it and who else approved it, and the specs its closed
                   issues name. loop_built is true when its branch is loop/issue-N, the branch the loop
                   opens; the loop opens it as whoever runs the loop, so it counts as that login's. A
                   review counts when its author isn't the pull request's and isn't a bot (GitHub's Bot
                   type, which gh's own reviews field doesn't show), and isn't pending or dismissed. An
                   approval is such a review in the APPROVED state
    totals         counts over those, and the median minutes from opened to merged
    by_person      for each login that authored or reviewed one: the same counts, and reviews_given, how
                   many of the others' pull requests it reviewed
    by_day         every UTC day from --since to today's UTC date, oldest first, with merged and loop_built
    milestones     GitHub milestones: closed, the ones closed on or after --since, and open, each with its
                   issues closed and still open and its due date
    releases       releases published on or after --since, drafts left out, from the newest RELEASES
    specs          for each spec a closed issue names, the pull requests that closed one. An issue names
                   it with a line "Spec: <path> [requirement ...]"; the path, its first word, is the spec
    changelog      CHANGELOG.md's entries dated on or after --since, newest first: what shipped, in words
    watch          sentences on what a lead would ask about: merged work nobody else approved, work on no
                   milestone or spec, a milestone closed late or with issues open, one past its due date,
                   and a search that stopped at its limit

Milestones are only what GitHub records: a release or a closed milestone. It never picks one, and a
CHANGELOG entry is not a milestone.

Unlike the other reports here, this one names people. It prints each pull request's author, reviewers
and approvers by GitHub login, with its number, title and address, because a lead reads it to see who
did what. It never prints an issue's or a pull request's body, beyond the one "Spec:" line's value,
nor a commit message, a diff or an email.

A section whose source is missing or can't be read is {"value": null, "why": ...}, and the script still
exits 0. GitHub's search returns at most LIMIT pull requests; truncated says when there were more, and
then the counts are low.
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
LIMIT = 1000  # GitHub's search returns no more than this
RELEASES = 100  # newest releases read
QUERY = """query($q: String!, $endCursor: String) {
  search(query: $q, type: ISSUE, first: 100, after: $endCursor) {
    issueCount
    pageInfo { hasNextPage endCursor }
    nodes { ... on PullRequest {
      number title url createdAt mergedAt headRefName
      author { __typename login }
      milestone { title }
      closingIssuesReferences(first: 20) { nodes { number body } }
      reviews(first: 50) { nodes { state author { __typename login } } }
    } }
  }
}"""
COUNTED_REVIEWS = {"APPROVED", "CHANGES_REQUESTED", "COMMENTED"}
SPEC_LINE = re.compile(r"^\s*Spec:\s*(\S+)", re.M)
CHANGELOG_HEADING = re.compile(r"^## (\d{4}-\d{2}-\d{2}): (\S.*)$", re.M)
SHIPPED_SHOWN = 15  # changelog entries the Markdown lists before "and N more"


def flat(pages):
    """The items of gh's pages, one array per page, or None when any page isn't a list."""
    if pages is None or not all(isinstance(page, list) for page in pages):
        return None
    return [item for page in pages for item in page if isinstance(item, dict)]


def searched(pages):
    """(pull requests, how many the search matched) from the GraphQL search's pages, or (None, 0)."""
    try:
        found = [page["data"]["search"] for page in pages or [None]]
        nodes = [node for page in found for node in page["nodes"] if isinstance(node, dict)]
        return nodes, found[0].get("issueCount") or 0
    except (KeyError, TypeError):
        return None, 0


def nodes(value):
    return [n for n in (value or {}).get("nodes") or [] if isinstance(n, dict)] if isinstance(value, dict) else []


def person(actor):
    """A login, or None for a bot or an account that no longer exists."""
    if not isinstance(actor, dict) or not isinstance(actor.get("login"), str):
        return None
    if actor.get("__typename") == "Bot" or actor["login"].endswith("[bot]"):
        return None
    return actor["login"]


def when(text):
    try:
        return datetime.datetime.fromisoformat(text.replace("Z", "+00:00"))
    except (AttributeError, ValueError):
        return None


def spec_of(issue):
    """The path on the first "Spec:" line of an issue's body, or None. Nothing else of the body is kept."""
    body = issue.get("body") if isinstance(issue.get("body"), str) else ""
    found = SPEC_LINE.search(body)
    return found.group(1)[:120] if found else None


def pull_request_rows(prs):
    """One row per merged pull request, oldest merge first."""
    rows = []
    for pr in prs:
        opened, merged = when(pr.get("createdAt")), when(pr.get("mergedAt"))
        if not isinstance(pr.get("number"), int) or merged is None:
            continue
        author = person(pr.get("author")) or (pr.get("author") or {}).get("login") or "ghost"
        issues = [i for i in nodes(pr.get("closingIssuesReferences")) if isinstance(i.get("number"), int)]
        reviews = [(person(r.get("author")), r.get("state")) for r in nodes(pr.get("reviews"))]
        reviews = [(who, state) for who, state in reviews if who and who != author and state in COUNTED_REVIEWS]
        milestone = pr.get("milestone") if isinstance(pr.get("milestone"), dict) else {}
        branch = pr.get("headRefName") if isinstance(pr.get("headRefName"), str) else ""
        rows.append({
            "number": pr["number"],
            "title": pr.get("title") if isinstance(pr.get("title"), str) else "",
            "url": pr.get("url") if isinstance(pr.get("url"), str) else None,
            "author": author,
            "merged": merged.date().isoformat(),
            "minutes_to_merge": round((merged - opened).total_seconds() / 60, 1) if opened else None,
            "closes": sorted(i["number"] for i in issues),
            "milestone": milestone.get("title") if isinstance(milestone.get("title"), str) else None,
            "loop_built": bool(LOOP_BRANCH.match(branch)),
            "reviewers": sorted({who for who, _ in reviews}),
            "approved_by": sorted({who for who, state in reviews if state == "APPROVED"}),
            "specs": sorted({s for s in map(spec_of, issues) if s}),
        })
    return sorted(rows, key=lambda r: (r["merged"], r["number"]))


def counts(rows):
    minutes = [r["minutes_to_merge"] for r in rows if r["minutes_to_merge"] is not None]
    return {"merged": len(rows),
            "loop_built": sum(1 for r in rows if r["loop_built"]),
            "hand_built": sum(1 for r in rows if not r["loop_built"]),
            "issues_closed": len({n for r in rows for n in r["closes"]}),
            "approved_by_another": sum(1 for r in rows if r["approved_by"]),
            "on_a_milestone_or_spec": sum(1 for r in rows if r["milestone"] or r["specs"]),
            "median_minutes_to_merge": round(statistics.median(minutes), 1) if minutes else None}


def by_person(rows):
    logins = {r["author"] for r in rows} | {who for r in rows for who in r["reviewers"]}
    people = [dict(counts([r for r in rows if r["author"] == who]), login=who,
                   reviews_given=sum(1 for r in rows if who in r["reviewers"])) for who in logins]
    return sorted(people, key=lambda p: (-p["merged"], -p["reviews_given"], p["login"]))


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
    closed, open_ = [], []
    for m in raw:
        row = {"title": m.get("title") if isinstance(m.get("title"), str) else "",
               "url": m.get("html_url") if isinstance(m.get("html_url"), str) else None,
               "issues_closed": m.get("closed_issues") if isinstance(m.get("closed_issues"), int) else 0,
               "issues_open": m.get("open_issues") if isinstance(m.get("open_issues"), int) else 0,
               "due": m["due_on"][:10] if isinstance(m.get("due_on"), str) else None}
        if m.get("state") == "closed" and isinstance(m.get("closed_at"), str):
            if m["closed_at"][:10] >= since:
                closed.append(dict(row, closed=m["closed_at"][:10]))
        elif m.get("state") == "open":
            open_.append(row)
    return {"closed": sorted(closed, key=lambda r: r["closed"]),
            "open": sorted(open_, key=lambda r: (r["due"] or "~", r["title"]))}


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


def short(day):
    return datetime.date.fromisoformat(day).strftime("%b %-d %Y")


def watch(doc, today):
    """What a lead would ask about, one sentence each, from the sections that could be read."""
    out = []
    if doc["truncated"]:
        out.append("GitHub's search stopped at {} pull requests, so every count here is low.".format(LIMIT))
    totals = doc["totals"]
    if "merged" in totals and totals["merged"]:
        n = totals["merged"]
        unapproved = n - totals["approved_by_another"]
        if unapproved:
            out.append("{} of {} merged pull requests weren't approved by anyone but their author.".format(unapproved, n))
        unlinked = n - totals["on_a_milestone_or_spec"]
        if unlinked:
            out.append("{} of {} merged pull requests are on no milestone and name no spec.".format(unlinked, n))
    milestones = doc["milestones"]
    if "closed" in milestones:
        for m in milestones["closed"]:
            if m["issues_open"]:
                out.append("{} closed with {} of its {} issues still open.".format(
                    m["title"], m["issues_open"], m["issues_open"] + m["issues_closed"]))
            if m["due"] and m["closed"] > m["due"]:
                out.append("{} closed on {}, after its due date of {}.".format(m["title"], short(m["closed"]), short(m["due"])))
        for m in milestones["open"]:
            if m["due"] and m["due"] < today.isoformat():
                out.append("{} is past its due date of {}, with {} of its {} issues open.".format(
                    m["title"], short(m["due"]), m["issues_open"], m["issues_open"] + m["issues_closed"]))
    return out


def build(root, since, today, name=None, now=None):
    now = now or datetime.datetime.now().astimezone()
    repo = gh(root, "repo", "view", "--json", "nameWithOwner")
    name = (repo[0].get("nameWithOwner") if repo and isinstance(repo[0], dict) else None) or name or Path(root).name
    prs, matched = searched(gh(root, "api", "graphql", "--paginate",
                               "-F", "q=repo:{{owner}}/{{repo}} is:pr is:merged merged:>={}".format(since),
                               "-f", "query=" + QUERY))
    doc = {"schema": SCHEMA, "generated": now.isoformat(timespec="seconds"), "repo": name,
           "since": since, "until": today.isoformat(), "truncated": matched > LIMIT}
    if prs is None:
        for key in ("pull_requests", "totals", "by_person", "by_day", "specs"):
            doc[key] = missing("gh unavailable")
    else:
        rows = pull_request_rows(prs)
        doc.update(pull_requests=rows, totals=counts(rows), by_person=by_person(rows),
                   by_day=by_day(rows, since, today), specs=spec_rows(rows))
    raw = flat(gh(root, "api", "repos/{owner}/{repo}/milestones?state=all&per_page=100", "--paginate"))
    doc["milestones"] = milestone_rows(raw, since) if raw is not None else missing("gh unavailable")
    raw = flat(gh(root, "release", "list", "--json", "name,tagName,publishedAt,isDraft", "--limit", str(RELEASES)))
    doc["releases"] = release_rows(raw, since) if raw is not None else missing("gh unavailable")
    try:
        doc["changelog"] = changelog_rows((Path(root) / "CHANGELOG.md").read_text(encoding="utf-8"), since)
    except OSError:
        doc["changelog"] = missing("no CHANGELOG.md")
    doc["watch"] = watch(doc, today)
    return doc


def unavailable(section):
    return isinstance(section, dict) and section.get("value") is None and "why" in section


def duration(minutes):
    if minutes is None:
        return "n/a"
    return "{} min".format(round(minutes)) if minutes < 60 else "{:.1f} h".format(minutes / 60)


def cell(text):
    return str(text).replace("|", "\\|").replace("\n", " ")


def chart(days):
    """A Mermaid bar chart of merges, a day a bar up to 31 days and a week a bar after that, with a line for the loop's."""
    if len(days) > 31:
        days = [{"day": days[i]["day"], "merged": sum(d["merged"] for d in days[i:i + 7]),
                 "loop_built": sum(d["loop_built"] for d in days[i:i + 7])} for i in range(0, len(days), 7)]
        unit = "week, starting the day shown"
    else:
        unit = "UTC day"
    top = max([d["merged"] for d in days] + [1])
    return "\n".join([
        "```mermaid",
        "xychart-beta",
        '    x-axis [{}]'.format(", ".join('"{}"'.format(datetime.date.fromisoformat(d["day"]).strftime("%b %-d")) for d in days)),
        '    y-axis "Merged" 0 --> {}'.format(top),
        "    bar [{}]".format(", ".join(str(d["merged"]) for d in days)),
        "    line [{}]".format(", ".join(str(d["loop_built"]) for d in days)),
        "```",
        "",
        "Each bar is the pull requests merged in a {}; the line is the ones the loop built.".format(unit),
    ])


def markdown(doc):
    out = ["# Work report: {}, {} to {}".format(doc["repo"], short(doc["since"]), short(doc["until"])), "", "## In numbers", ""]
    totals = doc["totals"]
    if unavailable(totals):
        out += ["Not available: {}.".format(totals["why"])]
    else:
        n = totals["merged"]
        out += ["| | |", "|---|---:|",
                "| Pull requests merged | {} |".format(n),
                "| Built by the loop | {} |".format(totals["loop_built"]),
                "| Built by hand | {} |".format(totals["hand_built"]),
                "| Issues closed by a merge | {} |".format(totals["issues_closed"]),
                "| Approved by someone other than the author | {} of {} |".format(totals["approved_by_another"], n),
                "| On a milestone or a spec | {} of {} |".format(totals["on_a_milestone_or_spec"], n),
                "| Median time from opened to merged | {} |".format(duration(totals["median_minutes_to_merge"])),
                "", "## Merges", "", chart(doc["by_day"])]
    out += ["", "## To watch", ""]
    out += ["- " + line for line in doc["watch"]] or ["Nothing in these numbers."]
    out += ["", "## Milestones", ""]
    releases, milestones = doc["releases"], doc["milestones"]
    reached = [] if unavailable(releases) else ["- {} · Release {}".format(short(r["published"]), r["name"]) for r in releases]
    if not unavailable(milestones):
        reached += ["- {} · {} closed: {} of {} issues{}{}".format(
            short(m["closed"]), m["title"], m["issues_closed"], m["issues_closed"] + m["issues_open"],
            ", due " + short(m["due"]) if m["due"] else "", " " + m["url"] if m["url"] else "") for m in milestones["closed"]]
    out += reached or ["None reached in this period."]
    for section, what in ((releases, "Releases"), (milestones, "GitHub milestones")):
        if unavailable(section):
            out += ["", "{} not available: {}.".format(what, section["why"])]
    if not unavailable(milestones) and milestones["open"]:
        out += ["", "Open:", ""]
        out += ["- {}: {} of {} issues closed{}".format(m["title"], m["issues_closed"], m["issues_closed"] + m["issues_open"],
                                                        ", due " + short(m["due"]) if m["due"] else "") for m in milestones["open"]]
    out += ["", "## By person", ""]
    if unavailable(doc["by_person"]):
        out += ["Not available: {}.".format(doc["by_person"]["why"])]
    elif not doc["by_person"]:
        out += ["Nobody merged a pull request in this period."]
    else:
        out += ["Loop-built pull requests count as the login the loop runs as. Reviews given counts the others' "
                "merged pull requests each login reviewed.", "",
                "| Login | Merged | By hand | By the loop | Issues closed | Approved by another | Reviews given | Median to merge |",
                "|---|---:|---:|---:|---:|---:|---:|---:|"]
        out += ["| {login} | {merged} | {hand_built} | {loop_built} | {issues_closed} | {approved_by_another} | {reviews_given} | {m} |".format(
            m=duration(p["median_minutes_to_merge"]), **p) for p in doc["by_person"]]
    out += ["", "## Specs", ""]
    if unavailable(doc["specs"]):
        out += ["Not available: {}.".format(doc["specs"]["why"])]
    elif not doc["specs"]:
        out += ["No closed issue named a spec. An issue names one with a `Spec:` line in its References."]
    else:
        out += ["- {}: {} pull request{}".format(s["spec"], len(s["pull_requests"]), "" if len(s["pull_requests"]) == 1 else "s")
                for s in doc["specs"]]
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
    if not unavailable(doc["pull_requests"]) and doc["pull_requests"]:
        out += ["", "## Pull requests", "",
                "| # | Title | Author | Built | Reviewed by | Merged |", "|---:|---|---|---|---|---|"]
        out += ["| {} | {} | {} | {} | {} | {} |".format(
            "[{}]({})".format(r["number"], r["url"]) if r["url"] else r["number"], cell(r["title"]), r["author"],
            "loop" if r["loop_built"] else "hand",
            ", ".join(w + (" (approved)" if w in r["approved_by"] else "") for w in r["reviewers"]) or "nobody else",
            r["merged"]) for r in reversed(doc["pull_requests"])]
    return "\n".join(out) + "\n"


def main(argv=None, root=ROOT):
    now = datetime.datetime.now().astimezone()
    today = now.astimezone(datetime.timezone.utc).date()  # merges are dated in UTC, so the period is too
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--since", type=since_date, default=(today - datetime.timedelta(days=14)).isoformat(),
                        help="the first day to count, as YYYY-MM-DD (default: 14 days ago)")
    parser.add_argument("--project", help="a repo under projects/ to report on instead of the harness")
    parser.add_argument("--json", action="store_true", help="print the numbers as JSON instead of Markdown")
    args = parser.parse_args(argv)
    repo = Path(root)
    if args.project:
        repo = Path(root) / "projects" / args.project
        if "/" in args.project or not (repo / ".git").exists():
            parser.error("no repo at projects/{}".format(args.project))
    doc = build(repo, args.since, today, args.project, now)
    print(json.dumps(doc, indent=2) if args.json else markdown(doc), end="\n" if args.json else "")
    return 0


if __name__ == "__main__":
    sys.exit(main())
