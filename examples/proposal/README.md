# Example: drafting a client proposal

One job, wrapped in all five layers, for you to read and copy. A proposal is
where the cheap mistakes live: a placeholder left in, a rate somebody made up,
a total that doesn't add up. None are hard. All of them ship anyway when the
process lives in your head.

| Layer | Here |
|---|---|
| Inputs | [`data/rates.json`](data/rates.json), [`templates/proposal.md`](templates/proposal.md), and one finished proposal in [`proposals/`](proposals/) |
| Instructions | The rules below |
| Skill | [`skills/draft-proposal/SKILL.md`](skills/draft-proposal/SKILL.md) |
| Gate | [`gates/proposal_gate.py`](gates/proposal_gate.py), tested in the root [`tests/test_gate.py`](../../tests/test_gate.py) |
| Hook | Block 2 of the root [`.githooks/pre-commit`](../../.githooks/pre-commit) |
| Review brief | [`agents/proposal-reviewer.md`](agents/proposal-reviewer.md), read by the root `reviewer` agent |

Paths below are relative to this folder.

## Rules for this job

- Rates come from [`data/rates.json`](data/rates.json) and nowhere else. Never invent a rate and
  never discount unless a human tells you to in this session.
- Every proposal starts from [`templates/proposal.md`](templates/proposal.md) and is saved as
  `proposals/<client-name-in-kebab-case>.md`.
- Leave no `{{placeholder}}` in a finished proposal. If you don't know
  something, ask. Don't guess, and don't fill it with something plausible.
- [`proposals/juniper-bakery.md`](proposals/juniper-bakery.md) is a finished example. Match its shape.
- A proposal is done when this passes, run from the harness root:

  ```bash
  python3 examples/proposal/gates/proposal_gate.py examples/proposal/proposals/<file>.md
  ```

## Try it

Ask your agent: "follow [`examples/proposal/skills/draft-proposal/SKILL.md`](skills/draft-proposal/SKILL.md) and
draft a proposal for a client of your choosing". Then try to break it: ask it
to call the proposal done with a placeholder left in, or to commit one.

## Make it yours

Don't edit this folder into your own job. Leave it as the reference, and build
your job at the root: `skills/<job>/`, `gates/<job>_gate.py`, a brief in
[`agents/`](agents/). `/orientation` walks you through it, one layer at a time.
