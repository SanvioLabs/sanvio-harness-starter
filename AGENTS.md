# How to work in this repo

This is a harness: the rules, skills, gates and agents you work inside. You do
the work. A human reviews it, and a human sends, merges or pays.

## Steering

Standing guidance, one file per topic, in `steering/`. These three apply to
every session. Claude Code loads them through the lines below and Kiro through
`.kiro/steering/`. In any other tool, read them before you start:

@steering/operating.md
@steering/response-style.md
@steering/data-and-tools.md

Read these when their moment comes:

| File | Read when |
|---|---|
| `steering/writing.md` | Writing anything a person outside the company will read |
| `steering/project-setup.md` | Starting a new repo or project |
| `steering/model-selection.md` | Deciding which model runs what, or handing work to a subagent |

Add your own the same way: one topic per file, and a row here saying when it
applies. Where a steering file and this file disagree, this file wins, and you
say so.

## Who you work for

Before any company work, read `company/COMPANY.md` and `company/DATA.md` if
they exist. The first says who the company is and what it won't do. The second
says where its data lives and how you reach it. Never invent a fact about the
company: if a section is empty or a file is missing, ask, or suggest
`/orientation`. Both files are gitignored, so never quote them into a tracked
file.

## Where you start

Sessions start at the harness root, the folder this file is in. Code repos are
cloned into `projects/` and worked on from here. If your working directory is
below the root, say so before any work: the harness's skills, agents and
guards didn't load, so the rules below are unenforced. Ask the person to
restart from the root. `projects/README.md` has why.

A project's own `AGENTS.md` or `CLAUDE.md` adds to these rules for that
project. Where the two disagree, these rules win and you say so.

## Rules

- Every input comes from a named source: a file, a connector in
  `company/DATA.md`, or the person in this session. Never invent one. If you
  don't know something, ask. Don't guess, and don't fill it with something
  plausible.
- Leave no `{{placeholder}}`, `TODO` or `TBD` in finished work.
- Never send, email or publish anything. A connector that can send, edit,
  delete or share does so only when a human says yes to that one call.
- Never read, write or print a credential, a key or a `.env` file.
  `steering/data-and-tools.md` has the detail.

## Skills

Skills are procedures. When a request matches one, read it and follow its
steps in order.

| Skill | Use when |
|---|---|
| `skills/review-pr/SKILL.md` | Asked to review a pull request, a branch or a diff, or whether a change is ready to merge |
| `skills/review-tests/SKILL.md` | Asked whether tests are any good or would catch a regression, or after tests were written by an agent |
| `skills/review-skill/SKILL.md` | Asked to install, add, try or review a skill from outside this repo |
| `skills/learn/SKILL.md` | The agent got something wrong and the person wants it to stick: "learn from that", "don't do that again", "make that a rule" |
| `skills/orientation/SKILL.md` | Someone runs `/orientation`, is new here, asks how to use this, says "get me started", or wants it set up for their own job and their company's data |

## Done means the gate passes

Work that has a gate is done when its gate passes. Each job's skill names its
gate and the command that runs it. Run it and show the output. Never say work
is done, ready or finished while its gate fails, and never edit a gate to make
work pass.

The gates also run in `.githooks/pre-commit`, along with a check for secrets.
If a commit is blocked, fix what it names. Never commit with `--no-verify`.

In Claude Code, `.claude/hooks/guard.py` also runs before every tool call: it
refuses credential files and asks the human before any connector changes
something. If it refuses, don't look for another way to do the same thing. Say
what you needed and ask.

## Agents

After the gate passes, hand the work to a reviewer before a human sees it.

| Agent | Does |
|---|---|
| `agents/reviewer.md` | Reads finished work as the person who receives it would and reports what's unclear or over-promised, using the job's brief if it has one. Never edits |

In Claude Code it runs as the `reviewer` subagent. In other tools, run it as a
separate session with that file as its instructions.

## Examples

`examples/` holds worked jobs to read and copy. Before working in one, read its
`README.md`: it carries that job's rules, and they apply on top of these.

| Example | Shows |
|---|---|
| `examples/proposal/` | Drafting a client proposal: inputs, rules, a skill (`skills/draft-proposal/SKILL.md` inside it), a gate, the hook block and a review brief |
