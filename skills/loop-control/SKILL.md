---
name: loop-control
description: Drive the loop in scripts/loop.py from a conversation. Put an issue on it after checking it's ready, start it, say what it did, or stop it in the right order, or start the pull-request reviewer. Use when someone says "put #12 on the loop", "is this ready for the loop", "start the loop", "run the loop on #12", "what did the loop do", "why is #12 blocked", "stop the loop", or "review the pull requests waiting on me".
license: MIT. From the Sanvio Labs harness starter, https://github.com/SanvioLabs/sanvio-harness-starter
---

# Loop control

[`scripts/loop.py`](../../scripts/loop.py) takes an issue labelled `loop-ready`, plans it, builds it,
runs the tests, has a fresh agent review it and opens a pull request.
[`HOW-IT-WORKS.md`](../../HOW-IT-WORKS.md) (*The loop*) says how. This skill is the conversation
around it: what goes on the loop, when it starts, what it did and how it
stops, and the pull-request reviewer beside it. Five jobs. Do the one asked for.

## Put an issue on the loop

A ticket is an instruction to an agent that runs without anyone watching, so
it gets read before it's labelled.

1. **Read it:** `gh issue view <N>`. Read the comments too.
2. **Check it's ready** against [`steering/tickets.md`](../../steering/tickets.md). All of these, or it isn't:
   - **One change**, small enough for one pull request.
   - **Acceptance criteria** a check can prove, at least one of them by a
     test that fails now and passes after. "Make it better" isn't one.
   - **Risk Low or Medium,** and no Human Approval section. Open
     dependencies needn't stop you labelling it: the loop waits for them.
     `WAITING` lines in `.loop/loop.log`, and `waiting_on` on the issue's
     entry in the queue in `.loop/status.json`, show what it waits on.
   - **Where Stelliad is installed,** `stelliad:review-ticket <N>` says READY.
   - **Nothing outside the repo:** no deploying, sending, publishing,
     credentials, or anything the guard would refuse.
   - **Not assigned to someone else.** The loop skips those anyway.
3. **If something's missing,** draft the missing part (usually the
   acceptance criteria) in the shape of [`.github/ISSUE_TEMPLATE/loop-task.md`](../../.github/ISSUE_TEMPLATE/loop-task.md), and show it. The person adds it to the issue, or tells you to.
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
   ready issue (`run` alone, which keeps going until the queue is empty). For
   every ready issue over a set time, such as overnight, add `--for 8h` (a whole
   number then `m`, `h` or `d`). After that time it takes no new issue, lets
   each running one finish, logs `END --for 8h reached` and exits.
4. Start it in tmux when `command -v tmux` finds it, so it outlives this
   conversation and the person can open it and watch. One session per clone,
   named after the folder (tmux won't take a dot or a colon in a name), with the
   flags from step 3 in place of `<flags>`:

   ```bash
   name="loop-$(basename "$PWD" | tr '.:' '--')"
   tmux new-session -d -s "$name" -c "$PWD" \
     "python3 scripts/loop.py run <flags>; echo; echo 'The loop has exited. Press Enter to close.'; read _"
   ```

   If `tmux new-session` says `duplicate session`, a loop is probably
   running there: say so and give the attach command rather than starting a
   second. The loop's lock refuses a second run in one clone anyway.
   Without tmux, start it in the background instead, and say that it stops
   when this session ends.
5. Check it started: `tail -3 .loop/loop.log` shows a `START` line naming
   the tmux session (none without tmux), an `UNTIL` line with `--for`'s end
   time, then `DISCOVER` or `IDLE`. Then say
   how to watch it: `tmux attach -t <name>` (`Ctrl-b d` leaves it
   running), `/loop-pane` in Claude Code, or `tail -f .loop/loop.log`.

`max_workers` in `loop.json` (default 1) is how many issues `run` works at
once. Each worker runs its own agent sessions, so say that usage grows with the
number before the person raises it. Each issue's agents write to
`.loop/issue-<N>/agent.log` as they go, and in tmux each issue gets a window
named `issue-<N>` that follows it (`Ctrl-b w` lists them) and closes when the
issue ends. A stop lets every running issue finish its step.

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

## Review pull requests

`python3 scripts/loop.py review` is the other half of the queue: it reviews
each open pull request that asks for the person (`review_query`, by default
`review-requested:@me`), once per head commit, with
[`skills/review-pr/`](../review-pr/SKILL.md), and posts the report as one comment per pull request,
edited in place on later commits. Start it only when asked.

1. Run `python3 scripts/check_setup.py`, then say what it will do: which pull
   requests match, and that the comments go up under the person's own GitHub
   identity. Ask before starting.
2. `python3 scripts/loop.py review --once` reviews what is waiting and exits;
   without `--once` it keeps watching. Start it in tmux as under *Start it*,
   with that command in place of `run <flags>`.
3. It takes the same lock as `run`, so one process works a clone at a time. If
   the loop is running here, say so: the review needs its own clone, or waits.
4. Say what it did from `.loop/loop.log`: one `REVIEW #N <sha> posted`,
   `skipped` or `failed: <why>` line per pull request and commit. A review
   whose agent exited non-zero or timed out, or whose diff couldn't be made,
   posted nothing and isn't retried until the pull request has a new commit. A
   fetch, checkout or post error ends in `(will retry)` and is tried again on
   the next poll. `loop.py stop` ends it at its next step.

It never approves, requests changes, merges or pushes, and the agent is never
asked to post: the script does. A person decides what happens to the pull
request.

## Stop it

The order matters. Stopping alone lets the loop take the issue straight back.

1. Take the label off first: `gh issue edit <N> --remove-label loop-ready`.
2. Then `python3 scripts/loop.py stop`. The loop ends at its next step, not
   mid-step.
3. Say what it was doing when it stopped, from `.loop/status.json`. In tmux,
   its session waits for Enter once the loop exits, so the last lines stay
   readable; `tmux kill-session -t <name>` closes it.

## Rules

- Never label an issue the person hasn't read or written.
- Never merge a pull request the loop opened, or approve one. `loop.py review`
  doesn't approve or merge either, and nothing here makes it.
- Never take `loop:blocked` off an issue without the person: it's the record
  that the loop gave up.
- Never edit anything under `.loop/`. The loop writes it; you read it.
- The test command lives in `loop.json`, and the person sets it. If the proof
  an issue needs isn't in it, say so rather than changing it.

## Output

For each job, one short report: what you checked or did, the issue number,
and the pull request link or the reason it stopped. Every label added or taken
off is named.
