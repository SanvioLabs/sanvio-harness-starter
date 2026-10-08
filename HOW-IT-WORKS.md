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
| [`company/`](company/), [`projects/`](projects/) | Who you are, where your data is, your code | Read by the agent, never committed here |
| [`examples/`](examples/) | One worked job with all five layers, to read and copy | You, and the agent when you point it there |

The tool (Claude Code, Codex or Kiro) does the model calls, the tool calls, the
MCP connections and the context handling. The harness writes none of that. It
decides what the agent knows, what it's allowed to do, and what counts as done.

## A request, start to finish

1. You ask for something. The tool has already loaded [`AGENTS.md`](AGENTS.md), and in
   Claude Code the name and description of every skill. A skill's full steps
   load only when a request matches it, so twenty skills cost little until one
   is used.
2. The agent follows the skill's steps. Before each tool call, the guard
   checks it: credential files are refused, and a connector that would send,
   edit or delete asks you first.
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
- **Mistake to rule**, across sessions: when the agent gets something wrong,
  [`skills/learn/`](skills/learn/) writes the rule into the file that governs it.

A bigger harness adds a fourth: a runner that picks up a ticket, starts a fresh
agent session to build it, runs the tests and a review, and repeats until the
checks pass or it gives up and asks a person. Each round starts clean and
reads its state from files (the ticket, the diff, the test output), not from a
growing transcript. That's the same shape as this starter, run headless with
`claude -p` or the Claude Agent SDK instead of you at the keyboard.

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
two small Claude Code hooks, all standard-library Python or shell, all with
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
| Connectors | Read tools are fine | Every write asks first. The guard already asks for send, edit, delete and share |
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

Nobody edits a shared rule in their own copy. A local edit is a quiet fork,
and the next update collides with it. A rule only one project needs goes in
that project's `AGENTS.md`.

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
