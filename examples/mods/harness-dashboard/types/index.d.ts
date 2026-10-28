// What scripts/dashboard_data.py --json prints, kept as it came: each section is read field by field
// in logic.ts, so an older script, or a section that's { value: null, why }, still draws.
export type Doc = Record<string, unknown>

// What the pane draws from. readAt and failedAt are Date.now() values.
export type Seen = {
  root: string
  // The last document that read whole. A refresh that fails keeps it.
  doc: Doc | null
  readAt: number | null
  // A read is under way. The first one can take a minute: it reads every transcript once.
  isReading: boolean
  // The last refresh failed, when it did, and in a few words why. Cleared by the next good one.
  failedAt: number | null
  failure: string | null
}

declare module 'claude-code' {
  interface PluginState {
    'harness-dashboard': { launch: string | null; seen: Seen | null }
  }
}
