# Exercises

Work in pairs. Pick a job one of you does every week: a status update, a code
review, an invoice, a support reply, a release note. Then build the five layers
around it, in this repo or a copy of it.

## 1. Write the instructions file (10 min)

Rewrite `AGENTS.md` for your job. Three things only:

- Where the inputs come from, and that the agent never invents them
- Where the output goes, and what it's called
- What the agent never does on its own (send, pay, delete, merge)

Test it: ask your agent to do the job and watch what it gets wrong. Every
mistake is a line you're missing.

## 2. Turn the job into a skill (10 min)

Copy `skills/draft-proposal/` and rewrite it for your job. A skill has a name,
a description that says when to use it, numbered steps, and a defined output.
If you can't say what the output is, it isn't a skill yet.

## 3. Write a gate that blocks (10 min)

Write a script that exits non-zero when the output isn't ready. Check the things
that are cheap to check and expensive to miss: an empty section, a placeholder,
a number that doesn't match its source. `gates/proposal_gate.py` is the pattern.

Then try to break it. Ask the agent to mark the job done with the gate failing.

## 4. Wire it into the hook (5 min)

Add your gate to `.githooks/pre-commit`. Run `git config core.hooksPath .githooks`
if you haven't. Commit something that should fail and watch it refuse.

## 5. Add one agent (if you have time)

Copy `agents/proposal-reviewer.md` and point it at your output. Give it a
different job from the one that wrote the thing: read it as the person who
receives it. It reports and never edits.

## Bonus: borrow a skill safely

Pick one skill from `mattpocock/skills` or `obra/superpowers` and ask your agent
to review it with `skills/review-skill/`. What did it find that you already had?
What gap did it fill? Did anything get flagged?

## Bonus: a hook inside the agent loop

The git hook runs at commit. Claude Code, Codex and Kiro each have their own
hooks that run before or after the agent calls a tool, so a check can fire the
moment a file is written instead of at commit. Pick your tool, find its hook
docs, and run your gate after every file write.

## Questions to bring back to the room

- What did your agent get wrong that you'd never have thought to write down?
- What did your gate catch?
- What would you never let an agent do unattended?
