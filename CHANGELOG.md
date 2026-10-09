# What's new

Newest first. Each entry has a dated heading with a short name that never
changes, what it adds, the files it touched, and **Do:** what you need to do to
take it. Ask the agent "what's new" and [`skills/whats-new/`](skills/whats-new/) reads this, and the
starter's copy, and tells you what you don't have yet.

Changing your own harness? Anything noticeable gets an entry at the top in
the same shape ([`steering/operating.md`](steering/operating.md) says what counts). Then "what's new"
works for your team too.

## 2026-10-09: Harness lens

A Claude Code mod that draws one line above the prompt naming which layer just
acted: the steering read, the skill followed, the last gate and how it went, a
tool the guard refused, the reviewer. `/lens` lists everything the harness did
in the session. It only looks, and it shows only this harness's own skills and
agents. `/orientation` now offers it at the end, for Claude Code users.

**Files:** [`examples/mods/harness-lens/`](examples/mods/harness-lens/), [`skills/orientation/SKILL.md`](skills/orientation/SKILL.md), [`AGENTS.md`](AGENTS.md),
[`README.md`](README.md), [`tests/test_steering.py`](tests/test_steering.py) (the house-style check skips what git ignores, so the
types Claude Code lays into a loaded mod don't fail it)

**Do:** nothing. To try it, start Claude Code from the harness root with
`claude --plugin-dir examples/mods/harness-lens`.

## 2026-10-08: File names are links

Every file or folder a Markdown file names is now a link to it, so you can
click from the README, a skill or a steering file straight to what it means.
[`scripts/link_files.py`](scripts/link_files.py) does it for the whole repo and is safe to run again;
[`steering/operating.md`](steering/operating.md) says to keep doing it.

**Files:** every tracked `.md` file, [`scripts/link_files.py`](scripts/link_files.py),
[`tests/test_link_files.py`](tests/test_link_files.py), [`steering/operating.md`](steering/operating.md)

**Do:** run `python3 scripts/link_files.py` after editing your own Markdown.
Read the diff before committing: it skips mentions of another project's
file, but a name it can't tell apart is yours to check.

## 2026-10-08: Two sessions, one clone

`building-and-testing.md` now says to give a second agent session its own git
worktree, so two sessions never share a branch or a checkout. The README now
opens with what a harness is, for someone who has never seen one, and shows
what shapes a session (what the agent reads and can skip, and what checks it)
and where something new goes, in the order `learn` uses.

**Files:** [`steering/building-and-testing.md`](steering/building-and-testing.md), [`README.md`](README.md),
[`docs/what-is-a-harness.gif`](docs/what-is-a-harness.gif), [`docs/what-shapes-a-session.gif`](docs/what-shapes-a-session.gif),
[`docs/where-it-goes.gif`](docs/where-it-goes.gif)

**Do:** if you run two agents at once, start the second in a worktree.

## 2026-10-07: Running one harness across teams

[`HOW-IT-WORKS.md`](HOW-IT-WORKS.md) now says how strictness follows risk (a read-only project
against one that writes to something people use), how a change to the harness
travels from one person's mistake to everyone's `/whats-new`, and who owns
which part, with `CODEOWNERS` to make it hold.

**Files:** [`HOW-IT-WORKS.md`](HOW-IT-WORKS.md)

**Do:** nothing. If more than one person changes your harness, read "Who owns
what" and decide yours.

## 2026-10-07: CI for your own repos, and the deploy workflow

[`examples/ci/project-checks.yml`](examples/ci/project-checks.yml) is CI to copy into a repo in [`projects/`](projects/). It's
green on an empty repo and checks more as the repo grows. `deploying.md` has a
new section on the deploy workflow: one workflow with a caller per
environment, production started by hand with a typed confirmation, plan on
the pull request and apply only in the deploy, short-lived credentials.

**Files:** [`examples/ci/project-checks.yml`](examples/ci/project-checks.yml), [`steering/deploying.md`](steering/deploying.md),
[`steering/building-and-testing.md`](steering/building-and-testing.md), [`projects/README.md`](projects/README.md)

**Do:** copy [`examples/ci/project-checks.yml`](examples/ci/project-checks.yml) into each of your code repos as
`.github/workflows/checks.yml`, then require its jobs once they've run.

## 2026-10-07: Secret scan in CI

[`.github/workflows/secrets.yml`](.github/workflows/secrets.yml) runs gitleaks over the whole history on every
push to main and every pull request. The hook checks for secrets too, but
`--no-verify` skips the hook, and nothing skips this.

**Files:** [`.github/workflows/secrets.yml`](.github/workflows/secrets.yml), [`README.md`](README.md)

**Do:** take the file from the starter. After it has run once on a pull
request, add `secret scan` to your required checks. If it finds something,
rotate the secret first: deleting the commit doesn't un-leak it.

## 2026-10-07: CI should block, not just report

Nothing in your copy changes. CI runs the tests, the gate and the setup check
on every push, but until branch protection requires its checks, a red run
still lets the merge through. A check that blocks nothing is decoration.

**Files:** none. It's a setting on GitHub. [`steering/project-setup.md`](steering/project-setup.md) has the
steps.

**Do:** protect `main` and require CI's checks. Take the names from a run that
actually happened, not from the workflow file: unrenamed, they're
`checks (python 3.9)` and `checks (python 3.13)`. A wrong name waits forever
and blocks every pull request. Read the protection back to confirm it took.
Branch protection on a private repo needs a paid GitHub plan; on the free plan,
read every CI run before you merge.

## 2026-10-07: Example gate catches empty sections

The proposal example's gate now fails a required section that has a heading
and nothing under it: no text, only whitespace, or only an HTML comment. Each
one gets its own `empty section: <name>` line. An empty Fees section still
reports `no fee rows under Fees`, and a missing heading still reports only
`missing section: <name>`.

**Files:** [`examples/proposal/gates/proposal_gate.py`](examples/proposal/gates/proposal_gate.py), [`tests/test_gate.py`](tests/test_gate.py),
`CHANGELOG.md`

**Do:** nothing.

## 2026-10-07: What goes in the log

[`steering/operating.md`](steering/operating.md) now says which changes get an entry here: anything
new, anything that works differently, anything that moved, and anything you
have to act on. `whats-new` also stops at naming commands, and no longer
offers to merge the starter's changes, which can't work on a template copy.

**Files:** [`steering/operating.md`](steering/operating.md), [`AGENTS.md`](AGENTS.md), [`skills/whats-new/SKILL.md`](skills/whats-new/SKILL.md),
[`skills/review-pr/SKILL.md`](skills/review-pr/SKILL.md), `CHANGELOG.md`

**Do:** nothing. Add an entry when you change something noticeable.

## 2026-10-07: What's new

A release log, this file, and a skill that answers "what's new" from it,
including what the public starter has that your copy doesn't.

**Files:** `CHANGELOG.md`, [`skills/whats-new/`](skills/whats-new/), [`AGENTS.md`](AGENTS.md),
[`skills/review-pr/SKILL.md`](skills/review-pr/SKILL.md), [`skills/orientation/SKILL.md`](skills/orientation/SKILL.md), [`README.md`](README.md),
[`tests/test_changelog.py`](tests/test_changelog.py), [`tests/test_steering.py`](tests/test_steering.py)

**Do:** nothing. From now on, ask "what's new" after the starter changes.

## 2026-10-07: Building, testing and deploying steering

Two on-demand steering files. `building-and-testing.md`: spec first, small
changes, tests that fail when the behaviour breaks, never weaken a test.
`deploying.md`: infrastructure as code, the deploy script first, staging
before production, a known rollback, and a human yes for every production
deploy. `project-setup.md` now points at both instead of repeating them.

**Files:** [`steering/building-and-testing.md`](steering/building-and-testing.md), [`steering/deploying.md`](steering/deploying.md),
[`steering/project-setup.md`](steering/project-setup.md), [`steering/gates.md`](steering/gates.md), [`AGENTS.md`](AGENTS.md),
[`skills/learn/SKILL.md`](skills/learn/SKILL.md)

**Do:** nothing. Edit both to match how your team builds and ships.

## 2026-10-07: Gate guide

[`steering/gates.md`](steering/gates.md): whether a check earns a gate, the six places one can run
(skill step, Claude guard, git hook, CI, required check, release step) and
what each one misses, and the question each phase gate asks. Orientation now
adds a new gate to CI as well as the hook.

**Files:** [`steering/gates.md`](steering/gates.md), [`gates/README.md`](gates/README.md), [`steering/operating.md`](steering/operating.md),
[`skills/orientation/SKILL.md`](skills/orientation/SKILL.md), [`skills/learn/SKILL.md`](skills/learn/SKILL.md), [`AGENTS.md`](AGENTS.md)

**Do:** if you added a gate to the hook before this, add the same command,
with no file arguments, as a step in [`.github/workflows/ci.yml`](.github/workflows/ci.yml).

## 2026-10-07: Steering

Six light steering files in [`steering/`](steering/): how the agent operates, how it
replies, what data may go to which tool, writing, project setup and model
choice. Three load every session, through [`AGENTS.md`](AGENTS.md) and [`.kiro/steering/`](.kiro/steering/).

**Files:** [`steering/`](steering/), [`.kiro/steering/`](.kiro/steering/), [`AGENTS.md`](AGENTS.md), [`scripts/check_setup.py`](scripts/check_setup.py),
[`tests/test_steering.py`](tests/test_steering.py)

**Do:** read the three that always load, and edit them to sound like you.

## 2026-10-07: The proposal job moved to examples/

The root is generic now. The proposal job (its skill, gate, data, template,
review brief and finished proposal) lives in [`examples/proposal/`](examples/proposal/), and there's
one generic reviewer in [`agents/reviewer.md`](agents/reviewer.md) that takes a brief per job.

**Files:** [`examples/proposal/`](examples/proposal/), [`agents/reviewer.md`](agents/reviewer.md), [`gates/README.md`](gates/README.md),
[`.githooks/pre-commit`](.githooks/pre-commit), [`.github/workflows/ci.yml`](.github/workflows/ci.yml), [`.claude/agents/`](.claude/agents/),
[`AGENTS.md`](AGENTS.md), [`scripts/check_setup.py`](scripts/check_setup.py)

**Do:** if you copied the starter before this, your proposal files are at the
old paths and block 2 of your hook points at the old gate. Keep your own
blocks, take block 2 from the starter, and run `python3 scripts/check_setup.py`.

## 2026-10-07: Your repos inside the harness, and two review skills

[`projects/`](projects/) for cloning your code repos into, so they work under the
harness's rules. `review-pr` and `review-tests`, a check for personal skills
that hide the repo's, and [`HOW-IT-WORKS.md`](HOW-IT-WORKS.md).

**Files:** [`projects/README.md`](projects/README.md), [`skills/review-pr/`](skills/review-pr/), [`skills/review-tests/`](skills/review-tests/),
[`CLAUDE.md`](CLAUDE.md), [`.ignore`](.ignore), [`.gitignore`](.gitignore), [`HOW-IT-WORKS.md`](HOW-IT-WORKS.md), [`scripts/check_setup.py`](scripts/check_setup.py)

**Do:** start the agent from the harness root, never from inside a project.
[`projects/README.md`](projects/README.md) has why.

## 2026-10-07: Orientation, company record, guards, learn and CI

`/orientation` sets you up: checks the clone, maps where your company's data
lives, interviews you for a company record, and builds the five layers around
your job. Claude Code guards refuse credential files and ask before a
connector changes anything. `learn` writes a correction into the file that
governs it. CI runs the tests, the gate and the setup check.

**Files:** [`skills/orientation/`](skills/orientation/), [`skills/learn/`](skills/learn/), [`company/`](company/),
[`.claude/settings.json`](.claude/settings.json), [`.claude/hooks/`](.claude/hooks/), [`.github/workflows/ci.yml`](.github/workflows/ci.yml),
[`scripts/check_setup.py`](scripts/check_setup.py), [`AGENTS.md`](AGENTS.md)

**Do:** run `git config core.hooksPath .githooks` if you haven't, then
`/orientation`.

## 2026-10-06: Starter skills list

[`STARTER-SKILLS.md`](STARTER-SKILLS.md): skills worth adding first, where they come from, and how
to make one your own.

**Files:** [`STARTER-SKILLS.md`](STARTER-SKILLS.md)

**Do:** nothing. Read it before you install an outside skill.

## 2026-09-23: The five layers

The starter itself: instructions, a skill, a gate, a hook and a review agent,
each tagged `step-1` to `step-5`, plus `review-skill` and the four loops.

**Files:** everything

**Do:** `git diff step-1 step-2` shows what one layer adds.
