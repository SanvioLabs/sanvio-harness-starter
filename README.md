# Harness starter

A harness is everything around the model: the rules it reads, the procedures it
follows, the checks that stop it, and the other agents it hands work to. The
model is the engine. The harness is what makes it safe to leave running.

This repo is the smallest harness that still does the job. It drafts client
proposals, because a proposal is where the cheap mistakes live: a placeholder
left in, a rate somebody made up, a total that doesn't add up. None of those are
hard. All of them ship anyway when the process lives in your head.

It works with Claude Code, Codex and Kiro. Nothing in it is tied to one tool.

## Set up

```bash
git clone <this repo> && cd harness-starter
git config core.hooksPath .githooks
python3 gates/proposal_gate.py
```

**Don't skip the middle line.** Git won't run the hook in `.githooks/` unless
you point it there, and the setting doesn't travel with a clone. Skip it and
every check in the hook silently does nothing. That exact line was missing from
a real harness for months, and nobody noticed because nothing failed.

You need Python 3.9 or newer and no packages.

On Windows, clone with `git clone -c core.symlinks=true` from a terminal with
Developer Mode on, or the two links below arrive as plain text files. If they
do, `AGENTS.md` still works for every tool.

## The five layers, one step at a time

Each step is a tag. Check one out to see the harness as it stood at that point,
or diff two to see exactly what a layer adds.

| Tag | Adds | What it fixes |
|---|---|---|
| `step-0` | A rate card, a template, one finished proposal | Nothing yet. The agent guesses |
| `step-1` | `AGENTS.md`, the instructions file | The agent stops inventing rates and knows where things go |
| `step-2` | `skills/draft-proposal/`, a skill | Drafting becomes the same procedure every time, with a defined output |
| `step-3` | `gates/proposal_gate.py`, a gate | "Done" becomes something a script checks, not something the agent claims |
| `step-4` | `.githooks/pre-commit`, a hook | The gate runs whether anyone remembers it or not, and secrets can't be committed |
| `step-5` | `agents/proposal-reviewer.md`, a review agent | A second reader who reads like the client, and reports without editing |

```bash
git checkout step-2          # the harness after step 2
git diff step-2 step-3       # what the gate adds
git checkout main            # everything
```

`main` has all five layers, so the exercises have something to copy from.
Check out `step-0` to start where the talk started.

## One file, three tools

Each tool reads its instructions from a different place. So there's one real
file and the others point at it:

| Tool | Reads | Here |
|---|---|---|
| Codex | `AGENTS.md` | The real file |
| Claude Code | `CLAUDE.md` | One line: `@AGENTS.md` |
| Kiro | `.kiro/steering/` | A symlink to `AGENTS.md` |

Skills and agents work the same way: the real file lives in `skills/` or
`agents/`, and `AGENTS.md` names it so every tool can find it. Claude Code also
picks them up natively through `.claude/`.

A second copy of an instruction is worse than none. It drifts, and it still
reads as the rule.

## Rules versus enforcement

`AGENTS.md` is context. The agent reads it and usually follows it. The hook is
enforcement. It runs whatever the agent decided. Anything you'd hate to get
wrong belongs in the second one.

## Four loops that keep it working

The layers are what a harness is made of. The loops are how you run it. Each
one is small, and each one is the difference between a harness that works on
day one and a harness that still works in month six.

**1. Fix and recheck.** A check fails, you fix what it names, it runs again,
and nothing moves until it passes. Here that's the skill's last two steps and
the hook refusing a commit. The rule that makes it a loop: never edit the check
to make the work pass.

**2. A pass goes stale.** A check that passed yesterday says nothing about the
file you edited this morning. That's why the gate runs in the hook on every
commit, not once when someone remembers. In your job, anything that was
reviewed and then changed gets reviewed again.

**3. The flywheel.** Every stage ends at a gate, and the output of one turn is
the input to the next. A proposal becomes a signed scope, the scope becomes the
build, and the build's lessons change the next proposal. Keep each turn small
enough to finish.

**4. Mistake to rule.** When the agent gets something wrong, don't just fix the
output. Write the rule that stops it happening again, in the file that governs
it: `AGENTS.md`, a skill, or a gate if it has to hold. Mitchell Hashimoto calls
this harness engineering. A correction you only said out loud hasn't happened,
because the next session never heard it.

The fourth loop is the one that makes the others better. Every other file in
this repo exists because of it.

## Your turn

`EXERCISES.md` has the hands-on: swap the proposal job for one you actually do,
and build the same five layers around it.

## Licence

MIT. Take it, change it, ship it. See `LICENSE`.
