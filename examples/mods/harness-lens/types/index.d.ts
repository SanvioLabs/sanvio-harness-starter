// One thing seen: a steering file read, a skill followed, a gate run, a tool a guard refused, a reviewer.
// `turn` is the session's turn it happened in, so the band can tell this turn from earlier ones.
export type Hit = { name: string; turn: number }
export type GateHit = Hit & { ok: boolean }

// The harness's declared scope for this session: a client its guard enforces, or a project or area it
// only names. Read from the files `scope` lists in .claude/harness-lens.json; the starter declares none.
export type Scope = { kind: string; name: string }

export type Lens = {
  root: string
  turn: number
  always: string[]
  steering: Hit[]
  skills: Hit[]
  gates: GateHit[]
  // The tool a guard refused, never its reason: a reason can name a file or a customer.
  refusals: Hit[]
  reviews: Hit[]
  scope: Scope | null
}

declare module 'claude-code' {
  interface PluginState {
    'harness-lens': { launch: string | null; lens: Lens | null }
  }
}
