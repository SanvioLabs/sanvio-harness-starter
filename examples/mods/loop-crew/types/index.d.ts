// The part of what scripts/loop.py writes to status.json that the figures draw from.
export type Row = { number: number; title: string; step: string; state: string; round: number }

export type Status = { issues: Row[] }

// One look at one loop's files.
export type Seen = {
  // The project under .loop/projects/ this loop belongs to. Unset for the harness's own.
  project?: string
  status: Status | null
  // A lock whose holder is alive: the loop is running.
  isLive: boolean
}

declare module 'claude-code' {
  interface PluginState {
    // launch: the folder the session started in. shown: the loop on screen, a project's name or ''
    // for the harness. seen: that loop's last look, null until the first.
    'loop-crew': { launch: string | null; shown: string; seen: Seen | null }
  }
}
