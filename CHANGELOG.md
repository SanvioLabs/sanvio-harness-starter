# What's new

Newest first. Each entry has a dated heading with a short name that never
changes, what it adds, the files it touched, and **Do:** what you need to do to
take it. Ask the agent "what's new" and `skills/whats-new/` reads this, and the
starter's copy, and tells you what you don't have yet.

Changing your own harness? Add an entry at the top in the same shape. Then
"what's new" works for your team too.

## 2026-10-07: What's new only names commands

`whats-new` no longer offers to merge the starter's changes for you. A copy
made with *Use this template* has no shared history, so it names the per-file
commands instead and stops.

**Files:** `skills/whats-new/SKILL.md`

**Do:** nothing.

## 2026-10-07: What's new

A release log, this file, and a skill that answers "what's new" from it,
including what the public starter has that your copy doesn't.

**Files:** `CHANGELOG.md`, `skills/whats-new/`, `AGENTS.md`,
`skills/review-pr/SKILL.md`, `skills/orientation/SKILL.md`, `README.md`,
`tests/test_changelog.py`, `tests/test_steering.py`

**Do:** nothing. From now on, ask "what's new" after the starter changes.

## 2026-10-07: Building, testing and deploying steering

Two on-demand steering files. `building-and-testing.md`: spec first, small
changes, tests that fail when the behaviour breaks, never weaken a test.
`deploying.md`: infrastructure as code, the deploy script first, staging
before production, a known rollback, and a human yes for every production
deploy. `project-setup.md` now points at both instead of repeating them.

**Files:** `steering/building-and-testing.md`, `steering/deploying.md`,
`steering/project-setup.md`, `steering/gates.md`, `AGENTS.md`,
`skills/learn/SKILL.md`

**Do:** nothing. Edit both to match how your team builds and ships.

## 2026-10-07: Gate guide

`steering/gates.md`: whether a check earns a gate, the six places one can run
(skill step, Claude guard, git hook, CI, required check, release step) and
what each one misses, and the question each phase gate asks. Orientation now
adds a new gate to CI as well as the hook.

**Files:** `steering/gates.md`, `gates/README.md`, `steering/operating.md`,
`skills/orientation/SKILL.md`, `skills/learn/SKILL.md`, `AGENTS.md`

**Do:** if you added a gate to the hook before this, add the same command,
with no file arguments, as a step in `.github/workflows/ci.yml`.

## 2026-10-07: Steering

Six light steering files in `steering/`: how the agent operates, how it
replies, what data may go to which tool, writing, project setup and model
choice. Three load every session, through `AGENTS.md` and `.kiro/steering/`.

**Files:** `steering/`, `.kiro/steering/`, `AGENTS.md`, `scripts/check_setup.py`,
`tests/test_steering.py`

**Do:** read the three that always load, and edit them to sound like you.

## 2026-10-07: The proposal job moved to examples/

The root is generic now. The proposal job (its skill, gate, data, template,
review brief and finished proposal) lives in `examples/proposal/`, and there's
one generic reviewer in `agents/reviewer.md` that takes a brief per job.

**Files:** `examples/proposal/`, `agents/reviewer.md`, `gates/README.md`,
`.githooks/pre-commit`, `.github/workflows/ci.yml`, `.claude/agents/`,
`AGENTS.md`, `scripts/check_setup.py`

**Do:** if you copied the starter before this, your proposal files are at the
old paths and block 2 of your hook points at the old gate. Keep your own
blocks, take block 2 from the starter, and run `python3 scripts/check_setup.py`.

## 2026-10-07: Your repos inside the harness, and two review skills

`projects/` for cloning your code repos into, so they work under the
harness's rules. `review-pr` and `review-tests`, a check for personal skills
that hide the repo's, and `HOW-IT-WORKS.md`.

**Files:** `projects/README.md`, `skills/review-pr/`, `skills/review-tests/`,
`CLAUDE.md`, `.ignore`, `.gitignore`, `HOW-IT-WORKS.md`, `scripts/check_setup.py`

**Do:** start the agent from the harness root, never from inside a project.
`projects/README.md` has why.

## 2026-10-07: Orientation, company record, guards, learn and CI

`/orientation` sets you up: checks the clone, maps where your company's data
lives, interviews you for a company record, and builds the five layers around
your job. Claude Code guards refuse credential files and ask before a
connector changes anything. `learn` writes a correction into the file that
governs it. CI runs the tests, the gate and the setup check.

**Files:** `skills/orientation/`, `skills/learn/`, `company/`,
`.claude/settings.json`, `.claude/hooks/`, `.github/workflows/ci.yml`,
`scripts/check_setup.py`, `AGENTS.md`

**Do:** run `git config core.hooksPath .githooks` if you haven't, then
`/orientation`.

## 2026-10-06: Starter skills list

`STARTER-SKILLS.md`: skills worth adding first, where they come from, and how
to make one your own.

**Files:** `STARTER-SKILLS.md`

**Do:** nothing. Read it before you install an outside skill.

## 2026-09-23: The five layers

The starter itself: instructions, a skill, a gate, a hook and a review agent,
each tagged `step-1` to `step-5`, plus `review-skill` and the four loops.

**Files:** everything

**Do:** `git diff step-1 step-2` shows what one layer adds.
