# Deploying

Read this when you set up infrastructure, deploy, or change anything that
runs where people use it. A deploy is the release step in [`gates.md`](gates.md): the last
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
  a value. [`data-and-tools.md`](data-and-tools.md) has the rule.

## Environments

- **Staging before production.** Staging runs production's configuration on
  synthetic data, so what you test is what ships.
- **Production deploys from the main branch, through CI** where you can. A
  deploy from a laptop ships whatever was on the laptop.
- **Know the way back before you go.** The rollback command, and what it can't
  undo: data written in between, emails sent, a migration that dropped a
  column.

## The deploy workflow

- **One deploy workflow, one caller per environment.** The steps (get
  credentials, apply, migrate, smoke test) live in one reusable workflow.
  Staging and production each call it, and differ only in which account they
  reach, who may start them and what has to be true first. Three copies
  drift, and the one that drifts is production.
- **Staging deploys on merge. Production starts by hand.** A merge to main
  is a decision to release, not a decision to deploy this minute. Make the
  person starting it type what they're doing ("deploy to production"), so it
  can't be a misclick. Once a second person exists, a GitHub environment with
  a required reviewer is the stronger gate.
- **Plan on the pull request, apply in the deploy.** An infrastructure
  change shows its plan where it's reviewed, and only the deploy workflow
  applies it. Never an apply from someone's terminal.
- **Short-lived credentials.** CI reaches the cloud account through OIDC
  federation, with a role that trusts this repo only. Never a stored access
  key.
- **One deploy at a time per environment.** Set `concurrency` with
  `cancel-in-progress: false`. Two applies against one state file is a lock
  error at best.
- **Honest before it's wired up.** Until the role and the account exist, each
  step says what's missing and skips. A workflow that's red from day one
  teaches people to ignore red.

## Every deploy

- **Production is a one-way door.** Whatever people did on it in between stays
  done. The agent deploys to production only when a human says yes to that one
  deploy. Standing permission for staging, if you want to give it, goes in
  [`AGENTS.md`](../AGENTS.md).
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
