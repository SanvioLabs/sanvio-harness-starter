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
| Stamps and the phase gate | [`gates/stamp.py`](gates/stamp.py) and [`gates/phase_gate.py`](gates/phase_gate.py), tested in the root [`tests/test_stamp.py`](../../tests/test_stamp.py) |
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

## Ready to send, and ready for Build

A gate that passed yesterday says nothing about today's text. So each check
stamps the proposal with a fingerprint of its text, in a fixed order, on a
`stamps:` line in its frontmatter. An edit below the frontmatter makes every
stamp stale, and they run again in the same order. From the harness root:

```bash
python3 examples/proposal/gates/stamp.py gate examples/proposal/proposals/<file>.md      # runs the gate, stamps on PASS
python3 examples/proposal/gates/stamp.py reviewed examples/proposal/proposals/<file>.md  # your okay on the review
python3 examples/proposal/gates/stamp.py status examples/proposal/proposals/<file>.md    # Ready to send, or what to run again
```

`reviewed` is a person's stamp: you read the reviewer's findings, dealt with
them, and are happy. The agent doesn't stamp it on its own.

Before the work enters Build, ask the phase gate what's missing:

```bash
python3 examples/proposal/gates/phase_gate.py build juniper-bakery
```

It names each gap and what closes it, and stops there. Ask your agent "can
juniper-bakery enter Build?" and it runs the gate, runs what each gap names in
order, and runs the gate again. The client's signature is a `signed:` line you
add to the frontmatter once they've signed. No skill closes that one, and the
gate never moves the phase on for you.

## Try it

Ask your agent: "follow [`examples/proposal/skills/draft-proposal/SKILL.md`](skills/draft-proposal/SKILL.md) and
draft a proposal for a client of your choosing". Then try to break it: ask it
to call the proposal done with a placeholder left in, or to commit one.

## Make it yours

Don't edit this folder into your own job. Leave it as the reference, and build
your job at the root: `skills/<job>/`, `gates/<job>_gate.py`, a brief in
[`agents/`](agents/). `/orientation` walks you through it, one layer at a time.
