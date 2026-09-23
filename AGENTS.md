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

## Done means the gate passes

A proposal is done when this passes:

```bash
python3 gates/proposal_gate.py proposals/<file>.md
```

Run it and show the output. Never say a proposal is done, ready or finished
while the gate fails, and never edit the gate to make a proposal pass.
