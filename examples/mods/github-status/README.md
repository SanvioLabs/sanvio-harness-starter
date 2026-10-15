# GitHub status

Whether a pull request is waiting or a workflow is still running lives on
GitHub, a browser tab away from the session. This mod draws one line above the
prompt with the repo's running actions, open pull requests and open issues:

```
◆ github  SanvioLabs/sanvio-harness-starter · 1 action running (2 queued) · 3 open pull requests · 5 open issues
```

It's a Claude Code mod, so it works in Claude Code only, and it was built on
Claude Code 2.1.301. Codex and Kiro don't have mods.

## Turn it on

It's off unless you install it. From inside a session, at the root:

```
/plugin marketplace add ./
/plugin install github-status@sanvio-harness-starter
```

It's active as soon as the install says so, no restart. Or load it for one
session with `claude --plugin-dir examples/mods/github-status`.

It reads GitHub through the [`gh`](https://cli.github.com/) command line, so
`gh` has to be installed and signed in (`gh auth status` says).

To turn it off just for you:

```bash
claude plugin disable github-status@sanvio-harness-starter --scope local
```

## Reading the line

| The line says | Means |
|---|---|
| `owner/name · reading…`, cyan | The first read of GitHub is under way |
| `owner/name · 2 actions running (1 queued) · 3 open pull requests · 5 open issues`, cyan | What the last read found. Actions are workflow runs in progress, and the queued count shows only when there is one. Issues don't include pull requests |
| `… · as of 7m ago`, yellow | The last read failed, so these are the counts from the one before, and how old they are |
| `owner/name · GitHub unavailable (is gh installed and signed in?)`, yellow | No read has worked yet this session. `gh` is missing, signed out, offline, or can't see the repo |
| `no GitHub remote`, dim | The session's folder has no `origin` remote on github.com, so the mod never calls `gh` |

`/github` reads GitHub straight away and prints the line.

## What it doesn't do

It only reads. It never changes anything on GitHub. When the session starts
it runs `git remote get-url origin` in the folder the session started in, and
on a github.com remote, at most once every two minutes, it makes three reads
through `gh`, each with a time limit:

- `gh api graphql` with a query (never a mutation) for the open pull request
  and open issue counts
- `gh api --method GET repos/owner/name/actions/runs`, once for runs in
  progress and once for queued ones

`/github` reads whenever you type it. Drawing the line never calls `gh`. A
read that fails, for any reason, shows as unavailable or stale and stops
nothing.

It shows the repo the session started in, from its `origin` remote. It
doesn't choose another remote or repo, list workflows one by one, or link to
GitHub.

## Changing it

[`hooks/logic.ts`](hooks/logic.ts) holds the decisions as plain functions, so they can be tested.
[`hooks/register.tsx`](hooks/register.tsx) runs `git` and `gh` and draws the line. From
[`examples/mods/`](../):

```bash
claude plugin validate github-status
claude plugin test github-status
```

CI doesn't run these, because they need Claude Code installed.
