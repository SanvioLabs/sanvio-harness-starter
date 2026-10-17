# Company

![Where things live. The harness holds the method; everything else stays where its owner keeps it. On the left, your harness on disk: my-harness/ holds AGENTS.md, steering/, skills/, gates/ and agents/, the method, tracked in the harness and shared with everyone who uses it. company/ is a clone of your-org/company, holding COMPANY.md (who you are) and DATA.md (where your systems are). projects/ holds billing/ and website/, each a clone of a repo your org owns, keeping its own access and history. DATA.md points to systems you run, such as Confluence, Google Drive, Jira and your CRM, reached through a connector (MCP). A cloned repo and a connector are the same idea: read where it lives, under its owner's access, never copied in.](where-things-live.png)

Who the agent works for. Everything in `company/` is yours, and by default none
of it gets committed: [`.gitignore`](../.gitignore) keeps the whole folder out of git.

| File | Holds | Written by |
|---|---|---|
| `COMPANY.md` | What you sell, who for, how you sound, what you won't do | `/orientation` interviews you, from [`COMPANY.example.md`](COMPANY.example.md) |
| `DATA.md` | Where your company's data lives and how the agent reaches it. Where, never what | `/orientation`, step 3 |

Every session reads both before company work. [`AGENTS.md`](../AGENTS.md) says so, which is
how Claude Code, Codex and Kiro all find them.

**Why it's ignored.** This starter is public, and a copy of a public repo on
GitHub is usually public too. Your company record stays on your machine until
you choose otherwise.

## Three ways to keep it

| Where | Fits when |
|---|---|
| Local files in `company/` (the default) | You work alone on one machine, or haven't decided yet |
| Committed in a private copy of the harness | Your whole team shares one private harness, and the record goes wherever it goes |
| A private repo cloned into `company/` with `git clone <url> company` | Several harnesses or people share one record, or the harness is public and the record can't be |

**Committing it in a private copy.** Once your copy is private, and only then,
delete the `company/` line from [`.gitignore`](../.gitignore) and commit the record. Check first:

```bash
gh repo view --json visibility -q .visibility    # should print PRIVATE
```

**A company repo.** Make a private repo for the record, then clone it into the
harness root as `company/`. The harness ignores the folder, so the two repos
never mix, and search tools still read it. `python3 scripts/check_setup.py`
asks GitHub for that repo's visibility and fails if it's public.
