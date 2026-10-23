# How it works

Two pages on what's actually running when you use this harness: what it's made
of, where the loops are, how context is handled, and how much of it is code.

## What it's made of

Nothing here is a framework. It's files your coding agent already knows how to
read, plus a few short scripts that run whatever the agent decides.

| Piece | Is | Who runs it |
|---|---|---|
| [`AGENTS.md`](AGENTS.md) | Standing rules | The agent reads it at the start of every session |
| [`steering/`](steering/) | Standing guidance, one topic per file. Three load every session, the rest when needed | The agent, through [`AGENTS.md`](AGENTS.md) |
| [`skills/`](skills/) | Named procedures with inputs, steps and an output | The agent, when a request matches one |
| [`agents/`](agents/) | Instructions for a second reader with one job | A separate agent session, started by the first |
| [`gates/`](gates/) | Scripts that exit non-zero when work isn't ready | The agent, the git hook and CI |
| [`.githooks/`](.githooks/) | The check at commit | Git, whatever the agent decided |
| [`.claude/hooks/`](.claude/hooks/) | Checks before each tool call and at session start | Claude Code, whatever the agent decided |
| `company/`, [`projects/`](projects/) | Who you are, where your data is, your code | Read by the agent, never committed here |
| [`examples/`](examples/) | One worked job with all five layers, to read and copy | You, and the agent when you point it there |

The harness holds only the method. Your company record, your code and your
company's systems stay where they live, under their own access control, and
the harness records where they are. [Where things live](README.md#where-things-live) in the README
has the three places and how the agent reaches each.

The tool (Claude Code, Codex or Kiro) does the model calls, the tool calls, the
MCP connections and the context handling. The harness writes none of that. It
decides what the agent knows, what it's allowed to do, and what counts as done.

## A request, start to finish

1. You ask for something. The tool has already loaded [`AGENTS.md`](AGENTS.md), and in
   Claude Code the name and description of every skill. A skill's full steps
   load only when a request matches it, so twenty skills cost little until one
   is used.
2. The agent follows the skill's steps. Before each tool call, the guard
   checks it: credential files are refused, and a connector call that isn't
   named as a plain read asks you first.
3. The skill ends at a gate. The agent runs it, fixes what it names, and runs
   it again until it passes. That's the first loop.
4. A review agent reads the result in its own fresh context and reports
   findings. It never edits.
5. You commit. The git hook runs the same gate and the secret check. You push,
   and CI runs everything again.

## Where the loops are

- **Fix and recheck**, inside a session: gate fails, agent fixes, gate runs.
- **At commit and at push**: the same checks, run by git and CI rather than
  by the agent's good intentions.
- **A stamp goes stale**, on one piece of work: each check stamps a fingerprint
  of the text it passed, in order, and an edit sends it back through them.
  [`examples/proposal/gates/stamp.py`](examples/proposal/gates/stamp.py) is the small version.
- **Close the gap**, between phases: the phase gate names what's missing and
  what closes it, you close it, and the gate runs again.
  [`examples/proposal/gates/phase_gate.py`](examples/proposal/gates/phase_gate.py) is the small version.
- **Mistake to rule**, across sessions: when the agent gets something wrong,
  [`skills/learn/`](skills/learn/) writes the rule into the file that governs it.
- **Sprint report**, across people: each person's usage log records which
  skills, agents and guards fired. At sprint end, `harness-report` turns it into
  a short report with their proposals, shared as a pull request. The owner reads
  the sprint's reports together and takes what earns a place.

**The runner**, across tickets, is the fifth, and [`scripts/loop.py`](scripts/loop.py)
is the small version of it. It picks up an issue labelled `loop-ready`, starts
a fresh agent session to build it, runs your tests and a review, and repeats
until both pass or it gives up and asks a person. Each round starts clean and
reads its state from files (the ticket, the diff, the test output), not from a
growing transcript. That's the same shape as this starter, run headless with
`claude -p` instead of you at the keyboard. [The loop](#the-loop) below has
the rest.

## The loop

`python3 scripts/loop.py run` takes one issue through the flywheel and then
the next. Nothing runs until you start it, and it never merges.

| Step | What happens | Left behind in `.loop/issue-N/` |
|---|---|---|
| Discover | The next open issue labelled `loop-ready` that isn't assigned to someone else, skipping one still waiting on an open dependency until it closes. A dependency counts as met when a merged change closes it; one closed by hand blocks the issue, with a comment saying why | `ticket.md` |
| Shape | A fresh agent writes the smallest plan that would count, plus the check that proves it | `plan.md` |
| Build | A fresh agent makes the change in a git worktree, outside your clone (`~/.harness-loop/`). Once the pull request is merged or closed, the loop removes the worktree and its branch while it's idle, unless the worktree has changes or the branch has commits the pull request doesn't | the commit |
| Validate | The script runs your test command. A second fresh agent reads the diff and the output and says PASS or FIX | `test-output.txt`, `diff.patch`, `review.md` |
| Scale | On PASS, and if the issue is still open, it opens a pull request that says `Closes #N`, the files changed, the last test lines, the review in full and the plan (collapsed), and comments the link on the issue. A blocked issue gets a comment saying why. It writes what went wrong into `.loop/lessons.md`, in the shape [`skills/learn/`](skills/learn/) reads, then takes the next issue | the pull request |

Build and Validate repeat up to five rounds. After that the issue is labelled
`loop:blocked` and the loop moves on without it. A pass needs the tests to exit 0
**and** the review to say PASS: the script runs the tests, so the agent never
grades its own work.

![scripts/loop.py takes issue #12 through five steps. Discover picks the loop-ready issue and writes ticket.md. Shape: a fresh agent writes plan.md. Build: another fresh agent makes the change in a worktree outside the clone. Validate: the script runs the tests and a second agent reads the diff; round 1 fails with review FIX, so it goes back to Build. Round 2 passes the tests and the review says PASS. Scale opens a pull request that closes #12 and doesn't merge it, and what went wrong goes to lessons.md. Each step writes one line to .loop/loop.log as it happens.](docs/one-issue-through-the-loop.gif)

**Watch it** with `tail -f .loop/loop.log`, or run it in tmux and attach: the `loop-control` skill starts it that way when tmux is installed, and a run inside tmux logs a `START` line with the attach command. One line per event, the issue
first, nothing secret in it:

    2026-10-09T20:14:52 #12 VALIDATE round 1 tests failed (2) review FIX
    2026-10-09T20:19:30 #12 VALIDATE round 2 tests passed review PASS
    2026-10-09T20:19:44 #12 SCALE PR opened https://github.com/you/repo/pull/31

Point a dashboard or a Slack post at that file and you have a monitor.
`.loop/status.json` holds the same state for a tool to read rather than parse:
`running`, when the run `started` (UTC), the `tmux` session it's in (when it was started in one), the
`queue` of ready issues waiting, and one row per issue, newest
first, with its `step`, `round`, `state` (`working`, `pr`, `blocked`,
`stopped` or `skipped`), the last `tests` and `review`, and the `pr` link.
It's rewritten whole at each step, so a reader never sees half of it.
In Claude Code, `/loop-pane` draws it in a pane beside the conversation
([`examples/mods/loop-pane/`](examples/mods/loop-pane/)). On a Mac, a run inside tmux also writes
`.loop/watch.command`, and the pane's **Watch it** button opens it: a new
Terminal window attached to the session, read-only.

A running loop keeps the code it started with: when [`scripts/loop.py`](scripts/loop.py) changes
on disk under it, it logs one `STALE` line on an idle poll and carries on, and
`python3 scripts/loop.py stop` then starting it again picks up the new code.

**More than one at once.** Set `max_workers` in `loop.json` and it works up to
that many ready issues side by side, each in its own worktree. One that depends
on an issue still being worked waits for it. Each issue's agents write what
they say to `.loop/issue-N/agent.log` as they say it. Run inside tmux, each
issue also gets a window named `issue-N` that follows that file and closes
when the issue ends, and while it's open the issue's row in `status.json`
names it as `window`. On a Mac the run also writes `.loop/issue-N/watch.command`
for that window, which the pane's **Watch** on the issue opens read-only. A stop
starts nothing new and lets each running issue finish its step. Every worker
runs its own agent sessions, so usage grows with the number of workers.

**Make it yours** with a `loop.json` at the repo root. Any key you leave out
keeps its default:

| Key | Default | Is |
|---|---|---|
| `agent` | `claude -p --permission-mode acceptEdits` | The command that builds, or a name: `claude` or `codex`, with `:<model>` if you like. `ollama` can't build: it has no tools to edit files with. The prompt arrives on stdin, so any other command line works the same way |
| `reader_agent` | `claude -p` | The command that plans and reviews, or a name: `claude`, `codex` or `ollama:<model>`. It's told not to edit, and anything it edits is thrown away. Held to read tools in the checkout when it's `claude`; for `review`, it has to be `claude` or `ollama:<model>` |
| `review_agent` | empty | The command that reviews, when it's set, or a name: `claude`, `codex` or `ollama:<model>`. Empty means `reader_agent` reviews. Held to read tools the same way, and for `review` it has to be `claude` or `ollama:<model>` |
| `test_command` | `python3 -m unittest discover -s tests` | Run by the script, in the worktree |
| `base`, `max_rounds` | `main`, `5` | Where branches start, and rounds before giving up |
| `max_workers` | `1` | How many issues it works at once. Each runs its own agent sessions, so usage grows with it |
| `hours` | empty | When `run` and `review` may start something, in local time, such as `Mon-Fri 09:00-17:00`. Empty means any time; `--hours` replaces it for one run. *In working hours* below has the format |
| `worktree_dir` | `~/.harness-loop/<repo>` | Where the build checkouts go. Keep it outside the clone: an agent started inside it loads this repo's [`CLAUDE.md`](CLAUDE.md) twice and stops to ask you to restart from the root |
| `ready_label`, `blocked_label` | `loop-ready`, `loop:blocked` | What it looks for, and what it leaves on a failure |
| `review_query` | `review-requested:@me` | The GitHub search `loop.py review` runs to find pull requests that ask for you |

To have one model build and another review it, set the two apart:

    "agent": "claude -p --model <one model> --permission-mode acceptEdits",
    "review_agent": "claude -p --model <another model>"

Or name the tool, and the loop gives it the flags its job needs. Codex
reviews, in its read-only sandbox, with:

    {"review_agent": "codex"}

To build with Claude and review with a model on your own machine:

    {"review_agent": "ollama:qwen3"}

A name can carry a model, as in `claude:<model>` or `codex:<model>`. Ollama
needs one. A name that can't do its job, `ollama` as `agent` or `ollama` with
no model, stops the run before it takes an issue, and the log says why.

**Before the first run,** run `python3 scripts/check_setup.py` and fix any FAIL. A
warning the harness's session-start hook prints (an unset `core.hooksPath`, for
instance) is the first thing every agent session says, and it ends up at the top of
`plan.md` and the review.

**Try it** on a private copy first. On a clone of the public starter, the
first real run opens a public pull request. Label one small issue
`loop-ready`, then:

    python3 scripts/loop.py run --dry-run    # which issue it would take, then stop
    python3 scripts/loop.py run --once       # one issue, then stop
    python3 scripts/loop.py run --issue 12   # only issue #12
    python3 scripts/loop.py run              # every ready issue, until none are left
    python3 scripts/loop.py run --for 8h     # every ready issue, taking no new one after 8 hours

Then read `.loop/issue-N/` and the pull request it opened.

**For a set time.** `--for` takes a whole number then `m`, `h` or `d` (`90m`,
`8h`, `2d`), and works on `review` too. The loop logs an `UNTIL` line with the
local time it ends. After that it starts no new issue or review, lets each
running one finish (an issue still gets every round, to a pull request or a
block), logs `END --for 8h reached` and exits. Any other value for `--for` is
refused before the loop starts. `loop.py stop` still ends it sooner.

**In working hours.** `"hours": "Mon-Fri 09:00-17:00"` in `loop.json`, or
`--hours "Mon-Fri 09:00-17:00"` on `run` or `review` for one run (it replaces
the `loop.json` value), keeps the loop to those hours in the machine's local
time. Days are `Mon` to `Sun`, capitalised as shown (`mon` is refused), alone, as a range (`Fri-Mon` wraps) or in a
comma list (`Mon,Wed-Fri`), then `HH:MM-HH:MM` on a 24-hour clock. A window
that crosses midnight belongs to the day it starts: `Fri 22:00-06:00` covers
early Saturday, not early Friday. Outside the hours the loop starts no new
issue or review, lets a running one finish every round, logs one `HOURS` line
with the next start, and waits, so `run --hours "Mon-Fri 22:00-06:00"` works
the queue on weeknights only. A value it can't read logs an `ERROR` and the
loop exits before it takes anything. With `--for` as well, the run still ends
on time, waiting or not.

**The build agent doesn't install packages.** This is the default, and it
stays the default. The agent can edit files, but `npm install`, `pip install`
and anything else that fetches a package need an approval nobody is there to
give, unless your own `~/.claude/settings.json` or the checkout's
[`.claude/settings.json`](.claude/settings.json) already allows it, so check both. A ticket whose work
needs a package the agent has to install blocks after `max_rounds`.

What the agent can still do is edit `package.json`, `pyproject.toml` or a
lockfile, and the script runs `test_command` with no approval at all. So use a
test command that installs only what the committed lockfile says and fails when
the manifest disagrees with it: `npm ci && npm test`, or `uv run --locked
pytest`. A fresh checkout has no `node_modules`, so a Node project needs that
`npm ci` anyway. In the pull request, read any manifest or lockfile change
before you merge it.

To give a ticket a new dependency, add it yourself first:

- Commit the dependency and its lockfile straight to `base`, and the ticket
  needs nothing more. Or open an issue for it, leave `loop-ready` off it, and
  merge a pull request that says `Closes #N`. Then put `Depends on #N` on the
  ticket, naming that issue rather than the pull request: the loop blocks a
  number that isn't an issue, or an issue closed by hand.
- If the ticket has already blocked, its old checkout and branch are reused as
  they are when it's relabelled, without your dependency. Remove both first,
  `git worktree remove <worktree_dir>/issue-N` then `git branch -D
  loop/issue-N`, then take `loop:blocked` off and put `loop-ready` back.

A team that wants its loop to install can allow it, in the harness's
`loop.json` or, with `--project`, the project's own. Name the commands the build
agent may run:

    {"agent": "claude -p --permission-mode acceptEdits --allowedTools \"Bash(npm install --ignore-scripts *)\""}

That works for a `claude` agent only. `codex` ignores `--allowedTools`, and a
full command line replaces `claude:<model>`, so add `--model` if you had one.
It's the team's decision, not the harness's default, and it lets an agent
nobody is watching pull any package the registry has. Without
`--ignore-scripts`, that package's install scripts also run on the machine
with your full environment, including the tokens the test command is denied.
Allow the narrowest command that does the job. With `--project`, whoever can
merge to the project's repo can change its `loop.json`, and a private
registry's token won't reach `test_command`, which runs with every variable
named like a token removed.

**What the review can see.** The reviewer gets the plan, the diff and the
script's test output. With the default `reader_agent` it can't run commands,
so it checks the rest by reading the code. If the proof is a command, put
that command in `test_command`, which the script runs itself. That includes
end-to-end tests: `npm test && npx playwright test` runs them every round, and
makes each round slower.

**Coverage, if you want it.** Put it in `test_command`, for instance
`"test_command": "uv run pytest --cov --cov-fail-under=80"`. The number is
the project's to choose, and a round below it fails like any other test
failure. A coverage pass shows which lines ran, not that a test would catch
a change to them; [`skills/review-tests/`](skills/review-tests/) checks that.

**On a project under [`projects/`](projects/).** Run it from the harness root with
`--project`, on `run`, `review` and `stop`:

    python3 scripts/loop.py run --project projects/app
    python3 scripts/loop.py stop --project projects/app

It then works that clone's GitHub repo: its issues, its pull requests and the
`base` in its own `loop.json`. That `loop.json` has to set `test_command`,
because the default tests the harness. For a TypeScript project,
`{"test_command": "npm test"}`, or `node --test` with no `package.json`
script; [`examples/typescript/`](examples/typescript/) has a fuller one. The loop refuses, with one
`ERROR` line and before it takes anything, a folder that isn't directly under
[`projects/`](projects/), one that isn't a git clone of its own, a clone whose `origin`
isn't on github.com, or a `loop.json` without `test_command`. Its state stays in
the harness, in `.loop/projects/<name>/` (`status.json`, `loop.log`,
`issue-N/` and a lock of its own, so it runs beside the harness's loop). None of
it goes in the project's folder, which gets only the `loop/issue-N` branches
and their checkouts, as any clone the loop works does. Its checkouts go in
`~/.harness-loop/<harness>/<name>/`. A checkout of the project holds none of
the harness's rules, so every prompt starts with [`AGENTS.md`](AGENTS.md) and the three
steering files it loads every session, and says
the project's own `AGENTS.md` or `CLAUDE.md` adds to them and never loosens them. A `claude` build agent also
gets the harness's [`.claude/hooks/guard.py`](.claude/hooks/guard.py) through `--settings`. Another
build agent, such as `codex`, has no hook to put it in, so it builds without
the guard. The loop pane shows the harness's own loop only.

**From a conversation,** the [`skills/loop-control/`](skills/loop-control/) skill does the same jobs:
it checks an issue is ready before labelling it, starts the loop, says what
it did, and stops it with the label off first.

**Rules it keeps.** To take an issue off the loop, the label comes off first and
then the run stops, because stopping alone lets the queue pick it straight back
up. `python3 scripts/loop.py stop` ends a running loop at its next step. A lock
file stops two loops running in one clone. On your machine it uses your own
agent sign-in and holds no credentials; in [GitHub Actions](#off-your-laptop) the
agent needs a key, held as a repository secret. A ticket is an instruction to an
agent, so label only issues you wrote or have read.

**Whose issues it builds from.** An issue written by the repo's owner, a member
or a collaborator is taken as it stands. Anyone else's is taken only as it was
when it was labelled `loop-ready`: if its title or body changed after the label
went on, or it holds an HTML comment (text the issue's page doesn't show), the
loop blocks it and says why on the issue. Read it again and label it again, or
copy what it asks into an issue of your own. The loop reads the issue fresh at
that check, so the text it checked is the text the agents get.

**What the issue's text can reach.** The planner and the reviewer run in the
build checkout with read tools only, so they can't read the rest of your clone
(`company/`, [`projects/`](projects/)) into a plan that ends up in a pull request. The loop
commits with git hooks off, so a hook the agent writes doesn't run. It runs your
test command without anything named like a secret in its environment (tokens,
keys, passwords, `AWS_*`, the SSH agent). The tests still run code the agent
wrote, as you, so they can reach whatever your user can on disk. Run the loop
as a user, or on a machine, with nothing you'd mind a test reading.

**Reviewing pull requests.** The issues are half the queue; pull requests waiting
on your review are the other half. Start it on the machine the loop runs on, in
its own tmux session. It takes the same lock as `run`, so one process works a
clone at a time: to run both at once, give each its own clone.

    python3 scripts/loop.py review --once    # review what is waiting, then stop
    python3 scripts/loop.py review           # then keep watching, every poll_seconds

It lists the open, non-draft pull requests that match `review_query`. For each
new head commit it checks the pull request out detached, outside your clone, in
`~/.harness-loop/`, and has a fresh `reader_agent` follow
[`skills/review-pr/`](skills/review-pr/) for the change between the base and the
head. The script, not the agent, posts the report: one comment per pull
request, marked, and edited in place on the next commit. It's the same
comment-edited-in-place pattern as [`examples/ci/review-pr.yml`](examples/ci/review-pr.yml), on the machine
that already runs the loop and with no CI minutes. It writes one line per
review to the same log:

    2026-10-13T09:02:11 - REVIEW #31 4f2a9c1 posted
    2026-10-13T09:02:12 - REVIEW #32 7be03d8 skipped (draft)
    2026-10-13T09:11:40 - REVIEW #33 c19e5a2 failed: agent exit 1

A commit is reviewed once. The result goes in `.loop/status.json` under
`reviews`, so a poll that sees the same commit again starts no agent. A review
whose agent exits non-zero or times out posts nothing, and it isn't tried again
until the pull request has a new commit; neither is a diff that can't be made,
such as a base with no history in common. A fetch, checkout or GitHub error is
logged once with `(will retry)` and tried again on the next poll.

**What it never does:** approve, request changes, merge, push, or ask the agent
to post. The comment goes up under your own GitHub identity. A pull request's
diff, commit messages and files are written by whoever opened it, so the prompt
calls them material to review, never instructions. The agent is told not to
edit, and whatever it edits is thrown away with the checkout. The
`reader_agent` runs with `--restricted --strict-mcp-config --tools Read,Grep,Glob`,
whatever tools or permissions `loop.json` gave it: it can read the checkout and
nothing outside it, so a pull request written to steer it can't get your keys
or tokens into the comment, and the checkout's own [`.claude/`](.claude/) settings and
hooks never load. That's why review mode needs `reader_agent` to be `claude`
itself (a path is fine, `npx` or `env` in front isn't), or `ollama:<model>`,
which runs as it is because it has no tools to reach anything with. Nothing
here knows how to confine another tool, so with any other command it reviews
nothing and logs why. That includes `codex`: its read-only sandbox can still
read files outside the checkout, and what it read could end up in the posted
comment. When `review_agent` is set, it's the one that reviews, so the same
holds for it. The issue loop still takes Codex or Kiro, because the issues it
builds from are checked first.

The comment opens with a line saying an agent wrote it from the pull request's
own text, and an `@` in the report can't mention anyone, so text planted in a
pull request can't page your team through your account. It still posts as you:
to post as a bot, sign `gh` in as one on the machine that runs the review.
`loop.py stop` ends it at its next step, as it does `run`.

**Not in it, on purpose:** many projects in one run, voice dispatch, merge passes,
a dashboard, model-tier routing. Each can be added by whoever needs it, reading
the log.

### Off your laptop

The loop is one script, so it runs wherever `python3`, `git`, `gh` and your
agent's CLI do. There are three places, and the script is the same in each:

| Where | Needs | Costs |
|---|---|---|
| Your own machine, in tmux | Your laptop awake and online, `gh` signed in, your agent signed in | Nothing extra. It stops when the lid closes |
| An always-on machine (a VM) beside the repo | A clone, `python3`, `git`, `gh` and the agent CLI signed in as you, and `loop.py run` in tmux | A machine that's billed whether or not there's work, and someone to patch it |
| GitHub Actions | The workflow in [`examples/ci/loop.yml`](examples/ci/loop.yml), an API key as a repository secret, and the agent CLI installed on the runner each run | Runner minutes for as long as a pass iterates, and the agent's usage on the key |

Setting up the VM is yours: nothing here goes beyond naming it. Actions is the
one the starter ships an example for: it runs `python3 scripts/loop.py run --once`
on a schedule and on manual dispatch, and uploads `.loop/` as a build artifact so
the plan, the test output and the review outlive the runner.

**Where Actions is the weaker home:**

- A run that iterates for an hour spends an hour of runner minutes. Five rounds
  of a slow test command is a long job, and it's billed like one.
- `/loop-pane` and `tmux attach` don't reach a runner. You read the job log and
  the artifact, not the pane.
- A job that commits back puts building into a pipeline that is otherwise only
  checks. Everything else in [`.github/workflows/`](.github/workflows/) reads the repo; this one writes
  to it, which is why its `permissions:` block names contents, issues and pull
  requests, all write, and nothing else.

**Its pull request won't start your checks.** A pull request opened with the
workflow's own `GITHUB_TOKEN` doesn't trigger other workflows, so the repo's
required checks don't run on it, and it can't merge until something triggers
them. The choice that changes that is a token that isn't the workflow's: a
fine-grained personal access token (or a GitHub App's token) with contents,
issues and pull requests write, held as a secret and used in place of
`GITHUB_TOKEN` for `GH_TOKEN` and the checkout. The example sets that token
only on the step that runs the loop and on checkout, after the agent is
installed, so the install never reads it.

**It can't tell who you are.** With a workflow token, `gh api user` returns no
login, so the loop skips every issue that's assigned to anyone and takes only
unassigned ones. The same personal token gives it your login, and your assigned
issues come back. Reading a login from the config instead is a change to
[`scripts/loop.py`](scripts/loop.py), left for when this limit bites.

**Credentials change.** On your machine the loop uses your own agent sign-in. In
Actions the agent needs an API key (or a cloud provider's credentials), held as a
repository secret and referenced by name, as `${{ secrets.ANTHROPIC_API_KEY }}`.
It's never written into a file, the workflow, `loop.json` or an issue.

**To use it,** copy [`examples/ci/loop.yml`](examples/ci/loop.yml) into [`.github/workflows/`](.github/workflows/), add the
secret it names, and read its opening comment: it lists the repository setting
that has to be on for a workflow to open a pull request at all.

## Context: who remembers what

- **Each agent has its own context.** A review agent, or any subagent, starts
  with only what it's given and hands back a report. The main session gets the
  report, not everything the reviewer read. That's why read-heavy work goes to
  a subagent: it can read 300 pages and return one.
- **The tool summarises, not the harness.** When a long session fills its
  context, Claude Code compacts it automatically. The harness doesn't write
  summarisation code.
- **What must survive goes in a file.** A session ends and its context is
  gone. Rules, decisions and lessons live in [`AGENTS.md`](AGENTS.md), a skill or a gate,
  where the next session reads them. A correction you only said out loud
  hasn't happened.

## How much of it is code

Very little. The agents are the tool's own agents, defined in Markdown. The
skills are Markdown. The code is the gate, the git hook, the setup check and
three small Claude Code hooks, all standard-library Python or shell, all with
tests.

You'd write SDK code when a loop has to run without a person: in CI, on a
schedule, or across many tickets at once. Even then, the harness files stay
the same. The runner reads [`AGENTS.md`](AGENTS.md), the skills and the gates exactly as you
do.

## One harness, many teams

One harness carries the rules every team shares. Each project under
[`projects/`](projects/) adds its own `AGENTS.md` for what's specific to it, and can only
add rules, never loosen them. A risky project (one that writes to a
production system) tightens its own rules and gates. A read-only one needs
fewer. Same harness, same skills, different strictness per project.

One person owns the harness and merges changes to it. Everyone else pulls.
That's what keeps ten developers' agents behaving like one team instead of ten
people's personal setups.

### Strictness follows risk

The same harness runs a read-only report and a service that writes to
production. What changes is how much each project's own `AGENTS.md`, gates
and branch protection ask for:

| | Reads only | Writes to something people use |
|---|---|---|
| Connectors | Read tools are fine | Every write asks first. The guard asks for any connector call not named as a plain read |
| Gates | The harness's own | Plus the project's, in its hook and its CI, required before merge |
| Agents working alone | Fine on a ready ticket | Never against production. Staging only, with that permission written in [`AGENTS.md`](AGENTS.md) |
| Merging | Anyone the owner trusts | The project's owner, after `review-pr` |
| Deploying | Nothing to deploy | A human yes for each production deploy. [`steering/deploying.md`](steering/deploying.md) has the rest |

Start a new project on the right-hand column and loosen it once you've seen
what it does. Going the other way, you learn the risk from an incident.

### How the harness changes

Someone's agent gets something wrong. They say "learn from that", and
[`skills/learn/`](skills/learn/) drafts the rule in the file that governs it. That goes to the
owner as a pull request with a [`CHANGELOG.md`](CHANGELOG.md) entry. Once it's merged,
everyone's `/whats-new` shows it and says what to do to take it.

The sprint report catches what nobody said out loud: a skill nobody uses, an
ask that always gets a yes, a step everyone does by hand. Each person's log
stays on their own machine, holding names and counts, never prompts or code.
Only the report they've read reaches the team ([`reports/usage/`](reports/usage/)).

Nobody edits a shared rule in their own copy. A local edit is a quiet fork,
and the next update collides with it. A rule only one project needs goes in
that project's `AGENTS.md`.

### Where a change lives

A change reaches the people who load the file it's written in, and nobody else:

| Where it's written | Who gets it | What belongs there |
|---|---|---|
| This repo: [`skills/`](skills/), [`steering/`](steering/), [`AGENTS.md`](AGENTS.md), [`.claude/settings.json`](.claude/settings.json) | Everyone, once it's merged and they pull | Anything the team relies on |
| A project's `AGENTS.md`, in that project's own repo under [`projects/`](projects/) | Anyone working in that project, once it's merged there | What only that project needs |
| `.claude/settings.local.json` in your clone | You, in this clone. Git ignores it | Your own permissions and preferences here |
| Your own `~/.claude/CLAUDE.md`, `~/.claude/settings.json` and `~/.claude/skills/` | You, in every repo on your machine | Personal habits nobody else depends on |

The quick test: if `git status` in the repo it belongs to doesn't show the
change, your team won't get it. Something that lives only in `~/.claude/` works for you and for
nobody you work with, and nothing tells you so. If the team needs it, it goes
in one of the first two rows, through a pull request with a
[`CHANGELOG.md`](CHANGELOG.md) entry.

**Don't keep a copy in both.** A skill in `~/.claude/skills/` with the same name
as one in [`skills/`](skills/) wins in Claude Code, so your agent runs your copy and
everyone else runs the harness's: one name, two different skills.
`python3 scripts/check_setup.py` warns when that happens. Settings go the other
way: where this repo's [`.claude/settings.json`](.claude/settings.json) or your `settings.local.json` sets
something, it wins over your `~/.claude/settings.json`. Your `~/.claude/CLAUDE.md`
and this repo's [`CLAUDE.md`](CLAUDE.md) both load, so a rule in yours applies to you alone.

### Who owns what

- **The harness owner**: steering, skills, gates, hooks and the release log.
  Merges every change to them.
- **Each project's lead**: that project's `AGENTS.md`, its gates and its CI.
- **Whoever runs production**: the release step, meaning
  [`steering/deploying.md`](steering/deploying.md) and the deploy workflow.

To make that hold rather than just be written down, add a
`.github/CODEOWNERS` naming the owner for [`steering/`](steering/), [`skills/`](skills/), [`gates/`](gates/),
[`.githooks/`](.githooks/) and [`.github/`](.github/), and turn on "require review from code owners" in
branch protection. A code owner can't approve their own pull request, so this
needs at least two people.
