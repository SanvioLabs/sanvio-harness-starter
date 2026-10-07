# How to work in this repo

This repo drafts client proposals. You draft. A human reviews and sends.

## Who you work for

Before any company work, read `company/COMPANY.md` and `company/DATA.md` if
they exist. The first says who the company is and what it won't do. The second
says where its data lives and how you reach it. Never invent a fact about the
company: if a section is empty or a file is missing, ask, or suggest
`/orientation`. Both files are gitignored, so never quote them into a tracked
file.

## Rules

- Rates come from `data/rates.json` and nowhere else. Never invent a rate and
  never discount unless a human tells you to in this session.
- Every proposal starts from `templates/proposal.md` and is saved as
  `proposals/<client-name-in-kebab-case>.md`.
- Leave no `{{placeholder}}` in a finished proposal. If you don't know
  something, ask. Don't guess, and don't fill it with something plausible.
- Never send, email or publish anything. A connector that can send, edit,
  delete or share does so only when a human says yes to that one call.
- Never read, write or print a credential, a key or a `.env` file.
- `proposals/juniper-bakery.md` is a finished example. Match its shape.

## Skills

Skills are procedures. When a request matches one, read it and follow its
steps in order.

| Skill | Use when |
|---|---|
| `skills/draft-proposal/SKILL.md` | Asked to write, draft or price a proposal |
| `skills/review-skill/SKILL.md` | Asked to install, add, try or review a skill from outside this repo |
| `skills/learn/SKILL.md` | The agent got something wrong and the person wants it to stick: "learn from that", "don't do that again", "make that a rule" |
| `skills/orientation/SKILL.md` | Someone runs `/orientation`, is new here, asks how to use this, says "get me started", or wants it set up for their own job and their company's data |

## Done means the gate passes

A proposal is done when this passes:

```bash
python3 gates/proposal_gate.py proposals/<file>.md
```

Run it and show the output. Never say a proposal is done, ready or finished
while the gate fails, and never edit the gate to make a proposal pass.

The same gate runs in `.githooks/pre-commit`, along with a check for secrets.
If a commit is blocked, fix what it names. Never commit with `--no-verify`.

In Claude Code, `.claude/hooks/guard.py` also runs before every tool call: it
refuses credential files and asks the human before any connector changes
something. If it refuses, don't look for another way to do the same thing. Say
what you needed and ask.

## Agents

After the gate passes, hand the proposal to a reviewer before a human sees it.

| Agent | Does |
|---|---|
| `agents/proposal-reviewer.md` | Reads a proposal as the client would and reports what's unclear. Never edits |

In Claude Code it runs as the `proposal-reviewer` subagent. In other tools, run
it as a separate session with that file as its instructions.
