# How it works

Two pages on what's actually running when you use this harness: what it's made
of, where the loops are, how context is handled, and how much of it is code.

## What it's made of

Nothing here is a framework. It's files your coding agent already knows how to
read, plus a few short scripts that run whatever the agent decides.

| Piece | Is | Who runs it |
|---|---|---|
| `AGENTS.md` | Standing rules | The agent reads it at the start of every session |
| `steering/` | Standing guidance, one topic per file. Three load every session, the rest when needed | The agent, through `AGENTS.md` |
| `skills/` | Named procedures with inputs, steps and an output | The agent, when a request matches one |
| `agents/` | Instructions for a second reader with one job | A separate agent session, started by the first |
| `gates/` | Scripts that exit non-zero when work isn't ready | The agent, the git hook and CI |
| `.githooks/` | The check at commit | Git, whatever the agent decided |
| `.claude/hooks/` | Checks before each tool call and at session start | Claude Code, whatever the agent decided |
| `company/`, `projects/` | Who you are, where your data is, your code | Read by the agent, never committed here |
| `examples/` | One worked job with all five layers, to read and copy | You, and the agent when you point it there |

The tool (Claude Code, Codex or Kiro) does the model calls, the tool calls, the
MCP connections and the context handling. The harness writes none of that. It
decides what the agent knows, what it's allowed to do, and what counts as done.

## A request, start to finish

1. You ask for something. The tool has already loaded `AGENTS.md`, and in
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
  `skills/learn/` writes the rule into the file that governs it.

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
  gone. Rules, decisions and lessons live in `AGENTS.md`, a skill or a gate,
  where the next session reads them. A correction you only said out loud
  hasn't happened.

## How much of it is code

Very little. The agents are the tool's own agents, defined in Markdown. The
skills are Markdown. The code is the gate, the git hook, the setup check and
two small Claude Code hooks, all standard-library Python or shell, all with
tests.

You'd write SDK code when a loop has to run without a person: in CI, on a
schedule, or across many tickets at once. Even then, the harness files stay
the same. The runner reads `AGENTS.md`, the skills and the gates exactly as you
do.

## One harness, many teams

One harness carries the rules every team shares. Each project under
`projects/` adds its own `AGENTS.md` for what's specific to it, and can only
add rules, never loosen them. A risky project (one that writes to a
production system) tightens its own rules and gates. A read-only one needs
fewer. Same harness, same skills, different strictness per project.

One person owns the harness and merges changes to it. Everyone else pulls.
That's what keeps ten developers' agents behaving like one team instead of ten
people's personal setups.
