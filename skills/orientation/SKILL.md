---
name: orientation
description: Get someone ready to use this harness. Checks the clone, asks what job they want to hand to an agent, which tool they drive it with and where their company's data lives, maps how the agent can reach that data, then walks them through the five layers around their job, one drafted file at a time. Use when someone runs /orientation, says "get me started", "orient me", "how do I use this", "new here", "set this up for my job", or asks where to begin.
---

# Orientation

The person has just cloned this repo. Show them the harness working on them:
check their setup, find out what they do and where their company's data lives,
then build the five layers around their job one at a time. Instructions, a
skill, a gate, the hook, a review agent.

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
- Never add, log in to or configure a connector or MCP server, and never ask
  for, read or print a token, key or password. Name the setup step in their
  tool and let them do it.
- Record where company data lives, never what's in it. Don't copy company data
  into the repo to look at it, and don't quote it back into a file.
- A no skips that step or layer and offers the next one. It doesn't end the
  conversation.
- If a request needs a tool-specific hook (`.claude/settings.json`, a Codex or
  Kiro hook) or a change to `gates/proposal_gate.py`, stop and say it's outside
  this skill. The in-loop hook is the last bonus in `EXERCISES.md`.

## Steps

### 1. Check the clone

Read-only. Run both and report what they print:

```bash
python3 scripts/check_setup.py
python3 -m unittest discover -s tests
```

`check_setup.py` prints one `PASS`, `WARN` or `FAIL` line per item with the fix
under it: Python version, whether the hook is switched on, whether the
`CLAUDE.md`, `.claude/skills` and Kiro links work, where `origin` points, and
whether the example proposal passes its gate. Pass its lines through as
printed. For the tests, one line: passed, or the names that failed.

Say these out loud when they show up:

- **Hook FAIL.** Every check in the hook silently does nothing until they run
  the fix. Don't run it for them.
- **Remote WARN on the public starter.** Before anything company-specific goes
  in (rules, data locations, their own job), they need their own private copy.
  On GitHub that's *Use this template* with the visibility set to private, then
  clone that. If `gh` is installed and `origin` is on GitHub, run
  `gh repo view --json visibility -q .visibility` and say what it returns.
  Hold step 4's write until the answer is private or there's no remote.
- **Gate or tests FAIL.** On a clean clone of `main` these pass, so suggest
  `git status` to look for local changes.

Then list any files in `skills/`, `gates/` and `agents/` beyond the ones this
repo ships (`draft-proposal`, `review-skill`, `orientation`,
`proposal_gate.py`, `proposal-reviewer.md`), and any "Where company data
lives" section already in `AGENTS.md`. Those are from an earlier run and show
where the person left off. Skip the questions they've already answered.

A FAIL doesn't stop the walk. Go on to step 2.

### 2. Ask three questions

In one message, ask exactly these three, then stop and wait for the answers:

1. What job do you do every week that you'd like to hand to an agent? (A
   status update, a code review, an invoice, a support reply, a release note.)
2. Which tool are you driving it with (Claude Code, Codex or Kiro), and is it
   on a personal plan or one your company manages?
3. Where does the company information that job needs live? Docs (Google
   Drive, Notion, Confluence, SharePoint), chat (Slack, Teams), tickets (Jira,
   Linear, GitHub), a CRM, a database, a code repo, files on your laptop.

If an answer is missing or vague, ask again for that one. Don't guess the job,
and don't guess where the data is.

From the job, pick a short kebab-case name (`weekly-status`, `release-notes`)
and use it in every path below. Say the name in the first draft so the person
can change it.

### 3. Map how the agent reaches each source

For each place they named in question 3, work out how the agent gets at it.
Start with what you can actually see: list the connectors and MCP servers
available to you in this session, by name only. Never show their config. Then
sort each source into one of four:

| Reach | Means | What to tell them |
|---|---|---|
| **Connected** | A connector or MCP server for it is live in this session | Nothing to do. Say which one |
| **Connectable** | A connector exists for it but isn't set up here | Where to add it in their tool: `/mcp` and `claude mcp add` in Claude Code, `codex mcp add` in Codex, the MCP settings in Kiro. Point at the tool's own docs and the vendor's official server. Connect read-only where it offers that |
| **Export** | No connector, but files can be exported | Put exports in `local-data/`, which is gitignored, and never commit them |
| **By hand** | None of the above | They paste what a task needs into the conversation, each time |

Then ask two things, once, for the whole list:

- **Is it cleared for this tool?** Company data reaching an AI tool is the
  company's call, and the plan matters: a personal plan can leave training on
  your data to a setting, where a business, enterprise or API plan usually
  rules it out by contract. If they don't know, mark the source `unconfirmed`
  and say not to connect anything sensitive until someone who owns that
  decision says yes.
- **Is anything off-limits outright?** Customer personal data, health or
  payment details, credentials. Those stay out of the agent's reach whatever
  the plan, and out of the repo whatever happens.

A connector that can write (send email, edit a doc, post a message) goes on the
list of things the agent never does on its own in layer 1.

### 4. Write down where the data lives

Only once step 1's remote check is private or there's no remote. If it's still
the public starter, say so, show the draft, and hold the write.

Draft a new section in `AGENTS.md`, below the proposal rules:

```markdown
## Where company data lives

| Source | What's there | How you reach it | Cleared for this tool |
|---|---|---|---|
| Google Drive, "Clients" folder | Signed proposals, briefs | Google Drive connector, read-only | yes |
| Billing system | Hours logged per client | CSV export into `local-data/` | unconfirmed |

- Read it where it lives. Never copy its contents into a tracked file.
- Exports go in `local-data/` and are never committed.
- Never use a source marked `unconfirmed`, or anything off-limits, until a human
  says so in this session.
- Never write to any of these without a human saying so in this session.
```

Fill it from the person's answers, not the example rows. Write on a yes.

Mention once that this is the one part of orientation every session will use:
the next agent that opens the repo knows where to look without asking.

### 5. If they want to see the layers first

Offer it in one line: each layer is a tag, and `git diff step-1 step-2` shows
exactly what one adds. If they want the tour, run
`git diff step-<n-1> step-<n> --stat` for each layer in turn, show it, and say
in two sentences what that layer adds and what it fixes (the table in
`README.md` has it). Don't check anything out: `skills/orientation/` doesn't
exist at `step-0`, and this conversation would lose its instructions.

If they'd rather build now, go on to step 6.

### 6. Build the five layers, in order

For each layer: say in one sentence what it's for, draft the files for the
person's job, show the drafts, and ask "Write this?" Write only on a yes. On a
no, say the layer is skipped and offer the next one. Keep a list of every file
you write or edit.

**Layer 1: Instructions.** Draft a new section in `AGENTS.md` headed with the
job, below the proposal rules. Three things only:

- Where the inputs come from, naming sources from "Where company data lives"
  if step 4 wrote it, and that the agent never invents them
- Where the output goes, and what it's called
- What the agent never does on its own (send, pay, delete, merge, and anything
  a connector from step 3 can write)

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
`|| status=1`. Blocks 1 and 2 stay exactly as they are. If the hook was FAIL in
step 1, repeat the fix, `git config core.hooksPath .githooks`, and say the hook
won't run until they do. To test it, they commit an output that should fail and
watch the commit refuse.

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
- Each data source, with how the agent reaches it and whether it's cleared,
  and any source still `unconfirmed` or still to connect
- For each gate added, the one command that checks it:
  `python3 gates/<job-name>_gate.py <path to an output>`. If no gate was
  added, say so
- Any FAIL or WARN from step 1 still open, with its fix
- The steps and layers skipped, so they know what's left if they run this
  again
