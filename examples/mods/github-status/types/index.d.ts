// What one read of GitHub found: workflow runs in progress and queued, open pull requests, open issues.
export type Counts = { running: number; queued: number; pulls: number; issues: number }

// The line's state. `repo` is `owner/name`, from the session's origin remote. `at` is when the counts
// were read, in milliseconds. Stale is a later read that failed: the last counts, with their age.
export type GitHubState =
  | { kind: 'no-remote' }
  | { kind: 'reading'; repo: string }
  | { kind: 'counts'; repo: string; counts: Counts; at: number }
  | { kind: 'unavailable'; repo: string }
  | { kind: 'stale'; repo: string; counts: Counts; at: number }

declare module 'claude-code' {
  interface PluginState {
    // `attempt` is when the last read of GitHub began, so a reload doesn't read again early.
    'github-status': { launch: string | null; status: GitHubState | null; attempt: number | null }
  }
}
