# Harness dashboard

The harness's numbers are spread across the loop's records, your usage log,
saved evals, Claude Code's transcripts and GitHub. This mod opens a pane
beside the conversation that brings them together, with what needs you first.
In a pane 66 columns wide, with made-up numbers:

```
starter                                              Updated 11:43
[ Refresh ] [ 7 days ] [ 14 days ] [ 30 days ]
──────────────────────────────────────────────────────────────────
Waiting on you
Pull request                              Waiting Checks Conflicts
#41 Gate: check the fee total                3.2h   pass   unknown

Blocked issue                                                Since
#38 README: link the loop section                           Oct 26

#38: still failing after 5 rounds

──────────────────────────────────────────────────────────────────

Loop spend
Daily, Oct 22 to Oct 27: most $6.40 on Oct 25
                      ▄▄▄▄▄▄▄▄▄▄ ██████████
                      ██████████ ██████████ ▂▂▂▂▂▂▂▂▂▂
                      ██████████ ██████████ ██████████ ▇▇▇▇▇▇▇▇▇▇
           ▆▆▆▆▆▆▆▆▆▆ ██████████ ██████████ ██████████ ██████████
▇▇▇▇▇▇▇▇▇▇ ██████████ ██████████ ██████████ ██████████ ██████████
  Oct 22     Oct 23     Oct 24     Oct 25     Oct 26     Oct 27
  $1.20      $2.30      $5.80      $6.40      $4.20      $3.60
   900k       1.7M       4.3M       4.9M       3.1M       2.6M

                                                       Cost Tokens
Today                                                 $3.60   2.6M
7 days                                               $23.50  17.5M
Since Oct 14                                         $23.50  17.5M
Per pull request                                     ~$2.35

Costliest issues                                       Cost Tokens
#38                                                   $5.40   4.0M
#36                                                   $3.10   2.3M
#41                                                   $2.20   1.6M

Model                                                  Cost Tokens
opus-5-5                                             $19.00  14.0M
sonnet-5-5                                            $4.50   3.5M

The loop's records start Oct 22
Claude Code's estimate at API prices, not a bill

──────────────────────────────────────────────────────────────────

Throughput and rework
12 recent issues                                             Count
Opened a pull request                                           10
Blocked                                                          2
Took more than one round                                         3

Merged loop pull requests                                    Count
Merged                                                          10
Needed a commit first                                      4 (40%)
  with a fix                                                     3
  only a merge from main                                         1

──────────────────────────────────────────────────────────────────

Evals
Reviewer                         Stable Flaky Failing  Saved Stale
reviewer                             10     0       0 Oct 24   yes

reviewer stale: 1 file changed, newest Oct 26. Run it again

──────────────────────────────────────────────────────────────────

Conversations
Daily, Oct 14 to Oct 27: most 9.4M tokens on Oct 24
                                             ███ ▅▅▅
                                         ▂▂▂ ███ ███
                             ▁▁▁ ▁▁▁ ▆▆▆ ███ ███ ███     ▁▁▁
     ▅▅▅             ▄▄▄ ▆▆▆ ███ ███ ███ ███ ███ ███ ▆▆▆ ███
     ███ ▅▅▅         ███ ███ ███ ███ ███ ███ ███ ███ ███ ███
                           Oct 20                      Oct 27

                                                   Tokens Sessions
Harness                                             42.5M       31
Loop worktrees                                      12.2M       40

Model                                                Harness  Loop
opus-5-5                                               40.3M 12.2M
haiku-5-5                                               2.2M     0

Since Oct 14, cache reads included

──────────────────────────────────────────────────────────────────

Activity
Skill                                                        Times
review-pr                                                        6
learn                                                            2
loop-control                                                     2

Agent                                                        Times
reviewer                                                         6
security-reviewer                                                2

Guard asked 2 times, since Oct 14
```

A line separates each section. A section with a chart starts with it, then its
tables: names on the left, figures in right-aligned columns. A row that needs
you is coloured. Red is a failing check, a conflict, a blocked issue, a failing
eval, or a list the pane couldn't read. Yellow is checks still running, a stale
or flaky eval, an eval count it couldn't read, loop pull requests that needed a
commit before merging, and what the guard refused.

Every number comes from [`scripts/dashboard_data.py`](../../../scripts/dashboard_data.py) `--json`, which the
pane runs and draws. That script says where each one comes from and what it
leaves out; this mod adds nothing to them. The daily charts need the version
that gives figures by day, from 2026-10-27.

It's a Claude Code mod, so it works in Claude Code only. It was built on
Claude Code 2.1.308 and seen working in its terminal on 2026-10-27. Codex and
Kiro don't have mods.

## Open it

Type `/harness-dashboard`. In fullscreen, from 110 columns, the pane docks
beside the conversation. Narrower, it sits above the prompt. Close it with the
`×` in its corner.

It isn't on by default. Load it for one session, from the root:

```
claude --plugin-dir examples/mods/harness-dashboard
```

Or install it from inside a session, at the root:

```
/plugin marketplace add ./
/plugin install harness-dashboard@sanvio-harness-starter
```

A change to what the mod does raises `version` in its [`.claude-plugin/plugin.json`](.claude-plugin/plugin.json), because `/plugin update` keeps an installed copy whose version hasn't changed, and CI checks this on every pull request with [`scripts/check_mod_versions.py`](../../../scripts/check_mod_versions.py).

## Reading it

| Section | Shows |
|---|---|
| The header | The harness's folder, and when the numbers were read. **7 days**, **14 days** and **30 days** pick how many days it counts, today among them: 14 until you pick another, and the pick is kept across reloads. Picking one reads straight away. A range you haven't read before takes a few seconds more the first time. **Reading…** until the first read ends. That can take a minute, because the first read goes through every Claude Code transcript once and keeps what it found in `.harness/cache/`; later reads took about two seconds here. **Refresh failed** in red when the last refresh didn't work, with the time of the numbers still shown and why under it |
| **Waiting on you** | Each open pull request, how long it has waited, whether it's a draft, its checks and whether it conflicts with its base, then each issue the loop blocked, with why. Red when checks fail or it conflicts, yellow while they run. **conflicts unknown** while GitHub hasn't worked it out. Without `gh`, signed out, or a list in a shape it doesn't know, it says in red that it couldn't read them: never that nothing is waiting |
| **Loop spend** | Three tables: the loop's estimated dollars and tokens today, over the last 7 days, since the date the numbers start and per pull request it opened; the five issues that cost most; and each model, costliest first. Runs that recorded no model show as **model not recorded**. When the loop's records start later than that date, it says when, and the chart starts there |
| **Throughput and rework** | How the loop's recent issues ended and how many took more than one round, then how many of its merged pull requests needed someone else's commit before merging, split into fixes and merges from main |
| **Evals** | Each reviewer's newest saved eval: stable, flaky and failing cases, which ones fail, and **stale** when the agent, a brief, a case or the eval script changed after it was saved. **stale: unknown** when git couldn't say |
| The daily charts | At the top of **Loop spend** and **Conversations**: one bar per day, today in orange, under a line naming the busiest day. The terminal draws them in coloured blocks the width of the pane, with each day and its figures under its bar when the pane has 7 columns a day: cost and tokens for spend, tokens for conversations. Narrower, as for Conversations above, it writes only the day, under every 7th bar counting back from today's. A day whose runs recorded no cost shows **?**, not $0.00. On other surfaces it draws them as a picture whose bars say their day and value when you hover, with every bar's figures under it up to 14 days and every 7th bar's day beyond that; the tests cover Claude Desktop's, and nobody has looked at it in VS Code or the mobile app yet. A `dashboard_data.py` that doesn't give daily figures says so instead |
| **Conversations** | Claude Code's tokens in the harness and in the loop's worktrees, with sessions and the four biggest models. Cache reads are most of it. Its chart covers every day counted, since the harness's own sessions start before the loop's |
| **Activity** | The skills, agents and slash commands you used most, what the guard refused and how often it asked, from your usage log |

A section whose source is missing or can't be read says why, dimmed, and the
rest still show. The range sets every section but **Throughput and rework**'s
issues, which are always the loop's 20 most recent. The loop's spend only goes
back as far as the loop's own records: a run before the loop recorded its usage
isn't in it, so **Since** can match **7 days** in a young harness.

## What it costs and touches

It spends no model tokens: it runs a Python script and draws what it prints.
It runs `python3 scripts/dashboard_data.py --json --since <the range's first day>` once when it opens, then
every five minutes while it's open, and **Refresh** reads now. One read runs at
a time, and a refresh that fails keeps the last numbers it had. After you close
the pane it stops at the next five-minute mark; a read already running then
finishes.

The script reads the loop's `.loop/` files, your usage log, `.harness/evals/`,
git and every transcript under `~/.claude/projects`, and writes only its own
caches under `.harness/cache/`, which is gitignored. Each refresh calls GitHub
through `gh` twice, for the open pull requests and the merged ones, and the
first time it sees a merged loop pull request, once more for its commits. The
[`github-status`](../github-status/) mod reads the same pull requests every two minutes, so the two
can differ for a few minutes.

It runs the script in the nearest folder at or above the one the session
started in that has [`scripts/dashboard_data.py`](../../../scripts/dashboard_data.py). Installed beyond this repo,
`/harness-dashboard` in another repo would run that repo's copy, so open it
only in a harness you trust.

## Changing it

[`hooks/logic.ts`](hooks/logic.ts) turns the script's JSON into the pane's sections, as plain
functions, so they can be tested, and [`hooks/charts.ts`](hooks/charts.ts) draws the daily
charts. [`hooks/register.tsx`](hooks/register.tsx) runs the script and draws the pane. From [`examples/mods/`](../):

```bash
claude plugin validate harness-dashboard
claude plugin test harness-dashboard
```

`python3 -m unittest discover -s tests`, and so the loop, runs these wherever Claude Code is installed. CI doesn't install Claude Code, so it skips them.
