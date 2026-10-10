---
name: loop-control
description: Drive the loop in scripts/loop.py from a conversation. Put an issue on it after checking it's ready, start it, say what it did, or stop it in the right order. Use when someone says "put #12 on the loop", "is this ready for the loop", "start the loop", "run the loop on #12", "what did the loop do", "why is #12 blocked", or "stop the loop".
license: MIT. From the Sanvio Labs harness starter, https://github.com/SanvioLabs/sanvio-harness-starter
---

# Loop control

[`scripts/loop.py`](../../scripts/loop.py) takes an issue labelled `loop-ready`, plans it, builds it,
runs the tests, has a fresh agent review it and opens a pull request.
[`HOW-IT-WORKS.md`](../../HOW-IT-WORKS.md) (*The loop*) says how. This skill is the conversation
around it: what goes on the loop, when it starts, what it did and how it
stops. Four jobs. Do the one asked for.

## Put an issue on the loop

A ticket is an instruction to an agent that runs without anyone watching, so
it gets read before it's labelled.

1. **Read it:** `gh issue view <N>`. Read the comments too.
2. **Check it's ready** against [`steering/tickets.md`](../../steering/tickets.md). All of these, or it isn't:
   - **One change**, small enough for one pull request.
   - **A "done means"** that a check can prove: a test that should fail now
     and pass after, or a command and what it should print. "Make it better"
     isn't one.
   - **Nothing outside the repo:** no deploying, sending, publishing,
     credentials, or anything the guard would refuse.
   - **Not assigned to someone else.** The loop skips those anyway.
3. **If something's missing,** draft the missing part (usually the "done
   means") in the shape of [`.github/ISSUE_TEMPLATE/loop-task.md`](../../.github/ISSUE_TEMPLATE/loop-task.md), and show it. The person adds it to the issue, or tells you to.
4. **Check where the pull request would go:** `gh repo view --json visibility
   -q .visibility`. If it's `PUBLIC`, say the pull request will be public and
   ask whether that's meant. A copy of the public starter is public until
   someone makes it otherwise.
5. **Ask, then label:** "Label #N `loop-ready`?" On a yes,
   `gh issue edit <N> --add-label loop-ready`. Label only issues the person
   has read in this conversation or wrote themselves.

## Start it

1. Run `python3 scripts/check_setup.py`. Fix or name any FAIL before going on.
2. Run `python3 scripts/loop.py run --dry-run` and say which issue it would
   take. Nothing ready means say so and stop.
3. Ask: one issue (`--once`, or `--issue <N>` for a particular one) or every
   ready issue (`run` alone, which keeps going until the queue is empty).
4. Start it in the background, so the conversation stays free. Then say how to
   watch it: `/loop-pane` in Claude Code, or `tail -f .loop/loop.log`.

## Say what it did

1. Read `.loop/status.json` for where each issue ended, then that issue's
   folder: `.loop/issue-<N>/plan.md`, `review.md`, and the end of
   `test-output.txt`.
2. Report, in this order:
   - how it ended: a pull request (with its link), blocked, stopped or skipped
   - how many rounds it took
   - what the review found, most important first
   - what the review couldn't check: the default reviewer reads, it doesn't
     run commands, so name anything it took on trust
3. **Blocked:** say why, from `review.md` and the last test output, and point
   at the entry in `.loop/lessons.md`. If the cause is the ticket (no check,
   too big), say what to change in it. The `learn` skill turns a repeated
   lesson into a rule.
4. **A pull request:** suggest reading its diff before merging. The loop never
   merges, and neither does this skill.

## Stop it

The order matters. Stopping alone lets the loop take the issue straight back.

1. Take the label off first: `gh issue edit <N> --remove-label loop-ready`.
2. Then `python3 scripts/loop.py stop`. The loop ends at its next step, not
   mid-step.
3. Say what it was doing when it stopped, from `.loop/status.json`.

## Rules

- Never label an issue the person hasn't read or written.
- Never merge a pull request the loop opened, or approve one.
- Never take `loop:blocked` off an issue without the person: it's the record
  that the loop gave up.
- Never edit anything under `.loop/`. The loop writes it; you read it.
- The test command lives in `loop.json`, and the person sets it. If the proof
  an issue needs isn't in it, say so rather than changing it.

## Output

For each job, one short report: what you checked or did, the issue number,
and the pull request link or the reason it stopped. Every label added or taken
off is named.
