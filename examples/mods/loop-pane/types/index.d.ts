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
  updated?: string
}

export type Status = {
  running: boolean
  updated: string | null
  queue: QueueItem[]
  issues: Row[]
}

// What the pane draws from: the status file, plus whether the lock and a stop request are there.
export type Seen = {
  root: string
  status: Status | null
  isLocked: boolean
  isStopping: boolean
}

declare module 'claude-code' {
  interface PluginState {
    'loop-pane': { launch: string | null; seen: Seen | null }
  }
}
