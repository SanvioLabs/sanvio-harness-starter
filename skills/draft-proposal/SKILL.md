---
name: draft-proposal
description: Draft a client proposal from the template and price it from the rate card. Use when asked to write, draft or price a proposal.
---

# Draft a proposal

## Inputs

You need all five before you write anything. Ask for whatever is missing, in one
message:

1. Client name
2. The problem, in the client's words
3. What's in scope
4. What's out of scope
5. Hours per role, using only the roles in `data/rates.json`

## Steps

1. Copy `templates/proposal.md` to `proposals/<client-name-in-kebab-case>.md`.
2. Fill every section from the inputs. Write it the way you'd say it to the
   client across a table: short, specific, no filler.
3. For each fee row, take the rate from `data/rates.json` and compute
   amount = hours x rate. Write money as `$1,750`.
4. Add the amounts for the total. If it's under `minimum_fee`, stop and tell
   the human rather than padding the hours.
5. Run `python3 gates/proposal_gate.py proposals/<file>.md`.
6. Fix what it names and run it again until it passes.

## Output

The path of the proposal and the gate's output, pasted as it printed. Nothing
else.
