---
name: work-report
description: Write a one-page report of what got done in a repo over a period, for a lead or a team: what merged and who did it, what the loop built, the milestones GitHub recorded, the specs it touched, a chart of merges, and what to watch. Reads GitHub through gh and the repo's CHANGELOG.md and changes nothing. Use when someone asks for a "work report", "what got done", "what did we ship", "which milestones did we hit", "a report for my lead", "showcase the work", or "what did the team do this sprint".
license: MIT. From the Sanvio Labs harness starter, https://github.com/SanvioLabs/sanvio-harness-starter
---

# Work report

One page on what got done in one repo over a period, built from what GitHub
recorded rather than what anyone remembers. [`scripts/work_report.py`](../../scripts/work_report.py) reads
the facts: merged pull requests, their authors and reviewers, the issues they
closed, releases, GitHub milestones, the `Spec:` lines on closed issues, and
the repo's [`CHANGELOG.md`](../../CHANGELOG.md). You add the summary and what to watch, from those
numbers only.

It names people. Each pull request's author and reviewers appear by GitHub
login, with its number and title, because a lead reads it to see who did what.
Say so when you hand it over, and the people it names should be able to read
the same report.

## Steps

1. **Pick the repo and the period.** The harness itself by default, or a repo
   under [`projects/`](../../projects/) by its folder name. Ask for the period, and default to
   the last 14 days. One repo per report. Repos for different customers never
   go into one report for anyone but the person running it:
   [`steering/data-and-tools.md`](../../steering/data-and-tools.md) has why.
2. **Run the script:**

   ```bash
   python3 scripts/work_report.py --since <YYYY-MM-DD>
   python3 scripts/work_report.py --since <YYYY-MM-DD> --project <name>
   ```

   It prints the facts as Markdown. A section that says `Not available` stays
   that way in the report, with its reason; the usual one is gh not signed in
   (`gh auth status`). Don't fill a gap from memory.
3. **Write the report** to `reports/work/<YYYY-MM-DD>-<repo>.md`:
   - The script's title line.
   - `## Summary`: three to five sentences. Lead with what was delivered (the
     milestones met and releases), then how much merged and how much the loop
     built, then who. Every figure in it is one the script printed.
   - The script's output as printed, from `## In numbers` down. The `## Merges`
     chart is Mermaid, which GitHub and most Markdown viewers draw.
   - `## What to watch`: one line each, with its figure, for whichever of these
     the numbers show: merged pull requests with no second reviewer, merged
     work on no milestone or spec, an open milestone past its due date, and the
     script's line about stopping at its limit. If none apply, say so.

   Describe the work, never the person: no "productive", "slow" or ranking.
4. **Have them read it.** Name what it holds that others will see: GitHub
   logins, pull request titles and addresses.
5. **Say how to share it.** It stays in [`reports/work/`](../../reports/work/), gitignored, and they
   send it. If they want it as a page or a post, that's a publish, and it
   waits for their yes to that one step. Run the `reviewer` agent on it first.

## Making milestones and specs show up

The report counts only what GitHub records, so a team gets out of it what it
puts in:

- **A deliverable is a GitHub milestone.** Name it after the deliverable or
  goal, put its issues on it, and close it when they're done. The report counts
  it met on the day it closed, and lists open ones with their progress and due
  date.
- **A release is a milestone too.** `gh release create` records it.
- **An issue names its spec** with one line in its References section:
  `Spec: specs/004-search REQ-002`.
- **Loop work needs nothing.** The script knows it by the loop's branch,
  `loop/issue-N`.

A CHANGELOG entry is what shipped, in words. It's never counted as a
milestone.

## Rules

- Every figure in the report comes from the script's output.
- Never put an issue's or a pull request's body, a commit message or an email
  address in the report.
- Never commit a report, force-add it, or send it anywhere. They send it.
- Change nothing on GitHub: no labels, comments or milestones.

## Output

The report file, read by the person it's for, and its path.
