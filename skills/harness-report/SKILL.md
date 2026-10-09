---
name: harness-report
description: Turn your harness usage for a sprint into a short report you share with the harness owner, with what you'd add, change or drop. Reads only your own local usage log, and you read the report before it goes anywhere. Use at the end of a sprint, or when someone asks for "my harness report", "what did I use this sprint", "sprint follow-up", or "what should we add to the harness".
---

# Harness report

Each person's usage log stays on their own machine. This turns it into the one
thing that's shared: a short report, with the person's own proposals, opened
as a pull request on the harness. The owner reads the sprint's reports together
and decides what goes into the harness.

The log is written by [`.claude/hooks/usage_log.py`](../../.claude/hooks/usage_log.py). It holds names and counts,
never prompts, paths or code.

## Steps

1. **Pick the period.** Use the date of their last report in
   [`reports/usage/`](../../reports/usage/) (the newest file with their name) as the start. If there
   isn't one, ask how long their sprint is, and default to 14 days.
2. **Run the summary:**

   ```bash
   python3 scripts/usage_report.py --since <YYYY-MM-DD>
   ```

   If it says there's no log, tell them why it might be missing (the hook isn't
   wired, or `HARNESS_USAGE_LOG` is off) and stop. Don't guess at their usage.
3. **Show them the summary,** then ask, one at a time:
   - What worked well enough that the team should use it?
   - Where did you work around the harness: a skill you skipped, a guard you
     kept saying yes to, a step you did by hand?
   - One or two proposals. For each: add, change or drop what, and why.
   Use their words. Point at the numbers where they back a proposal up ("asked
   12 times, said yes 12 times" argues for loosening that ask). Don't invent a
   proposal they didn't make.
4. **Write the report** to `reports/usage/<YYYY-MM-DD>-<user>.md`: the summary
   as printed, then a `## Proposals` section with their answers. Leave nothing
   unfilled.
5. **Have them read it.** It's going to the team. They can cut anything.
6. **Name the commands to share it,** and let them run them:

   ```bash
   git checkout -b report/<YYYY-MM-DD>-<user>
   git add reports/usage/<YYYY-MM-DD>-<user>.md
   git commit -m "Harness report, <YYYY-MM-DD>"
   ```

   Then a pull request to the harness's main branch.

## For the owner

Read the sprint's report PRs together, not one at a time. A pattern across
people is the signal: the same skill never used, the same ask answered yes
every time, the same workaround. Merge the reports as the record. For each
proposal you take, make the change in its own PR with a [`CHANGELOG.md`](../../CHANGELOG.md) entry,
so "what's new" tells everyone. For one you don't, say why on the report's PR.

## Rules

- Never read or quote another person's log. Each report comes from its
  author's own machine.
- Never add a prompt, a file path, a command or code to the report, even if
  they mention one. Describe it instead ("a deploy script", not the script).
- Never commit anything under `.harness/`. The raw log stays local.
- Never push or open the PR yourself. Name the commands.

## Output

The report file, read by its author, and the commands that share it.
