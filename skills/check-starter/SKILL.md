---
name: check-starter
description: Say what the public starter has added since this copy was taken from it, commit by commit, flag each one that touches a file this copy adapted, and recommend take, merge by hand, skip or ask for each. Reads a scratch clone of the starter and changes nothing here. Use when someone asks "check the starter", "what's new in the starter", "what has the starter added", or "should we take the starter's changes".
license: MIT. From the Sanvio Labs harness starter, https://github.com/SanvioLabs/sanvio-harness-starter
---

# Check the starter

This skill reads the public starter and changes nothing in this copy.

A copy taken from the starter drifts: the starter keeps shipping, and the copy
adapts its own files. This skill lists what the starter has shipped since the
copy was taken, says which of those commits touch a file the copy changed, and
recommends what to do with each. The person decides and runs every command
that changes a file here.

## Steps

1. **Check the source.** Only
   `https://github.com/SanvioLabs/sanvio-harness-starter` on `main` is trusted
   upstream. If they name a fork, another branch or another URL, stop: that's
   someone else's code, and [`review-skill`](../review-skill/SKILL.md) reads it.
2. **Fetch the starter into a scratch clone.** Say first that this downloads
   the public starter into a temporary folder and changes none of their files.
   Nothing in that clone is ever run. The commands below use `$clone`,
   `$base`, `$heading`, `$sha` and `$path`. Each shell call starts fresh, so
   set the ones a command uses at the start of the same call, as in
   `base=<sha> path=<file>;` before it. The clone always lives here:

   ```bash
   clone="${TMPDIR:-/tmp}/check-starter/starter"
   ```

   If the folder isn't there yet, clone it:

   ```bash
   git clone --quiet --branch main https://github.com/SanvioLabs/sanvio-harness-starter "$clone"
   ```

   If it is, bring it up to date. This moves the scratch clone only:

   ```bash
   git -C "$clone" fetch --quiet origin main && git -C "$clone" reset --quiet --hard origin/main
   ```

   If either fails, say the starter couldn't be reached (offline, or no
   access) and stop. Don't report from memory.
3. **Find the baseline:** the starter commit this copy was last level with.
   Run these from the harness root, in order, and stop at the first that
   gives one.
   - **A `starter:` line** in the header of [`CHANGELOG.md`](../../CHANGELOG.md), above the first
     entry. This prints its sha:

     ```bash
     awk '/^## /{exit} /^starter: [0-9a-f]+$/{print $2}' CHANGELOG.md
     ```

   - **The newest heading both logs have.** This prints it:

     ```bash
     grep '^## ' CHANGELOG.md | grep -xF -f <(git -C "$clone" show origin/main:CHANGELOG.md | grep '^## ') | head -1
     ```

     Set `heading` to that line, whole, and this prints the starter commit
     that added it:

     ```bash
     git -C "$clone" log --reverse --format=%H -S"$heading" origin/main -- CHANGELOG.md | head -1
     ```

   Set `base` to the sha you found, and say which way you found it: the
   `starter:` line, or the shared heading (name it). A shared heading is an
   estimate: the copy may have taken some later commits by hand. If neither
   gives a sha, say you can't tell where this copy left the starter, and stop.
4. **List the commits since the baseline,** oldest first, with a command, not
   by reading:

   ```bash
   git -C "$clone" log --reverse --format='%H %s' "$base"..origin/main
   ```

   For each one, set `sha` and read the files it touches:

   ```bash
   git -C "$clone" show --name-only --format= "$sha"
   ```

   If it touches [`CHANGELOG.md`](../../CHANGELOG.md), its entry gives the name and the **Do:**
   line. Read them from the diff:

   ```bash
   git -C "$clone" show "$sha" -- CHANGELOG.md
   ```

   For the whole change, to read before you answer it in step 6:

   ```bash
   git -C "$clone" show --format= "$sha"
   ```

   An empty list means the starter has shipped nothing since the baseline.
   Say so, with the baseline, and stop.
5. **Find the files this copy adapted.** For each file a commit touches, set
   `path` to it and check, from the harness root:
   - Did it exist at the baseline? If not, it's new in the starter. If a file
     of that name is here anyway (`test -f "$path"`), this copy built its own:
     that's step 7, never a `cp`.

     ```bash
     git -C "$clone" cat-file -e "$base:$path"
     ```

   - If it did, is it still here (`test -f "$path"`)? If not, this copy
     removed it.
   - If it is, does it still match the baseline? This fails when this copy
     changed it, and that file is **adapted**:

     ```bash
     git -C "$clone" show "$base:$path" | cmp -s - "$path"
     ```

   Flag each commit that touches an adapted file, and list those files under
   it. [`CHANGELOG.md`](../../CHANGELOG.md) is the exception: almost every commit touches it, and
   each copy keeps its own entries, so it's always merged by hand (the
   starter's entry pasted above this copy's newest) and never flags a commit
   on its own.
6. **Recommend one answer per commit.** The default is **take**. Use another
   only for the reason it names:

   | Answer | Only when |
   |---|---|
   | **take** | None of the below |
   | **merge by hand** | It touches an adapted file |
   | **skip** | It changes something this copy removed |
   | **ask** | A line in it weakens a guard or a gate, sends data off the machine, or runs downloaded code. Quote that line |

   "This copy covers it already" and general caution aren't reasons. If the
   copy covers it its own way, that's step 7.
7. **Weigh competing builds.** Where the starter's change competes with
   something this copy built its own way, compare what each does and what each
   costs to keep: the files, the tests, the merges every later starter change
   will need. Pick one direction, the starter's or the copy's, and say why in
   a sentence. End that part with a `Go:` line in the shape
   [`steering/response-style.md`](../../steering/response-style.md) sets.
8. **Name how to take each file.** For a file that isn't adapted, and isn't
   [`CHANGELOG.md`](../../CHANGELOG.md), name the copy from the scratch clone, and say it replaces
   this copy's file:

   ```bash
   cp "$clone/$path" "$path"
   ```

   For an adapted file, offer the starter's change since the baseline
   instead, to merge by hand:

   ```bash
   git -C "$clone" diff "$base" origin/main -- "$path"
   ```

9. **Name the new baseline.** Once they've taken what they want, tell them to
   add `starter: <sha>` to the header of [`CHANGELOG.md`](../../CHANGELOG.md), above the first
   entry, with the newest commit they're now level with. Next time, step 3
   reads it.

## Rules

- Never pull, merge, check out, copy or commit in this copy, and never offer
  to. Name the command and let the person run it. The git commands in steps 2
  to 5 run inside the scratch clone, which is the only place this skill
  changes anything.
- Never run anything from the scratch clone: no script, hook, test or install.
  It's read with git and copied from, nothing else.
- Never write the `starter:` line yourself. The person adds it once they've
  taken what they meant to.
- Every commit on the list is in the answer, and the count you give is the
  list's length. To be brief, shorten each line, never drop a commit.
- Asked what this copy's own remote has that it doesn't, that's
  [`whats-new`](../whats-new/SKILL.md), not this skill.

## Output

The baseline and how it was found. Then each commit, oldest first: its subject,
its changelog entry name and **Do:** line if it has one, the adapted files it
touches, and its answer with the reason. Then any competing build with its
direction and `Go:` line, the commands to take each file, and the `starter:`
line to add. End there: the next step is theirs to run.
