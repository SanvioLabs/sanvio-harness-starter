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

It loads by itself, the same way as the [harness lens](../harness-lens/): the harness's
[`.claude/settings.json`](../../../.claude/settings.json) turns it on. Don't see the line? Install it from
inside a session, at the root:

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

## Your projects

The line is the harness's repo. Repos cloned under [`projects/`](../../../projects/) are read
with the command, from a session at the harness root:

| Type | Prints |
|---|---|
| `/github acme` (or `/github projects/acme`) | The line for the repo cloned in `projects/acme`, read now |
| `/github all` | The harness's line, then one per folder under [`projects/`](../../../projects/) with a GitHub `origin`, in name order, then how many folders have none |

```
harness: SanvioLabs/sanvio-harness-starter · 0 actions running · 2 open pull requests · 5 open issues
acme: acme/app · 1 action running · 4 open pull requests · 12 open issues
1 folder under projects/ has no GitHub remote.
```

A name is one folder directly under [`projects/`](../../../projects/). Anything that could reach
outside it, such as `../x`, `a/b` or a leading `.`, is refused before anything
runs. A folder with no GitHub `origin` says so and `gh` isn't called. A repo
whose read fails says GitHub is unavailable on its own line, and the others
still print. Reading a project never changes the line above the prompt.

## What it doesn't do

It only reads. It never changes anything on GitHub. When the session starts
it runs `git remote get-url origin` in the folder the session started in (and,
for `/github <name>` or `/github all`, in each folder under [`projects/`](../../../projects/) it
reads), and
on a github.com remote, at most once every two minutes, it makes three reads
through `gh`, each with a time limit:

- `gh api graphql` with a query (never a mutation) for the open pull request
  and open issue counts
- `gh api --method GET repos/owner/name/actions/runs`, once for runs in
  progress and once for queued ones

`/github` reads whenever you type it. Drawing the line never calls `gh`. A
read that fails, for any reason, shows as unavailable or stale and stops
nothing.

The line shows the repo the session started in, from its `origin` remote.
Other repos are read only through `/github <name>` and `/github all`, from
folders under [`projects/`](../../../projects/). It doesn't choose another remote, list workflows
one by one, or link to GitHub.

## Changing it

[`hooks/logic.ts`](hooks/logic.ts) holds the decisions as plain functions, so they can be tested.
[`hooks/register.tsx`](hooks/register.tsx) runs `git` and `gh` and draws the line. From
[`examples/mods/`](../):

```bash
claude plugin validate github-status
claude plugin test github-status
```

`python3 -m unittest discover -s tests`, and so the loop, runs these wherever Claude Code is installed. CI doesn't install Claude Code, so it skips them.
