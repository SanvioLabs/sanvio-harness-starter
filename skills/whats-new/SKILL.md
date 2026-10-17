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
   mkdir -p "${TMPDIR:-/tmp}/whats-new" && curl -fsSL https://raw.githubusercontent.com/SanvioLabs/sanvio-harness-starter/main/CHANGELOG.md -o "${TMPDIR:-/tmp}/whats-new/CHANGELOG.md"
   ```

   This works the same in a clone and in a downloaded copy. If it fails
   (offline, no `curl`), say the starter couldn't be read and report from the
   local log only.
3. **List the entries with a command, not by reading.** Several entries can
   share a date, and a long log is easy to miscount by eye, so let the shell
   make the list and answer from it.
   - "What's new" or "am I up to date": the headings in the starter's log that
     aren't in theirs, in the starter's order, newest first. A heading only in
     theirs is their own change, not something missing.

     ```bash
     grep '^## ' "${TMPDIR:-/tmp}/whats-new/CHANGELOG.md" | grep -vxF -f <(grep '^## ' CHANGELOG.md 2>/dev/null)
     ```

   - "What changed since <date>" or "lately": the headings in their own log
     dated on or after that day (`YYYY-MM-DD`; for "lately", the last 14 days).

     ```bash
     grep '^## ' CHANGELOG.md | awk -v d=2026-10-12 'substr($2, 1, 10) >= d'
     ```
4. **Answer what was asked,** from that list. Say how many entries it has and
   give every one of them. If it's empty for "what's new", say they're up to
   date and show the latest three entries they do have. For a date, say "on or
   after" so the reader knows the day itself is included.
5. **For each entry**, give the name, one line on what it adds, and its
   **Do:** line as written. If they want to take it, show what would change
   first, for the files the entry names. To tell a clone from a download, run
   `git rev-parse --is-inside-work-tree` in the copy's root.

   - **It succeeds (a clone):**

     ```bash
     git fetch --quiet https://github.com/SanvioLabs/sanvio-harness-starter main
     git diff HEAD FETCH_HEAD --stat -- <files>
     ```

     The command that takes a file is `git checkout FETCH_HEAD -- <file>`.
   - **It fails (a download):** for each file,

     ```bash
     mkdir -p "$(dirname "${TMPDIR:-/tmp}/whats-new/<file>")" && curl -fsSL https://raw.githubusercontent.com/SanvioLabs/sanvio-harness-starter/main/<file> -o "${TMPDIR:-/tmp}/whats-new/<file>"
     diff -u <file> "${TMPDIR:-/tmp}/whats-new/<file>"
     ```

     The command that takes a file is
     `cp "${TMPDIR:-/tmp}/whats-new/<file>" <file>`.

   Name that command, and say what it costs: it replaces their copy, so any
   edit they made to that file is gone. For a file they've changed, offer to
   show the diff and merge the starter's change in by hand, one file at a time,
   on a yes.

## Rules

- Never pull, merge, check out, copy or commit, and never offer to. Name the
  command and let the person run it. A bare "say the word and I'll merge" is
  the thing this rule is for.
- Never suggest `git pull`, `git merge` or `git init` to take the starter's
  changes. A copy made with *Use this template* shares no history with the
  starter, so a merge either refuses or tries to merge everything, and a
  downloaded copy doesn't need git at all. The way in is one file at a time,
  with the commands in step 5.
- Quote the **Do:** line as written. Don't add steps it doesn't have.
- Every entry on the list is in the answer, and the count you give is the
  list's length. To be brief, shorten each line, never drop an entry.
- Never call a copy up to date when step 2 failed. Say the starter couldn't be
  read.

## Output

The entries new to them, each with what it adds and what to do, or that
they're up to date. Then, if they're behind, the one command that shows what
would change. End there: the next step is theirs to run.
