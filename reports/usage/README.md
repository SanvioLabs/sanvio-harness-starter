# Usage reports

One file per person per sprint, written by [`skills/harness-report/`](../../skills/harness-report/) from that
person's own usage log and read by them before it lands here. Each arrives as a
pull request. The harness owner reads a sprint's reports together, takes the
proposals worth taking, and says why for the ones it doesn't.

Counts and proposals only. The raw logs stay in `.harness/usage/` on each
person's machine, and that folder is gitignored.

## Telling your team

The log is on by default, so tell people before their first session. This is
written to paste into Slack or your team's working-practices doc as it is:

> The harness keeps a usage log on your own machine: which skills, agents and
> slash commands you ran, and when the guard refused something or asked you
> first. It records names and counts only. No prompts, no code, no file paths,
> and nothing leaves your machine on its own.
>
> At the end of each sprint, ask your agent for "my harness report". It
> summarizes your log, asks what worked, what you worked around and what you'd
> change, and writes a short report you read before sharing it as a pull
> request. I read the sprint's reports together and we decide what goes into the
> harness.
>
> To turn the log off for yourself, set `HARNESS_USAGE_LOG=off` in your shell
> profile.
