// The decisions, as pure functions. register.tsx runs git and gh and draws the line, then calls in here,
// because the test kit can't stand in for a process.

import type { Counts, GitHubState } from '../types'

// At most one read of GitHub per repo in this long, unless the person asks with /github.
export const LIMIT_MS = 2 * 60_000

const PART = '[A-Za-z0-9_.-]+'
const REMOTES = [
  new RegExp(`^git@github\\.com:(${PART})/(${PART}?)(?:\\.git)?/?$`),
  new RegExp(`^ssh://git@github\\.com(?::\\d+)?/(${PART})/(${PART}?)(?:\\.git)?/?$`),
  new RegExp(`^https://(?:[^@/]+@)?github\\.com/(${PART})/(${PART}?)(?:\\.git)?/?$`),
]

// `owner/name` for a github.com remote, over SSH or HTTPS. Anything else is none, and gh is never called.
export function parseRemote(url: string): string | null {
  const text = url.trim()
  for (const pattern of REMOTES) {
    const match = text.match(pattern)
    const owner = match?.[1]
    const name = match?.[2]
    if (!owner || !name || [owner, name].some(part => part === '.' || part === '..')) continue
    return `${owner}/${name}`
  }
  return null
}

// The GraphQL read, a query and never a mutation. issues(states: OPEN) leaves pull requests out.
export const QUERY =
  'query($owner: String!, $name: String!) { repository(owner: $owner, name: $name) { pullRequests(states: OPEN) { totalCount } issues(states: OPEN) { totalCount } } }'

function json(text: string): unknown {
  try {
    return JSON.parse(text)
  } catch {
    return null
  }
}

const count = (value: unknown): number | null => (typeof value === 'number' && Number.isInteger(value) && value >= 0 ? value : null)

// The counts from the GraphQL answer and the two workflow-run listings. None when any is the wrong shape.
export function parseCounts(graphqlJson: string, runningJson: string, queuedJson: string): Counts | null {
  const repo = (json(graphqlJson) as { data?: { repository?: Record<string, { totalCount?: unknown } | undefined> } } | null)?.data?.repository
  const pulls = count(repo?.pullRequests?.totalCount)
  const issues = count(repo?.issues?.totalCount)
  const running = count((json(runningJson) as { total_count?: unknown } | null)?.total_count)
  const queued = count((json(queuedJson) as { total_count?: unknown } | null)?.total_count)
  if (pulls === null || issues === null || running === null || queued === null) return null
  return { running, queued, pulls, issues }
}

// Whether a read may start: the first one, one two minutes after the last, or one the person asked for.
export function due(lastAttempt: number | null, now: number, isAsked = false): boolean {
  return isAsked || lastAttempt === null || now - lastAttempt >= LIMIT_MS
}

// A read that failed keeps the last counts, marked stale. With none to keep, GitHub is unavailable.
export function failed(state: GitHubState | null, repo: string): GitHubState {
  return state && (state.kind === 'counts' || state.kind === 'stale') && state.repo === repo
    ? { kind: 'stale', repo, counts: state.counts, at: state.at }
    : { kind: 'unavailable', repo }
}

export type Tone = 'quiet' | 'now' | 'warn'
export type Line = { text: string; tone: Tone }

const plural = (n: number, one: string, many: string) => `${n} ${n === 1 ? one : many}`

function countsText(repo: string, c: Counts): string {
  const actions = `${plural(c.running, 'action', 'actions')} running${c.queued ? ` (${c.queued} queued)` : ''}`
  return `${repo} · ${actions} · ${plural(c.pulls, 'open pull request', 'open pull requests')} · ${plural(c.issues, 'open issue', 'open issues')}`
}

function age(ms: number): string {
  const minutes = Math.max(0, Math.floor(ms / 60_000))
  return minutes < 60 ? `${minutes}m` : `${Math.floor(minutes / 60)}h ${minutes % 60}m`
}

// The line above the prompt, after its `◆ github` label.
export function lineFor(state: GitHubState, now: number): Line {
  switch (state.kind) {
    case 'no-remote':
      return { text: 'no GitHub remote', tone: 'quiet' }
    case 'reading':
      return { text: `${state.repo} · reading…`, tone: 'now' }
    case 'counts':
      return { text: countsText(state.repo, state.counts), tone: 'now' }
    case 'unavailable':
      return { text: `${state.repo} · GitHub unavailable (is gh installed and signed in?)`, tone: 'warn' }
    case 'stale':
      return { text: `${countsText(state.repo, state.counts)} · as of ${age(now - state.at)} ago`, tone: 'warn' }
  }
}
