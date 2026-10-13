---
name: standup
description: One morning read of what's on this person, from the sources the harness can reach, then a walk through the items one at a time and a suggested order for the day. Reads only, changes nothing. Use when someone says "standup", "morning check", "what's on me today", "what's on my plate", "what do I need to do first", or "start my day".
license: MIT. From the Sanvio Labs harness starter, https://github.com/SanvioLabs/sanvio-harness-starter
---

# Standup

Starting the day means checking the same places by hand. This skill checks them
in one pass, says where to start, and asks about each item so the order for the
day comes from the person, not a guess.

It changes nothing. It sends nothing, comments nowhere, and edits no issue,
label, pull request or calendar entry. Where an answer implies a change, it
gives the command and the person runs it.

## Steps

1. **Gather from GitHub.** `gh` has to be signed in: check with `gh auth status`
   and, if it isn't, skip this source, say why in step 4 and carry on with the
   others. Don't guess at its items. Otherwise, read only:

   ```bash
   gh search prs --review-requested=@me --state=open --sort updated --limit 10 --json number,title,url,repository,updatedAt
   gh search prs --author=@me --state=open --sort updated --limit 10 --json number,title,url,repository,isDraft,updatedAt
   gh search issues --assignee=@me --state=open --sort updated --limit 10 --json number,title,url,repository,updatedAt
   ```

   For each of their own pull requests, read the state of its checks and of its
   review:

   ```bash
   gh pr checks <number> --repo <owner/repo>
   gh pr view <number> --repo <owner/repo> --json reviewDecision
   ```

   Call the checks passing, failing, pending or none (`gh pr checks` reports
   "no checks" when the repository has no CI). A `reviewDecision` of
   `APPROVED`, `CHANGES_REQUESTED` or `REVIEW_REQUIRED` is as it says. An empty
   one means the repository requires no review, so the pull request is waiting
   on nothing but its checks.

   Each search above returns the 10 most recently updated. To say how many were
   left out, take the total of each kind and subtract the ones shown:

   ```bash
   gh api "search/issues?q=is:pr+is:open+review-requested:@me&per_page=1" --jq .total_count
   gh api "search/issues?q=is:pr+is:open+author:@me&per_page=1" --jq .total_count
   gh api "search/issues?q=is:issue+is:open+assignee:@me&per_page=1" --jq .total_count
   ```
2. **Gather from the loop.** If `.loop/status.json` exists, read its `issues`.
   Keep the ones whose `state` is `pr` or `blocked` and whose `updated` time is
   within the last 24 hours. A `pr` is a pull request the loop opened and won't
   merge. A `blocked` issue has its `note`. If the file is missing, skip this
   source and say so in step 4.
3. **Gather from optional sources.** Calendar (today's meetings), email (what
   needs an answer) and a ticket tracker (what's assigned) are used only when a
   connector for them is available in this session and `company/DATA.md`, if it
   exists, clears it. List and search calls only. Never an accept, decline,
   reply, label, draft or update call. Today's meetings go in as one line each
   with their time.
4. **Name what was skipped.** One line per source that wasn't read, saying why:
   `Calendar: skipped, no calendar connector in this session.` or
   `GitHub: skipped, gh isn't signed in.` Never leave a
   source out silently, and never invent an item for one you couldn't reach.
5. **Report.** Lead with one line:

   ```
   Start here: <the single item to do first, and why in a few words>
   ```

   Then two sections, one line per item, each with its link:

   - **On you:** reviews requested of them, their own pull requests that are
     failing, have changes requested, are still drafts, or have passing or no
     checks and are either approved or need no review (ready to merge), issues assigned
     to them, loop issues that are `blocked` or whose `pr` is waiting for their
     review and merge, emails to answer, today's meetings.
   - **Waiting on someone:** their own pull requests that are not drafts, have
     no failing checks and are either waiting on a review (`REVIEW_REQUIRED`) or
     approved or needing no review with checks still pending, and anything
     they've handed on.

   Leave out a section with nothing in it. If both are empty, say the day is
   clear and name the sources read. The skipped-source lines go last.
6. **Walk the items.** After the report, ask about the items one at a time, in
   the order they're listed, one question per turn: *done, still on, drop, or
   move up?* Wait for the answer before the next. Take "all still on" or "skip
   the rest" as an answer for everything left.
7. **Suggest the order.** End with the day's order: what they said is still on,
   with "move up" first, then by what blocks someone else. A review someone is
   waiting on goes ahead of work only they are waiting on. Drop the dropped and
   the done.

## Rules

- Read only, every source. If an answer implies a change (close this issue,
  remove a label, decline a meeting), give the command or the one line to do
  it and leave running it to them. Never ask "shall I?" and then do it.
- Never post a comment, a review or a status, and never send a message, even
  to remind someone.
- Don't read the body of an email or a meeting's notes beyond what one line
  needs. Subject, sender and time are enough.
- One line per item. No summaries of pull request diffs; that's
  [`skills/review-pr/`](../review-pr/SKILL.md).
- An item you couldn't verify is marked as such, not dropped and not guessed.

## Output

The "Start here" line, "On you", "Waiting on someone" (each omitted if empty),
the skipped-source lines, then the one-at-a-time questions, and last the
suggested order for the day. Per [`steering/response-style.md`](../../steering/response-style.md),
no confidence line: this is a lookup, not a recommendation.
