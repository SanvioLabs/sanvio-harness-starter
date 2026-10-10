# Tickets: what goes in one, and how one ends

Read this when you write an issue, put one on the loop, or close one.
[`.github/ISSUE_TEMPLATE/loop-task.md`](../.github/ISSUE_TEMPLATE/loop-task.md) is the shape; this file is why.

## What goes in

A ticket says what has to be true and how anyone can tell. It doesn't say how
to write the code: the rules in [`AGENTS.md`](../AGENTS.md) and the steering already do.

| Section | Holds | Fails when |
|---|---|---|
| **What and why** | One or two sentences | It describes a feeling ("make the gate better") rather than a change |
| **Done means** | The check that proves it: a test that fails now and passes after, or a command and what it prints | Nobody could run it. "Works well" is not a check |
| **Out of scope** | What it leaves alone | It's empty on a change that touches shared code |
| **Pointers** | Files to start from, a similar change. Optional | It turns into instructions for writing the code |

**One change per ticket.** If the "done means" has two unrelated checks, it's
two tickets. If it can't fit one pull request, split it so each part can be
tested on its own.

## Ready for the loop

Label an issue `loop-ready` only when all of these hold. The `loop-control`
skill checks them and asks before it labels.

- Someone has read the whole issue, comments included. A ticket is an
  instruction to an agent, and the loop acts on it with nobody watching.
- **Done means** is a check the loop's `test_command` can run. If the proof is
  something else, the loop can't see it, and the reviewer only reads.
- Nothing outside the repo: no deploy, no message, no credentials, nothing the
  guard would refuse.
- It isn't assigned to someone else.

## While it's worked

The loop comments on the issue twice at most, so the issue tells the story
without the machine that ran it:

- **A pull request opened:** the link, how many rounds it took, and that the
  tests and review passed.
- **Blocked:** why, the round count, and that the plan, test output and review
  are in `.loop/issue-N/` on the machine that ran it.

A person commenting adds what changed: a decision, a narrowed scope, an
answer to a question the review raised. A comment that changes the "done
means" changes the ticket, so edit the description too. The loop reads the
description, not the comments.

## How it ends

- **Done:** the pull request that does it says `Closes #N`, and merging it
  closes the issue. The loop writes that line itself. A pull request a person
  opens writes it too. GitHub only acts on it when the pull request merges
  into the repo's default branch; one that lands somewhere else first leaves
  the issue for a person to close.
- **Blocked:** stays open with `loop:blocked`. Fix the ticket (usually the
  "done means"), take `loop:blocked` off, put `loop-ready` back. The loop picks
  up where it left off, on its old `loop/issue-N` branch. For a clean start,
  delete that branch and its checkout under `~/.harness-loop/` first.
- **Not doing it:** close it as not planned, with one line saying why.

Never close an issue whose "done means" hasn't been checked.
