# Projects

Your code repos live here, inside the harness, so every one of them works
under the same rules, skills, gates and guards. Each folder is its own git
clone. The harness tracks nothing in this folder except this file.

```bash
cd projects
git clone <your repo>        # or several
cd ..                         # then start your agent from the harness root
```

## Start the agent at the harness root, not in the project

Then point it at the project: "in projects/billing, fix the failing test".

This matters more than it looks. We tested Claude Code started inside
`projects/<repo>`: it reads the harness's `CLAUDE.md` from the folder above,
but not the `AGENTS.md` that file imports, and **none of the harness's
skills, agents or hooks**. No rules, no `/orientation`, no `review-pr`, no
credential guard, and nothing tells you so. `CLAUDE.md` carries one warning
outside the import for exactly this, so the agent says so out loud.

In Kiro, open the harness root as the workspace, for the same reason.

## Why `.ignore` is at the root

This folder is gitignored so the harness never commits your code. Search
tools skip gitignored folders, and Claude Code's Grep did: started at the
root, it found nothing under `projects/` until `.ignore` said to look. Leave
that file in place.

## What each project keeps for itself

- **Its own instructions.** A project's own `AGENTS.md` or `CLAUDE.md` adds
  what's specific to it: how to run it, its architecture, its quirks. It adds
  to the harness's rules and never loosens one.
- **Its own git hooks and CI.** Each project is a separate repo, so the
  harness's `.githooks/pre-commit` doesn't run on its commits. Wire the
  project's own checks there, and in its own pipeline.
- **Its own history.** Commit and push inside the project folder. The harness
  repo never sees the project's files.

## One harness, many developers

One person owns the harness and merges changes to it: new rules, skills,
gates. Everyone else clones the harness, clones their projects into this
folder, and pulls the harness to get what's new. A skill someone writes for
themselves goes to the owner as a pull request, so it reaches everyone instead
of living in one person's `~/.claude/skills`.
