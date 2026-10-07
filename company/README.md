# Company

Who the agent works for. Everything here is yours, and by default none of it
gets committed: `.gitignore` keeps every file in this folder out of git except
this one and the examples.

| File | Holds | Written by |
|---|---|---|
| `COMPANY.md` | What you sell, who for, how you sound, what you won't do | `/orientation` interviews you, from `COMPANY.example.md` |
| `DATA.md` | Where your company's data lives and how the agent reaches it. Where, never what | `/orientation`, step 3 |

Every session reads both before company work. `AGENTS.md` says so, which is
how Claude Code, Codex and Kiro all find them.

**Why it's ignored.** This starter is public, and a copy of a public repo on
GitHub is usually public too. Your company record stays on your machine until
you choose otherwise.

**Sharing it with your team.** Once your copy is private, and only then, delete
the `company/*` lines from `.gitignore` and commit the record. Check first:

```bash
gh repo view --json visibility -q .visibility    # should print PRIVATE
```
