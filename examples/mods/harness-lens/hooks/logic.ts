// The decisions, as pure functions. register.tsx reads files and watches events, then calls in here,
// because the test kit can't stand in for the filesystem.

import type { GateHit, Hit, Lens } from '../types'

// Where a harness keeps each layer, relative to its root. A harness with another layout says so in
// .claude/harness-lens.json, with any of these keys; a key left out keeps the starter's value.
export type Config = {
  // Folders of steering files.
  steering: string[]
  // Files whose `@path` lines load steering into every session.
  always: string[]
  // Folders whose subfolders are the harness's own skills. `*` stands for one folder name.
  skills: string[]
  // Plugin namespaces whose skills count as the harness's too: `studio:` for `studio:phase-gate`.
  skillPrefixes: string[]
  // Folders whose `<name>.md` files are the harness's agents.
  agents: string[]
  // Patterns for a shell command that runs a gate. The first group, if any, is the gate's name.
  gates: string[]
}

export const STARTER: Config = {
  steering: ['steering'],
  always: ['AGENTS.md'],
  skills: ['skills', 'examples/*/skills'],
  skillPrefixes: [],
  agents: ['agents'],
  gates: ['([\\w-]+)_gate\\.py'],
}

export const CONFIG_FILE = '.claude/harness-lens.json'

const KEYS = Object.keys(STARTER) as Array<keyof Config>

export function parseConfig(text: string | null): Config {
  if (text === null) return STARTER
  let raw: unknown
  try {
    raw = JSON.parse(text)
  } catch {
    return STARTER
  }
  const given = (raw ?? {}) as Record<string, unknown>
  const config = { ...STARTER }
  for (const key of KEYS) {
    const value = given[key]
    if (Array.isArray(value) && value.every(item => typeof item === 'string')) config[key] = value as string[]
  }
  return config
}

const tidy = (path: string) => path.replace(/^\.\//, '').replace(/\/+$/, '')
const escape = (text: string) => text.replace(/[.+?^${}()|[\]\\]/g, '\\$&')
const folderPattern = (folder: string) =>
  tidy(folder).split('/').map(part => (part === '*' ? '[^/]+' : escape(part))).join('/')

// A path inside the root, relative to it. Anything outside is none of the lens's business.
export function relative(path: string, root: string): string | null {
  const base = `${root.replace(/\/+$/, '')}/`
  return path.startsWith(base) ? path.slice(base.length) : null
}

export function steeringName(rel: string, config: Config): string | null {
  for (const folder of config.steering) {
    const match = rel.match(new RegExp(`^${folderPattern(folder)}/([^/]+)\\.md$`))
    const name = match?.[1]
    if (name && name.toLowerCase() !== 'readme') return name
  }
  return null
}

// The steering every session gets: each `@path` line in the always-loaded files that names a steering file.
export function alwaysSteering(texts: readonly string[], config: Config): string[] {
  const names: string[] = []
  for (const text of texts) {
    for (const line of text.split('\n')) {
      const match = line.trim().match(/^@(\S+)$/)
      const path = match?.[1]
      const name = path ? steeringName(tidy(path), config) : null
      if (name && !names.includes(name)) names.push(name)
    }
  }
  return names
}

// A skill followed by reading its file, which is how Codex, Kiro and a model that skips the Skill tool do it.
export function skillFromPath(rel: string, config: Config): string | null {
  for (const folder of config.skills) {
    const name = rel.match(new RegExp(`^${folderPattern(folder)}/([^/]+)/SKILL\\.md$`))?.[1]
    if (name) return name
  }
  return null
}

// skill.prompt names every skill a session expands, a machine-wide plugin's too. Only the harness's own
// show, so a projector never lists someone's personal plugins.
export function harnessSkill(name: string, known: readonly string[], config: Config): string | null {
  if (known.includes(name)) return name
  for (const prefix of config.skillPrefixes) {
    if (prefix && name.startsWith(prefix)) return name.slice(prefix.length)
  }
  return null
}

export type GateRun = { name: string; ok: boolean }

const FAILED = /^(FAIL|BLOCKED)\b|Commit blocked|✗/m
const PASSED = /^PASS\b|✓/m

// A shell command that ran a gate, and how it went. None when the command ran no gate, or when the output
// can't say: a gate piped somewhere else doesn't count as a pass.
export function gateRun(command: string, output: string, isError: boolean, config: Config): GateRun | null {
  for (const pattern of config.gates) {
    let match: RegExpMatchArray | null
    try {
      match = command.match(new RegExp(pattern))
    } catch {
      continue
    }
    if (!match) continue
    const name = match[1] ?? 'gate'
    if (isError || FAILED.test(output)) return { name, ok: false }
    if (PASSED.test(output)) return { name, ok: true }
    return null
  }
  // The pre-commit hook is silent when it passes, so only a refusal can be seen.
  if (/\bgit\s+commit\b/.test(command) && /Commit blocked|^BLOCKED\b/m.test(output)) return { name: 'pre-commit', ok: false }
  return null
}

export function emptyLens(root: string, always: string[]): Lens {
  return { root, turn: 0, always, steering: [], skills: [], gates: [], refusals: [], reviews: [] }
}

const KEEP = 50

// Newest last. A name seen again moves to the end, so the list reads as what happened most recently.
export function remember<T extends Hit>(list: readonly T[], hit: T): T[] {
  return [...list.filter(item => item.name !== hit.name), hit].slice(-KEEP)
}

// Every gate run counts, a repeat included, so the report can say passed 3, failed 1.
export function record<T extends Hit>(list: readonly T[], hit: T): T[] {
  return [...list, hit].slice(-KEEP)
}

export type Tone = 'now' | 'pass' | 'fail' | 'earlier' | 'quiet'
export type Segment = { label: string; text: string; tone: Tone }

// The band: one segment per layer. A layer that acted this turn stands out; one that acted earlier is dim.
export function bandSegments(lens: Lens): Segment[] {
  const now = (hit: Hit | undefined) => hit !== undefined && hit.turn === lens.turn
  const readNow = lens.steering.filter(now).map(hit => hit.name)
  const always = lens.always.length ? `${lens.always.length} always on` : 'none always on'
  const steering: Segment = readNow.length
    ? { label: 'steering', text: `${always} + ${readNow.join(' · ')}`, tone: 'now' }
    : { label: 'steering', text: lens.steering.length ? `${always} + ${lens.steering.length} read` : always, tone: 'earlier' }

  const skill = lens.skills.at(-1)
  const gate = lens.gates.at(-1)
  const refusal = lens.refusals.at(-1)
  const review = lens.reviews.at(-1)
  return [
    steering,
    { label: 'skill', text: skill?.name ?? 'none yet', tone: now(skill) ? 'now' : skill ? 'earlier' : 'quiet' },
    {
      label: 'gate',
      text: gate ? `${gate.ok ? '✓' : '✗'} ${gate.name}` : 'none run',
      tone: now(gate) ? (gate!.ok ? 'pass' : 'fail') : gate ? 'earlier' : 'quiet',
    },
    {
      label: 'guard',
      text: refusal ? `✗ refused ${refusal.name}` : 'no refusals',
      tone: now(refusal) ? 'fail' : refusal ? 'earlier' : 'quiet',
    },
    { label: 'review', text: review?.name ?? 'none yet', tone: now(review) ? 'now' : review ? 'earlier' : 'quiet' },
  ]
}

function counts(list: readonly Hit[]): string {
  const seen = new Map<string, number>()
  for (const hit of list) seen.set(hit.name, (seen.get(hit.name) ?? 0) + 1)
  return [...seen].map(([name, n]) => (n > 1 ? `${name} ×${n}` : name)).join(', ')
}

// What /lens prints: the whole session, layer by layer.
export function lensReport(lens: Lens): string {
  const names = (list: readonly Hit[]) => (list.length ? list.map(hit => hit.name).join(', ') : 'none')
  const passed = lens.gates.filter(gate => gate.ok)
  const failed = lens.gates.filter(gate => !gate.ok)
  const gates = lens.gates.length
    ? [passed.length ? `passed ${counts(passed)}` : '', failed.length ? `failed ${counts(failed)}` : ''].filter(Boolean).join('; ')
    : 'none run'
  return [
    'What the harness did this session:',
    `  Steering, always on: ${lens.always.length ? lens.always.join(', ') : 'none'}`,
    `  Steering, read when it applied: ${names(lens.steering)}`,
    `  Skills followed: ${names(lens.skills)}`,
    `  Gates: ${gates}`,
    `  Guard refusals: ${lens.refusals.length ? counts(lens.refusals) : 'none'} (the reasons are in the transcript)`,
    `  Reviewers: ${names(lens.reviews)}`,
  ].join('\n')
}
