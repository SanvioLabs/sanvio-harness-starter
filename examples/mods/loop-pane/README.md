# Loop pane

[`scripts/loop.py`](../../../scripts/loop.py) works without you, which also means you can't see it
work. This mod opens a pane beside the conversation that shows it:

```
Running
tmux loop-starter: tmux attach -t loop-starter
[ Watch it ]
[ Copy attach command ]
1 waiting: #15

#14 Gate: an empty Role cell passes
building, round 2 of 5
tests failed (1), review FIX

#1 Gate: a fee row with 0 hours passes
pull request open
tests passed, review PASS
[ Copy pull request link ]

#9 README: link the loop section
blocked
tests passed, review FIX. still failing after 5 rounds, see .loop/issue-9/
```

It's a Claude Code mod, so it works in Claude Code only, and it was built and
tested on Claude Code 2.1.296. Codex and Kiro don't have mods.

## Open it

Type `/loop-pane`. Not `/loop`: that's Claude Code's own command for running a
prompt on a schedule.

In fullscreen, from 110 columns, the pane docks beside the conversation.
Narrower, it sits above the prompt. Close it with the `×` in its corner.

It loads by itself, the same way as the [harness lens](../harness-lens/): the harness's
[`.claude/settings.json`](../../../.claude/settings.json) turns it on. Don't see `/loop-pane`? Install it from
inside a session, at the root:

```
/plugin marketplace add ./
/plugin install loop-pane@sanvio-harness-starter
```

Or load it for one session with `claude --plugin-dir examples/mods/loop-pane`.

On a machine that already knew this marketplace from another copy of the
harness, the first session in a new copy can miss it: Claude Code installs
the enabled mods before it re-reads the marketplace. The second session has
it.

## Reading it

| Line | Shows |
|---|---|
| The first line | **Running** while a live loop holds its lock, **Stopping after this step** after `loop.py stop`, **Not running** otherwise. Red when the last run was killed: its lock is still there but its process isn't, and the next run replaces it |
| **tmux** | While a loop started in tmux is running, its session and the command that opens it, with a button that copies the command. `loop-control` starts the loop that way when tmux is installed |
| **Watch it** | On a Mac, opens a new Terminal window attached to that session, read-only: you see the loop work and can't type into it. Close the window and the loop keeps running. If the window can't open, it copies the read-only attach command instead. It shows only while the loop runs in tmux on macOS |
| **waiting** | Ready issues the loop will take next, lowest first |
| An issue | Its title, then what it's on (planning, building, checking, opening the pull request) with the round, or how it ended: a pull request, blocked, stopped or skipped |
| Under it | The last round's test and review results, and why it was blocked |

While the pane is open, an issue that reaches an end also pops up a short
notice, so you hear about it without reading the pane.

## What it doesn't do

It only reads. It never starts, stops or changes the loop: run
`python3 scripts/loop.py` for that. **Watch it** opens
`.loop/watch.command`, which `loop.py` writes when a run starts inside tmux
on macOS and removes when it ends; the window it opens is read-only. Every two seconds while the pane is open,
and not at all while it's closed, it reads `.loop/status.json`, which the loop
rewrites at every step, and checks `.loop/STOP` and `.loop/lock`, with
`kill -0` on the process the lock names.

It shows the loop of the harness the session started in: the nearest folder
at or above it with [`scripts/loop.py`](../../../scripts/loop.py).

## Changing it

[`hooks/logic.ts`](hooks/logic.ts) holds the decisions as plain functions, so they can be tested.
[`hooks/register.tsx`](hooks/register.tsx) reads the files and draws the pane. From
[`examples/mods/`](../):

```bash
claude plugin validate loop-pane
claude plugin test loop-pane
```

CI doesn't run these, because they need Claude Code installed.
