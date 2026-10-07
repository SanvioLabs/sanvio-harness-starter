---
name: learn
description: Turn a mistake the agent just made into a written rule, in the file that governs it, so the next session doesn't repeat it. Use when someone says "learn from that", "don't do that again", "remember this", "write that down", "make that a rule", or corrects the agent and wants the correction to stick.
---

# Learn from a mistake

A correction you only said out loud hasn't happened. The next session never
heard it. This skill writes it down, in the one place that governs that
behaviour, with the date and the reason, so it holds next time.

You draft. The person says yes or no. Nothing gets written without a yes.

## Inputs

What went wrong, in one sentence, and what should have happened instead. If the
person hasn't said both, ask, in one message. Don't guess what the right
behaviour was.

## Steps

1. **Say the mistake back** in one line: what the agent did, and what it
   should have done.
2. **Pick the one file that governs it.** Strongest first, and stop at the
   first that fits:

   | If | It goes in |
   |---|---|
   | It must hold even when the agent decides otherwise, and a script can check it | A gate in `gates/`, with a test in `tests/`, run where `steering/gates.md` says: the hook for a fast check, CI for a slow one (`gates/README.md` has how to write it) |
   | It's one step of a procedure that a skill already runs | That skill's `SKILL.md`, as a step or a line in its Rules |
   | It's about the company: what you sell, how you sound, what you won't do | `company/COMPANY.md` |
   | It's where to find something, or how to reach it | `company/DATA.md` |
   | It's about how you work on a topic a steering file covers: replies, writing, data and tools, setup, models, gates | That file in `steering/` |
   | It's a standing rule for any work in this repo | `AGENTS.md`, under the section it belongs to |

   If a rule that covers it already exists and the agent broke it anyway, the
   rule isn't strong enough where it is. Say so, and move it one row up rather
   than writing it twice.
3. **Look for a copy.** Search the repo for the same rule in other words. One
   copy only. If you find one, edit that one instead of adding another.
4. **Draft the smallest change.** One rule, stated as what to do. Add a dated
   reason on the line below it: `Learned YYYY-MM-DD: <what went wrong>.` For a
   gate, draft the check and a test that fails without it.
5. **Show the draft** as a diff and ask "Write this?" Write only on a yes.
6. **Prove it.** If you changed a gate or a skill, run
   `python3 -m unittest discover -s tests` and paste the result. If you changed
   a gate, run it on the file that went wrong and show it fail.

## Rules

- One mistake, one rule. Don't tidy the rest of the file while you're there.
- Never weaken or remove a check to make the mistake go away. The rule is about
  the behaviour, not about the check that caught it.
- Never write a rule that names a customer, a person outside the company, or a
  secret. Describe the kind of thing instead.
- If the person says it was a one-off and needs no rule, stop. Not every
  mistake is a pattern.

## Output

The file changed, the rule as written, and the test or gate output from step 6
if there was one.
