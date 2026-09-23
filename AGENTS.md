# How to work in this repo

This repo drafts client proposals. You draft. A human reviews and sends.

## Rules

- Rates come from `data/rates.json` and nowhere else. Never invent a rate and
  never discount unless a human tells you to in this session.
- Every proposal starts from `templates/proposal.md` and is saved as
  `proposals/<client-name-in-kebab-case>.md`.
- Leave no `{{placeholder}}` in a finished proposal. If you don't know
  something, ask. Don't guess, and don't fill it with something plausible.
- Never send, email or publish anything.
- Never read, write or print a credential, a key or a `.env` file.
- `proposals/juniper-bakery.md` is a finished example. Match its shape.

## Skills

Skills are procedures. When a request matches one, read it and follow its
steps in order.

| Skill | Use when |
|---|---|
| `skills/draft-proposal/SKILL.md` | Asked to write, draft or price a proposal |
| `skills/review-skill/SKILL.md` | Asked to install, add, try or review a skill from outside this repo |

## Done means the gate passes

A proposal is done when this passes:

```bash
python3 gates/proposal_gate.py proposals/<file>.md
```

Run it and show the output. Never say a proposal is done, ready or finished
while the gate fails, and never edit the gate to make a proposal pass.

The same gate runs in `.githooks/pre-commit`, along with a check for secrets.
If a commit is blocked, fix what it names. Never commit with `--no-verify`.

## Agents

After the gate passes, hand the proposal to a reviewer before a human sees it.

| Agent | Does |
|---|---|
| `agents/proposal-reviewer.md` | Reads a proposal as the client would and reports what's unclear. Never edits |

In Claude Code it runs as the `proposal-reviewer` subagent. In other tools, run
it as a separate session with that file as its instructions.
