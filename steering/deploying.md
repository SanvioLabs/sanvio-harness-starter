# Deploying

Read this when you set up infrastructure, deploy, or change anything that
runs where people use it. A deploy is the release step in `gates.md`: the last
place to catch a problem before it reaches someone.

## Before the first deploy

- **Infrastructure as code.** A setting clicked in a console is a change
  nobody reviewed and nobody can repeat.
- **A named profile for each cloud account**, and confirm which one you're in
  before anything changes. On AWS that's
  `aws sts get-caller-identity --profile <name>`.
- **A separate account for anything with personal, health, financial or
  children's data**, or anything you might need to delete completely.
- **The deploy script comes first.** Write it before the first deploy and use
  it from then on. A deploy done by hand can't be repeated or reviewed.
- **Secrets come from the platform's store, by name.** The script never holds
  a value. `data-and-tools.md` has the rule.

## Environments

- **Staging before production.** Staging runs production's configuration on
  synthetic data, so what you test is what ships.
- **Production deploys from the main branch, through CI** where you can. A
  deploy from a laptop ships whatever was on the laptop.
- **Know the way back before you go.** The rollback command, and what it can't
  undo: data written in between, emails sent, a migration that dropped a
  column.

## Every deploy

- **Production is a one-way door.** Whatever people did on it in between stays
  done. The agent deploys to production only when a human says yes to that one
  deploy. Standing permission for staging, if you want to give it, goes in
  `AGENTS.md`.
- **Gates and CI green first.** Never deploy past a failing check.
- **A schema or data change needs a migration path** and a backup taken
  before it runs.
- **Smoke test what you deployed**: the happy path and one error case, against
  the live thing. Deployed and untested is worse than not deployed.
- **Write down what shipped.** A tag, a release note or the pull request, with
  the date.

## Never

- Delete or overwrite data without asking, even test data. Someone spent time
  making it.
- Fix production by hand. Fix the code and deploy again, or the next deploy
  undoes the fix.
