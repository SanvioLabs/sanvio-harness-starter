---
name: whats-new
description: Say what's changed in this harness, and what the public starter has that this copy doesn't yet, from CHANGELOG.md, with what to do to take each one. Reports only, never pulls, merges or copies files. Use when someone asks "what's new", "what changed", "anything new in the starter", "am I up to date", "what did I miss", or "what's changed since <date>".
license: MIT. From the Sanvio Labs harness starter, https://github.com/SanvioLabs/sanvio-harness-starter
---

# What's new

[`CHANGELOG.md`](../../CHANGELOG.md) is the release log: newest first, one entry per change, each
with a dated heading, the files it touched and a **Do:** line. This skill reads
it, and the starter's copy, and tells the person what's new for them.

## Steps

1. **Read [`CHANGELOG.md`](../../CHANGELOG.md) here.** If it's missing, this copy predates it, and
   everything in the starter's log is new to them.
2. **Read the starter's.** Say first that this reads the public starter and
   changes nothing in their files. Then:

   ```bash
   git fetch --quiet https://github.com/SanvioLabs/sanvio-harness-starter main
   git show FETCH_HEAD:CHANGELOG.md
   ```

   If it fails (offline, no git), say so and report from the local log only.
3. **Compare by heading, not by date.** Several entries can share a date. An
   entry is new to them when its heading (`## <date>: <name>`) is in the
   starter's log and not in theirs. A heading only in theirs is their own
   change, not something missing.
4. **Answer what was asked.**
   - "What's new" or "am I up to date": the entries they don't have, newest
     first. If there are none, say they're up to date and show the latest
     three entries they do have.
   - "What changed since <date>" or "lately": entries in their own log from
     that date on.
5. **For each entry**, give the name, one line on what it adds, and its
   **Do:** line as written. If they want to take it, show what would change
   first, for the files the entry names:

   ```bash
   git diff HEAD FETCH_HEAD --stat -- <files>
   ```

   Then name the command that takes a file, and say what it costs:
   `git checkout FETCH_HEAD -- <file>` replaces their copy, so any edit they
   made to that file is gone. For a file they've changed, offer to show the
   diff and merge the starter's change in by hand, one file at a time, on a
   yes.

## Rules

- Never pull, merge, check out, copy or commit, and never offer to. Name the
  command and let the person run it. A bare "say the word and I'll merge" is
  the thing this rule is for.
- Never suggest `git pull` or `git merge` to take the starter's changes. A
  copy made with *Use this template* shares no history with the starter, so a
  merge either refuses or tries to merge everything. The way in is one file at
  a time, with the commands in step 5.
- Quote the **Do:** line as written. Don't add steps it doesn't have.
- Never call a copy up to date when step 2 failed. Say the starter couldn't be
  read.

## Output

The entries new to them, each with what it adds and what to do, or that
they're up to date. Then, if they're behind, the one command that shows what
would change. End there: the next step is theirs to run.
