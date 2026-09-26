---
name: start-here
description: Check a fresh clone, then walk a newcomer through wrapping their own weekly job in the five layers, one drafted file at a time. Use when someone says "get me started", "how do I use this", "set this up for my job", "new here", or asks where to begin.
---

# Start here

The person has just cloned this repo. Show them the harness working on them:
check their setup, ask about their job, then build the five layers around it
one at a time. Instructions, a skill, a gate, the hook, a review agent.

You draft. They say yes or no. Nothing gets written without a yes.

## Rules for this skill

- Never write a file the person hasn't seen and said yes to. Show the whole
  draft for a new file, and a diff for an edit.
- Never overwrite silently. If a file you're about to write already exists,
  it's probably from an earlier run: show what's there and ask whether to keep
  it, edit it or replace it.
- Never remove or weaken a check in `.githooks/pre-commit` or
  `gates/proposal_gate.py`. New checks go alongside the proposal one.
- Never rewrite `AGENTS.md` wholesale. Add to it. The proposal rules and the
  Skills and Agents tables stay.
- Never run a fix the setup check names, never run `git checkout`, and never
  commit. Name the command and let the person run it.
- A no skips that layer and offers the next one. It doesn't end the
  conversation.
- If a request needs a tool-specific hook (`.claude/settings.json`, a Codex or
  Kiro hook) or a change to `gates/proposal_gate.py`, stop and say it's outside
  this skill. The in-loop hook is the last bonus in `EXERCISES.md`.

## Steps

### 1. Check the clone

Read-only. Run each of these and report one line per item, `PASS` or `FAIL`:

| Item | Command | PASS when |
|---|---|---|
| Python 3.9 or newer | `python3 --version` | The version is 3.9 or higher |
| Hook is switched on | `git config core.hooksPath` | It prints exactly `.githooks` |
| The gate passes the example | `python3 gates/proposal_gate.py proposals/juniper-bakery.md` | Exit code 0 |
| The tests pass | `python3 -m unittest discover -s tests` | Exit code 0 |

For every FAIL, name the fix on the same line:

- **Python:** install Python 3.9 or newer. No packages are needed.
- **Hook, unset:** `FAIL: core.hooksPath is not set, so the hook never runs.
  Fix: git config core.hooksPath .githooks`. Don't run it yourself. Say that
  every check in the hook silently does nothing until they do.
- **Hook, set to something else:** FAIL, say what it points at now, and name
  the same fix, `git config core.hooksPath .githooks`. Say that changing it
  stops whatever hooks live there now, so it's their call.
- **Gate or tests:** paste the lines that failed. On a clean clone of `main`
  these pass, so suggest `git status` to look for local changes.

Then list any files in `skills/`, `gates/` and `agents/` beyond the ones this
repo ships (`draft-proposal`, `review-skill`, `start-here`,
`proposal_gate.py`, `proposal-reviewer.md`). Those are from an earlier run,
and show where the person left off.

A FAIL doesn't stop the walk. Go on to step 2.

### 2. Ask three questions

In one message, ask exactly these three, then stop and wait for the answers:

1. What job do you do every week that you'd like to hand to an agent? (A
   status update, a code review, an invoice, a support reply, a release note.)
2. Which tool are you driving it with: Claude Code, Codex or Kiro?
3. Do you want to read the steps first (`git checkout step-0`) or build
   straight on `main`?

If an answer is missing or vague, ask again for that one. Don't guess the job.

From the job, pick a short kebab-case name (`weekly-status`, `release-notes`)
and use it in every path below. Say the name in the first draft so the person
can change it.

### 3. If they want to read the steps first

Don't check anything out: `skills/start-here/` doesn't exist at `step-0`, and
this conversation would lose its instructions. Instead, for each layer in turn,
run `git diff step-<n-1> step-<n> --stat`, show it, and say in two sentences
what that layer adds and what it fixes (the table in `README.md` has it).
Then tell them they can run `git checkout step-0` themselves to look around,
`git checkout main` to come back, and say "get me started" again to build.

If they'd rather build now, go on to step 4.

### 4. Build the five layers, in order

For each layer: say in one sentence what it's for, draft the files for the
person's job, show the drafts, and ask "Write this?" Write only on a yes. On a
no, say the layer is skipped and offer the next one. Keep a list of every file
you write or edit.

**Layer 1: Instructions.** Draft a new section in `AGENTS.md` headed with the
job, below the proposal rules. Three things only:

- Where the inputs come from, and that the agent never invents them
- Where the output goes, and what it's called
- What the agent never does on its own (send, pay, delete, merge)

Ask for anything you'd have to guess. In Codex it's read as is, in Claude
Code through `CLAUDE.md`, and in Kiro through `.kiro/steering/`, so it's one
edit for all three.

**Layer 2: Skill.** Draft `skills/<job-name>/SKILL.md`, shaped like
`skills/draft-proposal/SKILL.md`: `name` and `description` frontmatter, with
the description saying when to use it; Inputs; numbered Steps; Output. If the
person can't say what the output is, ask until they can. In the same draft,
add a row for it to the Skills table in `AGENTS.md`. Tell them
`python3 -m unittest discover -s tests` now fails if a skill is missing its
frontmatter or its row. Claude Code finds it through the `.claude/skills` link;
Codex and Kiro find it through `AGENTS.md`.

**Layer 3: Gate.** Draft `gates/<job-name>_gate.py`, shaped like
`gates/proposal_gate.py`: standard library only, Python 3.9, one `PASS` or
`FAIL` line per file, each problem named on its own line, exit 1 on any
failure. Check what's cheap to check and expensive to miss: an empty section,
a placeholder, a number that doesn't match its source. In the same draft, show:

- The edit to the last steps of their skill, if Layer 2 was written: run the
  gate, fix what it names, run it again until it passes
- A line in their `AGENTS.md` section, if Layer 1 was written: the job is
  done when the gate passes, and the gate is never edited to make it pass

After writing, suggest they ask the agent to call the job done with the gate
failing, and watch it refuse.

**Layer 4: Hook.** This needs a gate for the job. If Layer 3 was skipped and
no gate for the job exists, say the hook has nothing to run yet and offer
Layer 5. Otherwise draft a diff to `.githooks/pre-commit` that adds a new
numbered block after block 2, in the same style: collect the staged files
matching the job's output path and run the new gate on them with
`|| status=1`. Blocks 1 and 2 stay exactly as they are. If `core.hooksPath`
was FAIL in step 1, repeat the fix, `git config core.hooksPath .githooks`,
and say the hook won't run until they do. To test it, they commit an output
that should fail and watch the commit refuse.

**Layer 5: Review agent.** Draft `agents/<job-name>-reviewer.md`, shaped like
`agents/proposal-reviewer.md`: it reads the output as the person who receives
it, looks for what the gate can't check, reports at most ten findings, and
never edits. In the same draft, add a row to the Agents table in `AGENTS.md`.
If they drive with Claude Code, also draft
`.claude/agents/<job-name>-reviewer.md`, a short pointer like
`.claude/agents/proposal-reviewer.md`. In Codex or Kiro, tell them to run it
as a separate session with the agents file as its instructions.

## Output

Last, in one message:

- Every file written or edited, one per line, with created or edited
- For each gate added, the one command that checks it:
  `python3 gates/<job-name>_gate.py <path to an output>`. If no gate was
  added, say so
- Any FAIL from step 1 still open, with its fix
- The layers skipped, so they know what's left if they run this again
