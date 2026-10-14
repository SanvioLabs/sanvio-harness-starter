# What's new

Newest first. Each entry has a dated heading with a short name that never
changes, what it adds, the files it touched, and **Do:** what you need to do to
take it. Ask the agent "what's new" and [`skills/whats-new/`](skills/whats-new/) reads this, and the
starter's copy, and tells you what you don't have yet.

Changing your own harness? Any noticeable change gets an entry at the top, in
the same change, not later. Then "what's new" works for your team too.
Noticeable means:

- **Something new:** a skill, a steering file, a gate, a hook, an agent, a
  check, a folder people are meant to use
- **Something that works differently:** a skill or gate that now does more,
  less or something else, a rule that got stricter or looser
- **Something that moved:** a file renamed or relocated, so old paths break
- **Anything with a Do:** if someone has to run a command or edit a file to
  take it, it needs an entry whatever its size

Typo fixes, rewording, tests on their own and tidying inside a file don't. The
test: would someone who copied the harness last week want to know, or need to
act? If you're unsure, write the entry.

One entry per change someone would name, not per commit: three files that add
one feature are one entry. The heading is `## YYYY-MM-DD: Name`, and the name
never changes once it's written, because copies are compared by it. Under it:
what it adds in a sentence or two, the files, and a **Do:** line ("nothing" is
fine).

## 2026-10-14: Secret scan reads every staged name

The pre-commit secret scan now checks files whose names have a space in them
and files renamed in the commit. Before, a name like `a b.txt` was split into
two names that didn't exist, and a renamed file was skipped, so a key in
either got through. Accented names come through as written. Names holding a
newline, a quote, a backslash or a control character are still not handled.

Files: [`.githooks/pre-commit`](.githooks/pre-commit), [`tests/test_pre_commit.py`](tests/test_pre_commit.py)

**Do:** nothing.

## 2026-10-14: Tighter guard on the security reviewer and on credential names

[`.claude/hooks/guard.py`](.claude/hooks/guard.py) closes gaps the security reviewer found in its own
fence. Git and `gitleaks` don't run in a repo whose `.git/config` can make a
read run a command (a pager, an external or textconv diff, a filesystem
monitor, an include), which a repo handed over as an archive can carry.
`git log` and `git show` can't print old file contents (`show` needs
`--stat` or `--name-only`, and no `rev:path`), and `gitleaks` takes only a
bare `--redact`. For every agent, `git show HEAD:.env` now counts as reading
a credential. [`.githooks/pre-commit`](.githooks/pre-commit) blocks `.env.*` and `id_rsa*` in a folder
too, not only at the root.

Files: [`.claude/hooks/guard.py`](.claude/hooks/guard.py), [`tests/test_agent_hooks.py`](tests/test_agent_hooks.py), [`.githooks/pre-commit`](.githooks/pre-commit),
[`tests/test_pre_commit.py`](tests/test_pre_commit.py), [`agents/security-reviewer.md`](agents/security-reviewer.md)

**Do:** nothing.

## 2026-10-14: The loop checks whose issue it builds from

[`scripts/loop.py`](scripts/loop.py) now reads each issue fresh before it takes it, and builds
from an issue written outside the repo's collaborators only if nothing in it
changed after it was labelled `loop-ready` and it hides no HTML comment.
Otherwise it blocks the issue and says why. The planner and the reviewer run
in the build checkout with read tools only, commits run with git hooks off,
and the test command runs without tokens, keys or passwords in its
environment. [`examples/ci/loop.yml`](examples/ci/loop.yml) leaves no token in `.git/config`, pushes
through `gh auth setup-git`, and pins the agent CLI.

Files: [`scripts/loop.py`](scripts/loop.py), [`tests/test_loop.py`](tests/test_loop.py), [`examples/ci/loop.yml`](examples/ci/loop.yml),
[`tests/test_ci_example.py`](tests/test_ci_example.py), [`HOW-IT-WORKS.md`](HOW-IT-WORKS.md)

**Do:** if you copied [`examples/ci/loop.yml`](examples/ci/loop.yml), copy it again. If your test
command needs a token or key from the environment, it no longer gets one:
have the tests read a test-only value instead.

## 2026-10-14: The security reviewer runs pip-audit and bandit

On a Python project, the `security-reviewer` agent now runs `pip-audit` on
each requirements file, with `--disable-pip` so nothing installs, and
`bandit` on the code. It treats bandit's hits as leads to trace, not as
findings. Either one that isn't installed is listed under Not checked.

Files: [`agents/security-reviewer.md`](agents/security-reviewer.md)

**Do:** `brew install pip-audit bandit`, or `pipx install pip-audit bandit`,
if you want them.

## 2026-10-14: The security reviewer runs audits

The `security-reviewer` agent now has a shell, for audits only. It runs
`osv-scanner` over the lock files, `npm audit`, `pip-audit`, `trivy fs`,
`govulncheck`, `bundle-audit` or `bandit` where they fit, and `gitleaks
--redact` over the history, and reports findings from them rather than
naming them for you to run. [`.claude/hooks/guard.py`](.claude/hooks/guard.py) holds its shell to
that list plus git reads: one command at a time, no pipes, nothing that
installs, builds or runs the code under review. Any other command it tries is
refused. The audits send package names and versions to their advisory
services.

Files: [`.claude/hooks/guard.py`](.claude/hooks/guard.py), [`tests/test_agent_hooks.py`](tests/test_agent_hooks.py), [`agents/security-reviewer.md`](agents/security-reviewer.md),
[`.claude/agents/security-reviewer.md`](.claude/agents/security-reviewer.md), [`AGENTS.md`](AGENTS.md), [`README.md`](README.md)

**Do:** install the scanners you want it to use. `osv-scanner` and `gitleaks`
cover most projects (`brew install osv-scanner gitleaks`). One that's missing
is listed under Not checked.

## 2026-10-14: A security reviewer

A second agent, `security-reviewer`, reads code the way an attacker would and
reports what could be exploited. Each Critical or High finding carries its
attack path from entry point to payoff, and the report opens with a READY or
NOT-READY verdict. It only reads and has no shell, so text planted in the code
it reviews can't make it run anything. It names the dependency audit and the
history scan for a person to run instead. `review-pr` hands it changes that
touch auth, input handling, secrets, infrastructure or dependencies.

Files: [`agents/security-reviewer.md`](agents/security-reviewer.md), [`.claude/agents/security-reviewer.md`](.claude/agents/security-reviewer.md),
[`AGENTS.md`](AGENTS.md), [`skills/review-pr/SKILL.md`](skills/review-pr/SKILL.md), [`tests/test_steering.py`](tests/test_steering.py)

**Do:** nothing. Ask for a security review, or run the `security-reviewer`
agent by name.

## 2026-10-14: Loop pane tabs

The loop pane (0.4.0) splits its list into **Queue**, **Active** and
**Finished** tabs, each with its count, and shows three jobs at a time:
scroll over the pane, or press the more lines, for the rest. **Finished**
keeps only the last 24 hours, so a pull request the loop opened days ago no
longer reads as open.

Files: [`examples/mods/loop-pane/`](examples/mods/loop-pane/)

**Do:** nothing. It arrives with your next session.

## 2026-10-14: Loop pane opens a window on the loop

On a Mac, the loop pane (0.3.0) has a **Watch it** button while the loop runs
in tmux. It opens a new Terminal window attached to the loop's session,
read-only, so you watch without typing into it; closing the window leaves the
loop running. [`scripts/loop.py`](scripts/loop.py) writes `.loop/watch.command` for it when a run
starts inside tmux on macOS, and removes it when the run ends. Elsewhere the
pane copies the attach command as before. The pane also stops reading the
loop's files once it's closed, which it was meant to and didn't.

Files: [`scripts/loop.py`](scripts/loop.py), [`tests/test_loop.py`](tests/test_loop.py), [`examples/mods/loop-pane/`](examples/mods/loop-pane/),
[`HOW-IT-WORKS.md`](HOW-IT-WORKS.md), [`AGENTS.md`](AGENTS.md)

**Do:** nothing. The button arrives with your next session, from the next
loop run started in tmux.

## 2026-10-13: Standup reads only cleared sources

[`skills/standup/`](skills/standup/) reads a calendar, email or tracker only when `company/DATA.md` clears it, as [`AGENTS.md`](AGENTS.md)
already requires. A connector being there isn't enough.

Files: [`skills/standup/SKILL.md`](skills/standup/SKILL.md), [`tests/test_skills.py`](tests/test_skills.py)

**Do:** nothing. To include your calendar or email, run `/orientation` so `company/DATA.md` lists them.

## 2026-10-13: What's new lists every entry

[`skills/whats-new/`](skills/whats-new/) makes its list with a command and gives every entry on it, with the count. "Since a date" includes that day.

Files: [`skills/whats-new/SKILL.md`](skills/whats-new/SKILL.md), [`tests/test_changelog.py`](tests/test_changelog.py)

**Do:** nothing.

## 2026-10-13: The PR review workflow runs restricted

[`examples/ci/review-pr.yml`](examples/ci/review-pr.yml) runs the agent in Claude Code's restricted mode: read tools only, confined
to the checkout, with the diff in its prompt. That replaces the allow and deny lists.

Files: [`examples/ci/review-pr.yml`](examples/ci/review-pr.yml), [`tests/test_review_pr_workflow.py`](tests/test_review_pr_workflow.py)

**Do:** copied it already? Copy it again.

## 2026-10-13: loop.py review

`python3 scripts/loop.py review` watches the open pull requests that ask for
your review (`review_query`, by default `review-requested:@me`), has a fresh
`reader_agent` review each new head commit with [`skills/review-pr/`](skills/review-pr/), and posts the report as one
comment per pull request, edited in place on later commits. A commit is reviewed
once, the agent can read the checkout and nothing else, and it never
approves, merges or pushes. It shares the loop's lock, log, status file and
stop file.

Files: [`scripts/loop.py`](scripts/loop.py), [`tests/test_loop.py`](tests/test_loop.py), [`HOW-IT-WORKS.md`](HOW-IT-WORKS.md), [`skills/loop-control/SKILL.md`](skills/loop-control/SKILL.md)

**Do:** nothing, or start `loop.py review` on the machine the loop runs on, in a clone of its own if `run` is working the first.

## 2026-10-13: Where a change lives

[`HOW-IT-WORKS.md`](HOW-IT-WORKS.md) says which changes reach the team and which stay on your machine, and why a
skill kept in both this repo and `~/.claude/skills/` runs differently for you than for everyone else.

Files: [`HOW-IT-WORKS.md`](HOW-IT-WORKS.md)

**Do:** nothing.

## 2026-10-13: The PR review workflow runs

[`examples/ci/review-pr.yml`](examples/ci/review-pr.yml) failed on every run: the CLI refuses Grep and Glob path rules. It now
denies `/proc` with one Read rule, pins the CLI, prints why a run failed, and says the key must be scoped to a workspace.

Files: [`examples/ci/review-pr.yml`](examples/ci/review-pr.yml), [`tests/test_review_pr_workflow.py`](tests/test_review_pr_workflow.py)

**Do:** copied it already? Copy it again.

## 2026-10-13: A standup skill

[`skills/standup/`](skills/standup/) gives you one morning read of what's on you, from GitHub, the
loop and any calendar, email or tracker your session reaches, then asks about
each item and suggests an order for the day. It reads only and changes nothing.

Files: [`skills/standup/SKILL.md`](skills/standup/SKILL.md), [`AGENTS.md`](AGENTS.md), [`README.md`](README.md), [`STARTER-SKILLS.md`](STARTER-SKILLS.md), [`tests/test_skills.py`](tests/test_skills.py)

**Do:** nothing; ask for a standup in a new session.

## 2026-10-13: The loop off your laptop

"The loop" in [`HOW-IT-WORKS.md`](HOW-IT-WORKS.md) has a subsection, *Off your laptop*: where the loop can run
besides your terminal, what each place costs, and the limits of GitHub Actions.
[`examples/ci/loop.yml`](examples/ci/loop.yml) runs one pass there on a schedule or on demand.

Files: [`HOW-IT-WORKS.md`](HOW-IT-WORKS.md), [`examples/ci/loop.yml`](examples/ci/loop.yml), [`tests/test_ci_example.py`](tests/test_ci_example.py)

**Do:** to use it, copy it into [`.github/workflows/`](.github/workflows/) and add the secret it names,
`ANTHROPIC_API_KEY`.

## 2026-10-13: Review every pull request in CI

[`examples/ci/review-pr.yml`](examples/ci/review-pr.yml) is a GitHub Actions workflow that runs the
`review-pr` skill on every pull request and posts its report as one comment. It
runs on `pull_request` only, skips forks with a notice, and gives the agent no
GitHub token.

Files: [`examples/ci/review-pr.yml`](examples/ci/review-pr.yml), [`tests/test_review_pr_workflow.py`](tests/test_review_pr_workflow.py),
[`skills/review-pr/SKILL.md`](skills/review-pr/SKILL.md)

**Do:** to use it, copy it into [`.github/workflows/`](.github/workflows/) and add the secret it
names, `ANTHROPIC_API_KEY`, as a repository secret.

## 2026-10-13: The loop, animated

"The loop" in [`HOW-IT-WORKS.md`](HOW-IT-WORKS.md) has an animation after its step table,
[`docs/one-issue-through-the-loop.gif`](docs/one-issue-through-the-loop.gif): one issue through Discover, Shape, Build and
Validate, a FIX round back to Build, then a pull request the loop doesn't
merge. The log lines are in the format [`scripts/loop.py`](scripts/loop.py) writes.

Files: [`HOW-IT-WORKS.md`](HOW-IT-WORKS.md), [`docs/one-issue-through-the-loop.gif`](docs/one-issue-through-the-loop.gif)

**Do:** nothing.

## 2026-10-13: The README explains gates

[`README.md`](README.md) has a new section, *Gates: done is a script's call*: what a gate
is, the three places one runs and what each catches, when a check earns one,
and how a job's gate differs from the gate at the end of a phase. An
animation, [`docs/where-a-gate-runs.gif`](docs/where-a-gate-runs.gif), shows one gate file catching three
different mistakes in three places.

Files: [`README.md`](README.md), [`docs/where-a-gate-runs.gif`](docs/where-a-gate-runs.gif)

**Do:** nothing.

## 2026-10-12: link_files leaves . plain

[`scripts/link_files.py`](scripts/link_files.py) no longer turns a backticked `.` or `./` into a link
to the file's own folder. Below the root it used to; at the root it never did.
Named folders still link as before.

Files: [`scripts/link_files.py`](scripts/link_files.py), [`tests/test_link_files.py`](tests/test_link_files.py)

**Do:** nothing.

## 2026-10-12: loop-control starts the loop in tmux

When tmux is installed, [`skills/loop-control/`](skills/loop-control/) starts the loop in a tmux
session named after the clone's folder, instead of in the background of the
conversation. It keeps running after the conversation ends, and
`tmux attach -t loop-<folder>` opens it to watch; `Ctrl-b d` leaves it
running. Without tmux it starts in the background as before.
[`scripts/loop.py`](scripts/loop.py), run inside tmux, logs a `START` line with the session name
and `tmux attach -t <name>`, and writes the name to `tmux` in
`.loop/status.json` while it runs. The loop pane (0.2.0) shows it under its
first line, with a button that copies the attach command.

Files: [`skills/loop-control/SKILL.md`](skills/loop-control/SKILL.md), [`scripts/loop.py`](scripts/loop.py), [`tests/test_loop.py`](tests/test_loop.py),
[`examples/mods/loop-pane/`](examples/mods/loop-pane/), [`HOW-IT-WORKS.md`](HOW-IT-WORKS.md)

**Do:** install tmux if you want to watch the loop this way. The pane's new
line arrives with your next session.

## 2026-10-12: Tickets use Stelliad's sections

The issue template, [`steering/tickets.md`](steering/tickets.md) and the `loop-control` readiness
check now use the sections of Stelliad's Ticket Authoring Standard: Objective,
Why, Acceptance Criteria (flat checkboxes), Scope with In and Out, and Risk,
plus Verification, Context, Dependencies or References when they carry
something. `stelliad:create-ticket` writes this shape and
`stelliad:review-ticket` grades it; its checker blocked every ticket in the old
What and why / Done means shape. The loop's own rules stay on top: at least
one criterion is proved by a test the loop's test command runs, and a ticket
with High or Critical risk, a Human Approval section or an open dependency
isn't loop-ready. The loop's comment on a
blocked issue now says to fix the acceptance criteria.

Files: [`.github/ISSUE_TEMPLATE/loop-task.md`](.github/ISSUE_TEMPLATE/loop-task.md), [`steering/tickets.md`](steering/tickets.md),
[`skills/loop-control/SKILL.md`](skills/loop-control/SKILL.md), [`scripts/loop.py`](scripts/loop.py), [`tests/test_tickets.py`](tests/test_tickets.py)

**Do:** rewrite open tickets in the new shape before you label them
`loop-ready`: `loop-control` now wants `stelliad:review-ticket` to say READY,
and the checker blocks the old shape. Tickets already labelled still run, since
the loop reads the whole issue body.

## 2026-10-12: CI runs the link check

[`.github/workflows/ci.yml`](.github/workflows/ci.yml) now runs `python3 scripts/link_files.py --check`, so
a pull request that names a tracked file in its Markdown without linking it
fails CI instead of merging. It's checked against what git tracks, so a file
added in the same change counts.

Files: [`.github/workflows/ci.yml`](.github/workflows/ci.yml), [`README.md`](README.md)

**Do:** run `python3 scripts/link_files.py` before you push if you've
written file names into Markdown. It adds the links for you.

## 2026-10-12: Stelliad comes switched on

[`.claude/settings.json`](.claude/settings.json) now names the public Stelliad marketplace and switches
its plugin on, so trusting the folder switches it on, with no separate prompt.
Its skills run as `stelliad:<name>`: `stelliad:create-spec` and the spec loop
for specs, `stelliad:create-ticket` and `review-ticket` for issues the loop can
take. [`AGENTS.md`](AGENTS.md) points spec and ticket work at them, the README and
[`STARTER-SKILLS.md`](STARTER-SKILLS.md) say why Stelliad is the one set installed rather than copied,
and the lens counts its skills as the harness's. A new test checks every
plugin the settings switch on comes from a marketplace they name.
[`.gitignore`](.gitignore) now ignores `.claude/settings.local.json`, where the
per-person opt-out below is written, so it can't be committed by accident.

Files: [`.claude/settings.json`](.claude/settings.json), [`.claude/harness-lens.json`](.claude/harness-lens.json), [`AGENTS.md`](AGENTS.md), [`README.md`](README.md),
[`STARTER-SKILLS.md`](STARTER-SKILLS.md), [`examples/mods/harness-lens/README.md`](examples/mods/harness-lens/README.md), [`tests/test_plugins.py`](tests/test_plugins.py), [`.gitignore`](.gitignore)

**Do:** in an older copy, add the `stelliad` entry to `extraKnownMarketplaces`
and `"stelliad@stelliad": true` to `enabledPlugins` in [`.claude/settings.json`](.claude/settings.json),
and copy [`.claude/harness-lens.json`](.claude/harness-lens.json). Stelliad should come on with your next
session in that folder; if it doesn't, run `/plugin install stelliad@stelliad`.
To keep it off for yourself, run
`claude plugin disable stelliad@stelliad --scope local`.

## 2026-10-11: link_files.py leaves ~~~ code blocks alone

[`scripts/link_files.py`](scripts/link_files.py) now treats a block fenced with `~~~` as code, the same
as one fenced with three backticks, and a block closes only on the marker that
opened it, so file names inside it stay plain.

Files: [`scripts/link_files.py`](scripts/link_files.py), [`tests/test_link_files.py`](tests/test_link_files.py)

**Do:** if your copy has `~~~` blocks, check them for links like
``[`name`](path)`` that an earlier run added and remove them by hand.
Re-running the script won't remove them.

## 2026-10-11: Loop commits use the issue title

Each round's commit from [`scripts/loop.py`](scripts/loop.py) now takes the issue's title as its
subject and names the issue and round in its body, so a squash merge leaves a
readable line on `main` instead of `loop: issue N round R`.

Files: [`scripts/loop.py`](scripts/loop.py), [`tests/test_loop.py`](tests/test_loop.py)

**Do:** nothing.

## 2026-10-11: loop run --issue exits when that issue is done

`python3 scripts/loop.py run --issue N` now stops once issue N has a pull
request or is blocked, or logs `IDLE` once and stops if N isn't ready, instead
of polling for an issue that can never come.

Files: [`scripts/loop.py`](scripts/loop.py), [`tests/test_loop.py`](tests/test_loop.py)

**Do:** nothing.

## 2026-10-11: check_setup stops on --help or an unknown flag

[`scripts/check_setup.py`](scripts/check_setup.py) now reads its arguments with argparse, so `--help`
prints usage and a mistyped flag such as `--chek` stops with an error, instead
of either one running every check.

Files: [`scripts/check_setup.py`](scripts/check_setup.py), [`tests/test_check_setup.py`](tests/test_check_setup.py)

**Do:** nothing.

## 2026-10-11: usage_report refuses a date it can't read

[`scripts/usage_report.py`](scripts/usage_report.py) now stops with an error naming `--since` and the
`YYYY-MM-DD` format when given a date it can't read, instead of printing a
report that silently counts the wrong lines.

Files: [`scripts/usage_report.py`](scripts/usage_report.py), [`tests/test_usage.py`](tests/test_usage.py)

**Do:** nothing.

## 2026-10-11: link_files stops on --help or an unknown flag

[`scripts/link_files.py`](scripts/link_files.py) now reads its arguments with argparse, so `--help`
prints usage and a mistyped flag such as `--chek` stops with an error, instead
of either one linking every file name in the repo.

Files: [`scripts/link_files.py`](scripts/link_files.py), [`tests/test_link_files.py`](tests/test_link_files.py)

**Do:** nothing.

## 2026-10-11: The lens can show the session's scope

A harness that scopes a session to one client or project can now see that
scope on the lens line, first: `scope: partner fabrikam`. List the files that
hold it under a new `scope` key in [`.claude/harness-lens.json`](.claude/harness-lens.json); `/lens` prints
it too. The starter declares no scope, so its band doesn't change.

Files: [`examples/mods/harness-lens/`](examples/mods/harness-lens/) (`hooks/logic.ts`, `hooks/register.tsx`,
`types/index.d.ts`, [`README.md`](examples/mods/harness-lens/README.md), the tests), version 0.2.0.

**Do:** nothing, unless your harness has a scope file. Then add its path to
`scope` in [`.claude/harness-lens.json`](.claude/harness-lens.json).

## 2026-10-09: What a ticket holds, and how one ends

[`steering/tickets.md`](steering/tickets.md) says what goes in an issue (what and why, a "done
means" a check can prove, what's out of scope, pointers), when one is ready
for the loop, what a comment on one is for, and how one ends. New issues on
GitHub start from [`.github/ISSUE_TEMPLATE/loop-task.md`](.github/ISSUE_TEMPLATE/loop-task.md). The loop's pull
request now says `Closes #N`, so merging it closes the issue, and the loop
comments on the issue when it opens the pull request or blocks.

**Files:** [`steering/tickets.md`](steering/tickets.md), [`.github/ISSUE_TEMPLATE/loop-task.md`](.github/ISSUE_TEMPLATE/loop-task.md), [`scripts/loop.py`](scripts/loop.py),
[`tests/test_loop.py`](tests/test_loop.py), [`skills/loop-control/SKILL.md`](skills/loop-control/SKILL.md), [`AGENTS.md`](AGENTS.md), [`HOW-IT-WORKS.md`](HOW-IT-WORKS.md),
[`docs/specs/lightweight-loop.md`](docs/specs/lightweight-loop.md)

**Do:** take the steering file, its row in [`AGENTS.md`](AGENTS.md), the issue template and
[`scripts/loop.py`](scripts/loop.py). The loop's `gh` sign-in now needs permission to comment on
issues, which a normal sign-in has.

## 2026-10-09: Loop control skill

[`skills/loop-control/`](skills/loop-control/) drives the loop from a conversation. "Put #12 on the
loop" reads the issue, checks it's one change with a check that proves it and
nothing outside the repo, says if the pull request would be public, and asks
before labelling. It also starts the loop (setup check and dry run first),
says what the loop did (outcome, rounds, review findings, what the review
couldn't check), and stops it with the label taken off first.

**Files:** [`skills/loop-control/SKILL.md`](skills/loop-control/SKILL.md), [`AGENTS.md`](AGENTS.md), [`HOW-IT-WORKS.md`](HOW-IT-WORKS.md)

**Do:** take [`skills/loop-control/`](skills/loop-control/) and its row in [`AGENTS.md`](AGENTS.md).

## 2026-10-09: Loop pane

A Claude Code mod: `/loop-pane` opens a pane beside the conversation showing
the loop. Whether it's running, which ready issues are waiting, and for each
issue the step it's on and its round, the last test and review results, and
its pull request, with a button that copies the link. An issue that reaches
an end pops up a notice. It reads `.loop/status.json` every two seconds while
the pane is open and only reads. It's on by default, like the lens.

**Files:** [`examples/mods/loop-pane/`](examples/mods/loop-pane/), [`.claude-plugin/marketplace.json`](.claude-plugin/marketplace.json),
[`.claude/settings.json`](.claude/settings.json), [`AGENTS.md`](AGENTS.md), [`HOW-IT-WORKS.md`](HOW-IT-WORKS.md)

**Do:** take [`examples/mods/loop-pane/`](examples/mods/loop-pane/) and the `loop-pane` entry in
[`.claude-plugin/marketplace.json`](.claude-plugin/marketplace.json), and add
`"loop-pane@sanvio-harness-starter": true` to `enabledPlugins` in your
[`.claude/settings.json`](.claude/settings.json). Needs the status file entry below.

## 2026-10-09: The loop writes a status file

[`scripts/loop.py`](scripts/loop.py) now keeps `.loop/status.json` up to date at every step:
whether it's running, which ready issues are waiting, and for each issue the
step it's on, the round, the last test and review results, and the pull
request. The log stays as it was. A dashboard, a pane or a script reads the
file instead of parsing the log.

**Files:** [`scripts/loop.py`](scripts/loop.py), [`tests/test_loop.py`](tests/test_loop.py), [`HOW-IT-WORKS.md`](HOW-IT-WORKS.md)

**Do:** take [`scripts/loop.py`](scripts/loop.py) if you haven't changed yours. `.loop/` is already
gitignored.

## 2026-10-09: How to try the loop

[`HOW-IT-WORKS.md`](HOW-IT-WORKS.md) now shows the loop's flags (`--dry-run`, `--once`,
`--issue`), says to try it on a private copy because a real run opens a pull
request, and says what the review agent can and can't check.

**Files:** [`HOW-IT-WORKS.md`](HOW-IT-WORKS.md)

**Do:** nothing.

## 2026-10-09: What counts lives in this file

What gets an entry here, and the shape of one, moved from
[`steering/operating.md`](steering/operating.md) to the top of this file, where you are when you write
one. [`steering/operating.md`](steering/operating.md) loads into every session, and it no longer
repeats what [`AGENTS.md`](AGENTS.md) already says about the company files. The
always-loaded set is about 30 lines shorter.

**Files:** [`CHANGELOG.md`](CHANGELOG.md), [`steering/operating.md`](steering/operating.md), [`AGENTS.md`](AGENTS.md),
[`skills/review-pr/SKILL.md`](skills/review-pr/SKILL.md)

**Do:** if you copied [`steering/operating.md`](steering/operating.md), take the new one, or delete
its "Telling people what changed" section and take this file's header.

## 2026-10-09: Where it came from

The README now says who makes the starter and asks one thing beyond the MIT
licence: keep the line that says where a file came from. Each skill carries
that line as a `license:` field in its frontmatter, and the gate, the guard
and the git hook carry it as a comment. [`CITATION.cff`](CITATION.cff) turns on GitHub's
"Cite this repository" button.

**Files:** [`README.md`](README.md), [`CITATION.cff`](CITATION.cff), every `SKILL.md`,
[`examples/proposal/gates/proposal_gate.py`](examples/proposal/gates/proposal_gate.py), [`.claude/hooks/guard.py`](.claude/hooks/guard.py),
[`.githooks/pre-commit`](.githooks/pre-commit)

**Do:** nothing. If you copy a file into your own harness, keep its credit line.

## 2026-10-09: Usage log and sprint report

A new hook logs which skills, agents and slash commands ran, and when the guard
refused or asked and whether you said yes. Names and counts only, never
prompts, paths or code, in `.harness/usage/<you>.jsonl`, which is gitignored.
At the end of a sprint, `harness-report` turns your log into a short report with
your own proposals, shared as a pull request into [`reports/usage/`](reports/usage/). Whoever owns
the harness reads them together and decides what goes in.

**Files:** [`.claude/hooks/usage_log.py`](.claude/hooks/usage_log.py), [`.claude/settings.json`](.claude/settings.json), [`scripts/usage_report.py`](scripts/usage_report.py),
[`skills/harness-report/SKILL.md`](skills/harness-report/SKILL.md), [`reports/usage/README.md`](reports/usage/README.md), [`.gitignore`](.gitignore),
[`tests/test_usage.py`](tests/test_usage.py), [`AGENTS.md`](AGENTS.md), [`README.md`](README.md)

**Do:** take the files above, add the usage-log entries from [`.claude/settings.json`](.claude/settings.json) to
yours, and add `.harness/` to your [`.gitignore`](.gitignore). Tell your team it's on, and
that `HARNESS_USAGE_LOG=off` turns it off for them.

## 2026-10-09: A loop that runs without you

[`scripts/loop.py`](scripts/loop.py) takes an open issue labelled `loop-ready`
through the flywheel: a fresh agent plans it, another builds it in a worktree,
the script runs your tests itself, a third fresh session reviews the diff, and
a pull request opens when both pass. Five rounds, then the issue is labelled
`loop:blocked`. It writes one plain log, `.loop/loop.log`, to watch with
`tail -f`, and a `.loop/lessons.md` in the shape [`skills/learn/`](skills/learn/)
reads. It checks the issue is still open before it opens a pull request, and
it never merges. Standard library only.

**Files:** [`scripts/loop.py`](scripts/loop.py), [`tests/test_loop.py`](tests/test_loop.py),
[`docs/specs/lightweight-loop.md`](docs/specs/lightweight-loop.md), [`HOW-IT-WORKS.md`](HOW-IT-WORKS.md), [`README.md`](README.md), [`skills/learn/SKILL.md`](skills/learn/SKILL.md),
[`.gitignore`](.gitignore)

**Do:** take [`scripts/loop.py`](scripts/loop.py) and its test, and add `.loop/` to your
[`.gitignore`](.gitignore). Set `test_command` in a `loop.json` at your repo root to the
command that proves a change works, then try `python3 scripts/loop.py run --dry-run`.
It needs `git` and a signed-in `gh`.

## 2026-10-09: The harness lens is on by default

The lens now loads by itself in Claude Code: [`.claude/settings.json`](.claude/settings.json) names
this repo as a plugin marketplace, listed in [`.claude-plugin/marketplace.json`](.claude-plugin/marketplace.json), and
turns the lens on. Its README says how to install it from inside a session if
it doesn't show, and how to turn it off just for you.
`/orientation` now points at the line rather than asking you to load it.
The Set up section of [`README.md`](README.md) covers it too: trust the folder,
what the line looks like, and what to do when it doesn't show.

**Files:** [`.claude-plugin/marketplace.json`](.claude-plugin/marketplace.json), [`.claude/settings.json`](.claude/settings.json),
[`examples/mods/harness-lens/README.md`](examples/mods/harness-lens/README.md), [`skills/orientation/SKILL.md`](skills/orientation/SKILL.md),
[`AGENTS.md`](AGENTS.md), [`README.md`](README.md)

**Do:** take [`.claude-plugin/marketplace.json`](.claude-plugin/marketplace.json), and add the `extraKnownMarketplaces`
and `enabledPlugins` blocks from [`.claude/settings.json`](.claude/settings.json) to yours. Then restart
Claude Code at the root.

## 2026-10-09: The guard lets an existence check through

The guard refused `test -e .env`, the very check [`steering/data-and-tools.md`](steering/data-and-tools.md)
and the guard's own message tell the agent to use. `test -e`, `-f`, `-s` and
`[ -e … ]` on a credential file now pass. Anything else in the same command
still has to: `test -f .env && cat .env` is refused as before.

**Files:** [`.claude/hooks/guard.py`](.claude/hooks/guard.py), [`tests/test_agent_hooks.py`](tests/test_agent_hooks.py)

**Do:** take [`.claude/hooks/guard.py`](.claude/hooks/guard.py) if you haven't changed yours.

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
