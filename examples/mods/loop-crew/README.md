# Loop crew

The [loop pane](../loop-pane/) tells you what the loop is doing in words. This mod shows it: a pane
with one small figure for each issue being worked on, acting out the step that issue is on.

| Step | The figure | The words |
|---|---|---|
| `SHAPE` | At a drafting board | `planning` |
| `TEST` | Writing on a board | `writing tests` |
| `BUILD` | Swinging a hammer | `building` |
| `VALIDATE` | Holding up a magnifying glass | `checking` |
| `SCALE` | Carrying a box | `opening the pull request` |
| No step yet | Standing still | `starting` |
| Any other step | Standing still | The step, lowercased |

Beside each figure are its issue number and title, its step's words and, past round 0, its round.

It's a Claude Code mod, so it works in Claude Code only. It hasn't yet been tried on any surface.
It's built from the types and tested with `claude plugin test`. The animation on the mobile app is
expected but untried: the app draws an Svg in a web view, and nobody has checked that SMIL runs there.

## Turn it on

It loads by itself: the harness's [`.claude/settings.json`](../../../.claude/settings.json) turns it on. If `/loop-crew`
isn't there, install it from inside a session, at the root, or run `/reload-plugins`:

```
/plugin marketplace add ./
/plugin install loop-crew@sanvio-harness-starter
```

A change to what the mod does raises `version` in its [`.claude-plugin/plugin.json`](.claude-plugin/plugin.json).

To turn it off just for you:

```bash
claude plugin disable loop-crew@sanvio-harness-starter --scope local
```

## Using it

| Type | Does |
|---|---|
| `/loop-crew` | Opens the pane on the harness's loop, titled `Loop crew` |
| `/loop-crew <name>` | Opens it on the project's loop in `.loop/projects/<name>/`, titled `Loop crew: <name>` |
| The same again | Closes the pane |
| Another loop's name, or no name while a project is shown | Switches the open pane to that loop |

A name must be exactly a folder under `.loop/projects/`. Anything else, `../x` included, answers
`No loop for <name> under .loop/projects/.` and changes nothing.

## What the pane says

Checked in this order:

| The pane says | Means |
|---|---|
| `No loop has run here yet.` | There's no `status.json`, or it can't be read |
| `The loop isn't running.` | There's no lock, or its holder has gone. Rows left at `working` by a killed run draw no figures |
| `Nothing being built right now.` | The loop is running with no issue at `working` |
| The figures | One for each issue at `working`, in number order |

The terminal shows the figures that fit the pane, at 9 rows each, then `and <n> more`. It shows at
least one. Other surfaces show them all.

## What it doesn't do

It only reads. Every 2 seconds while the pane is open it reads the shown loop's `status.json` and
`lock`, and it stops once the pane closes. The one process it runs is `kill -0 <pid>`, to check the
lock's holder. It never writes a file, never runs [`scripts/loop.py`](../../../scripts/loop.py) or `gh`, and spends no model
tokens. Controls such as stop stay in the [loop pane](../loop-pane/). It shows one loop at a time, and
doesn't show issues that ended.

## How the animation works

Each act lives once in [`hooks/logic.ts`](hooks/logic.ts): two to four frames of 16 by 16 pixels, each pixel a key in the
act's palette, with `.` a fixed dark backdrop.

- **Terminal:** each figure is a `Raster` of half-block characters. A 250 ms timer paints its next frame
  with `$.ui.blit`, so the pane isn't redrawn for a frame, and a redraw keeps each figure on its current
  frame. A blit that fails is ignored.
- **Desktop, VS Code and mobile:** each figure is one `Svg` holding every frame, shown in turn by SMIL
  every 250 ms. No timer runs there. Where SMIL doesn't run, the first frame stands still.

## Changing it

[`hooks/logic.ts`](hooks/logic.ts) holds the acts and decisions as plain functions, so they can be tested.
[`hooks/register.tsx`](hooks/register.tsx) reads the files and draws the pane. From [`examples/mods/`](../):

```bash
claude plugin validate loop-crew
claude plugin test loop-crew
```

`python3 -m unittest discover -s tests`, and so the loop, runs these wherever Claude Code is installed. CI doesn't install Claude Code, so it skips them.
