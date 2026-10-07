# Model selection

Read this when deciding what runs on which model, or before sending work to a
subagent.

## The main session decides, subagents read

The main session holds the conversation, makes the judgement calls and hands
work out. Subagents do the reading, searching and structured reporting, and
hand back a report.

Before a long read or a broad sweep across files, ask whether it should be a
subagent. The reason isn't only cost. A subagent that reads 300 pages returns
one, and the 300 never enter the main session's context, where they'd crowd out
everything else for the rest of the session.

## Three tiers

| Tier | Gets | Why |
|---|---|---|
| **Strongest model**, the main session | Decisions, anything legal, pricing, anything a customer reads, writing in the company's voice, secret scanning | A miss here is silent, and nothing downstream catches it |
| **Mid tier** | Structured analysis and reports where a miss is recoverable: audits, reviews, summaries | It can be re-run, and a person reads the output before using it |
| **Smallest model** | Search, existence checks, listing and sweeping files | Reads a lot, decides almost nothing |

Never send to a cheaper tier: legal review, pricing, anything going to a
customer, voice-sensitive writing, or a secret scan. Secret scanning looks like
an obvious candidate for a small model, and a missed live credential can't be
fixed by re-running on a better one.

## Where the model is set

Skills run on whatever model the session uses. You pin a model on a subagent:
in Claude Code, in the `model:` field of `.claude/agents/<name>.md`, or per
call. Each tool has its own place for this; check its docs.

## Don't switch the main session's model to save money

Prompt caches belong to one model. Switching mid-session pays for the whole
conversation again, uncached, which usually costs more than it saves. Send the
cheap work to a cheaper subagent instead.

## Why the floor is high

If nobody reviews the output before it reaches a customer, the model is the
quality floor, not a first draft. Anything that leaves your control runs on the
strongest model you have.
