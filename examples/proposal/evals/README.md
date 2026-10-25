# Golden examples for the reviewer

Ten invented proposals, each a variant of [`../proposals/juniper-bakery.md`](../proposals/juniper-bakery.md), and what a good
review of each looks like. [`scripts/eval_agents.py`](../../../scripts/eval_agents.py) runs the reviewer on them and says which it
still gets right.

## What it is for

The reviewer is prompt text, and a change to it can make it worse without anything
failing. These cases are a fixed set of known answers to check it against.

| Cases | Plant | The reviewer should |
|---|---|---|
| `01` | A promise nobody meant: unlimited revisions | Quote it |
| `02` | Photos in Scope, none in Out of scope | Quote the photos |
| `03` | A point-of-sale link that isn't in Assumptions | Quote it |
| `04` | An internal name, `Hermes`, the client can't know | Quote it |
| `05` | A Problem section that states the solution | Quote it |
| `06` | "Running smoothly after launch", which reads as support | Quote it |
| `07` | Two acronyms the client may not know, `MVP` and `UAT` | Quote `UAT`. `MVP` is common enough that a review may let it pass |
| `08`, `09` | Nothing wrong | Report at most one finding |
| `10` | A `TBD` that [`proposal_gate.py`](../gates/proposal_gate.py) already catches | Not repeat it |

Cases `01` to `09` pass the gate. `10` fails it, on purpose.

Each case's `case.json` has the agent, the brief, `must_find` (texts a finding must
quote), `must_not_flag`, `max_findings`, and optionally a `verdict`. Every `must_find`
text appears once in its `work.md`.

## When to run it

After you change [`agents/reviewer.md`](../../../agents/reviewer.md), the [proposal reviewer brief](../agents/proposal-reviewer.md), or the model
the reviewer runs on. Not on every commit: it starts real agent sessions.

## What it costs

Two sessions per case by default, so twenty for a run of ten. Each reads one page.
The summary line gives the tokens and seconds it used.

## How to run it

From the harness root:

```
python3 scripts/eval_agents.py examples/proposal/evals --save ~/before.json
```

That runs `claude -p`, held to read tools like the loop's readers. Use `--agent` for
another: `codex`, or a command line that reads the prompt on standard input and can
read files. The agent is given the work's path, not its text, so `ollama:MODEL`, which
can't read files, fails every case. Only `claude` is held to read tools: anything else
runs with its own permissions, and the checkout check catches only what it changes. Each case prints as:

- **STABLE**: every run passed
- **FLAKY**: some did, so the reviewer sometimes misses it
- **FAILING**: none did

A run fails if the reply misses a `must_find` text, quotes a `must_not_flag` one, has
more than `max_findings` findings, or if the agent changed anything in the checkout.
A finding is a block starting at a `**Where:**` line, so a reply in another format
counts as no findings.

To compare a change with before it, save a run before you edit, then run again with it:

```
python3 scripts/eval_agents.py examples/proposal/evals --baseline ~/before.json
```

It lists the cases whose status changed, such as `01-unlimited-revisions: stable -> failing`.
Keep the saved file outside the repo: it holds one person's run on one model.
