// What scripts/loop.py writes to .loop/status.json. Every field is optional here: an older or
// half-written file still draws, with what it has.
export type QueueItem = { number: number; title: string }

export type Row = {
  number: number
  title: string
  step: string
  state: string
  round: number
  max_rounds?: number
  tests: string | null
  review: string | null
  pr: string | null
  note: string
  // When this run of the issue began, in local time. An older loop.py doesn't write it.
  started?: string
  updated?: string
}

export type Status = {
  running: boolean
  updated: string | null
  // The tmux session a running loop is in, when it was started in one.
  tmux: string | null
  queue: QueueItem[]
  issues: Row[]
}

// What the pane draws from: the status file, plus whether the lock and a stop request are there.
export type Seen = {
  root: string
  status: Status | null
  // A lock whose process is alive: the loop is running.
  isLocked: boolean
  // A lock left by a process that's gone: the last run was killed. The next run replaces it.
  isStaleLock: boolean
  isStopping: boolean
  // .loop/watch.command is there: loop.py wrote it, on macOS inside tmux, for the Watch it button.
  hasWatchFile: boolean
}

// Which tab the pane shows, and the first job of its list in view. Null until the person picks a tab.
export type Tab = 'queue' | 'active' | 'finished'
export type View = { tab: Tab; start: number }

declare module 'claude-code' {
  interface PluginState {
    'loop-pane': { launch: string | null; seen: Seen | null; view: View | null }
  }
}
