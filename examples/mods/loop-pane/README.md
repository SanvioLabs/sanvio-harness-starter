# Loop pane

[`scripts/loop.py`](../../../scripts/loop.py) works without you, which also means you can't see it
work. This mod opens a pane beside the conversation that shows it:

```
starter                                ● Running 2 · up 1h 04m

[ Watch it ] [ Copy attach command ]
──────────────────────────────────────────────────────────────
[ Queue 1 ] [ Active 2 ] [ Finished 4 ]

● #14 Gate: an empty Role cell passes
  started 14:22 · running 6m 12s · 840k tokens · ~$3.40
  building, round 2 of 5
  tests failed (1), review FIX

  [ Watch ]

● #15 Proposal: stamp the phase
  started 14:27 · running 1m 03s · 95k tokens · ~$0.41
  planning


  [ Watch ]
```

The top line names the repo, and on the right whether the loop is running, how
many jobs it's on and how long it has been up. In a narrow pane the state drops
to the second line; the header always takes two, so nothing under it moves.
While the loop is on a job, the dot before **Running** pulses with the jobs' dots.

The dot beside a job the loop is on pulses, bright then dim, about once a
second, and the clock beside it counts up. If the loop dies mid-step, the dot
stops and turns red with the row. A job that has ended keeps a still dot in its
result's colour, green for a pull request and red for a block, and says how
long it took. A job started by a loop.py older than this one has no clock.

After the time come the job's tokens and, beside them, its cost, totalled over
every run of the issue. The cost is Claude Code's estimate at API prices, not a
bill. A job with no tokens recorded, or from a loop.py older than #179, shows
neither, and in a narrow pane the usage is the part that's cut.

An issue on the **Queue** tab that depends on one still open says so:

```
#16 Gate: check the fee total · waiting on #14, #15
```

Pick **Finished** and it lists the last day's jobs, three at a time:

```
▲ 1 more
● #1 Gate: a fee row with 0 hours passes
  started 09:10 · took 18m 03s · 1.2M tokens · ~$3.40
  pull request open
  tests passed, review PASS
  [ Copy pull request link ]

● #9 README: link the loop section
  started 08:02 · took 1h 04m
  blocked
  tests passed, review FIX. still failing after 5 rounds, see .loop/issue-9/

● #7 Gate: a blank fee cell passes
  started 07:41 · took 12m 40s
  pull request open
  tests passed, review PASS
  [ Copy pull request link ]
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
| The header | The repo's folder on the left. On the right, **Running** while a live loop holds its lock and works a job (**Running 2** for two), **Idle** in dim green while it holds the lock with nothing to work, **Stopping after this step** after `loop.py stop`, **Not running** otherwise, with how long a live loop has been up. Red when the last run was killed: its lock is still there but its process isn't, and the next run replaces it. A loop.py older than this one writes no start, so no uptime |
| **Copy attach command** | While a loop started in tmux is running, copies the command that opens its session. `loop-control` starts the loop that way when tmux is installed |
| **Watch it** | On a Mac, opens a new Terminal window attached to that session, read-only: you see the loop work and can't type into it. Close the window and the loop keeps running. If the window can't open, it copies the read-only attach command instead. It shows only while the loop runs in tmux on macOS |
| **Queue** | Ready issues the loop will take next, lowest first. One that depends on an open issue says **waiting on** and which |
| **Active** | Issues being worked: what each is on (planning, building, checking, opening the pull request) with the round. One left part way by a run that stopped shows where it was left. In tmux, **Watch** opens a read-only Terminal window on that issue's own `issue-N` window, or copies its attach command when it can't. tmux has one current window per session, so it also switches any other window attached to the session, **Watch it**'s included |
| **Finished** | Issues that reached an end in the last 24 hours: a pull request, blocked, stopped or skipped. Older ones drop off; `.loop/status.json` still has them |
| Under an issue | The last round's test and review results, and why it was blocked |

Each tab shows its count. The pane opens on **Active** when something is
being worked, else **Queue**, else **Finished**, and stays on the tab you pick.
A tab shows three jobs at a time. Scroll over the pane, or press the
**▲ more** and **▼ more** lines, to move through the rest; the header and the
tabs stay put.

While the pane is open, an issue that reaches an end also pops up a short
notice, so you hear about it without reading the pane.

## What it doesn't do

It only reads. It never starts, stops or changes the loop: run
`python3 scripts/loop.py` for that. **Watch it** opens
`.loop/watch.command`, which `loop.py` writes when a run starts inside tmux
on macOS and removes when it ends, and a job's **Watch** opens
`.loop/issue-N/watch.command`, written when its window opens and removed when it
closes; the windows they open are read-only. Every two seconds while the pane is open,
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

`python3 -m unittest discover -s tests`, and so the loop, runs these wherever Claude Code is installed. CI doesn't install Claude Code, so it skips them.
