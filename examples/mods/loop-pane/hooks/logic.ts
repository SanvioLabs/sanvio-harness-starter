// The pane's decisions as plain functions, so they can be tested without a session.
import type { QueueItem, Row, Seen, Status, Tab } from '../types'

export type Tone = 'now' | 'pass' | 'fail' | 'quiet'
export type Line = { tone: Tone; text: string }

export const STATUS_FILE = '.loop/status.json'
export const LOCK_FILE = '.loop/lock'
export const STOP_FILE = '.loop/STOP'
export const WATCH_FILE = '.loop/watch.command'
export const SCRIPT = 'scripts/loop.py'

const STEPS: Record<string, string> = {
  SHAPE: 'planning',
  BUILD: 'building',
  VALIDATE: 'checking',
  SCALE: 'opening the pull request',
}

const ENDED: Record<string, { tone: Tone; text: string }> = {
  pr: { tone: 'pass', text: 'pull request open' },
  blocked: { tone: 'fail', text: 'blocked' },
  stopped: { tone: 'quiet', text: 'stopped' },
  skipped: { tone: 'quiet', text: 'skipped' },
}

const str = (v: unknown): string => (typeof v === 'string' ? v : '')
const num = (v: unknown): number => (typeof v === 'number' && Number.isFinite(v) ? v : 0)
const orNull = (v: unknown): string | null => (typeof v === 'string' && v ? v : null)

// The status file, or null when there's none or it can't be read. A row without a number is dropped.
export function parseStatus(text: string | null): Status | null {
  if (!text) return null
  let raw: unknown
  try {
    raw = JSON.parse(text)
  } catch {
    return null
  }
  if (!raw || typeof raw !== 'object') return null
  const data = raw as Record<string, unknown>
  const queue: QueueItem[] = (Array.isArray(data.queue) ? data.queue : [])
    .filter((q): q is Record<string, unknown> => !!q && typeof q === 'object' && num((q as Record<string, unknown>).number) > 0)
    .map(q => ({ number: num(q.number), title: str(q.title) }))
  const issues: Row[] = (Array.isArray(data.issues) ? data.issues : [])
    .filter((r): r is Record<string, unknown> => !!r && typeof r === 'object' && num((r as Record<string, unknown>).number) > 0)
    .map(r => ({
      number: num(r.number),
      title: str(r.title),
      step: str(r.step),
      state: str(r.state),
      round: num(r.round),
      max_rounds: num(r.max_rounds) || undefined,
      tests: orNull(r.tests),
      review: orNull(r.review),
      pr: orNull(r.pr),
      note: str(r.note),
      started: orNull(r.started) ?? undefined,
      updated: orNull(r.updated) ?? undefined,
    }))
  return { running: data.running === true, updated: orNull(data.updated), tmux: orNull(data.tmux), queue, issues }
}

// The first line of the pane. The lock is the truth about running: the file's own flag can be left
// true by a run that was killed.
export function headline(seen: Seen): Line {
  if (seen.isLocked && seen.isStopping) return { tone: 'now', text: 'Stopping after this step' }
  if (seen.isLocked) return { tone: 'now', text: 'Running' }
  if (seen.isStaleLock) return { tone: 'fail', text: 'Not running. The last run was killed and left its lock behind' }
  if (!seen.status) return { tone: 'quiet', text: "Hasn't run here yet" }
  if (seen.status.running) return { tone: 'fail', text: "Not running. The last run didn't finish cleanly" }
  return { tone: 'quiet', text: 'Not running' }
}

// The command that opens the tmux session a running loop is in, or null. A session named by a run
// that's no longer alive is gone, so it isn't offered.
export function attach(seen: Seen): string | null {
  const name = seen.status?.tmux
  if (!seen.isLocked || !name) return null
  return /^[\w.@%+=:,-]+$/.test(name) ? `tmux attach -t ${name}` : `tmux attach -t '${name.replace(/'/g, `'\\''`)}'`
}

// The file that opens a window on the running loop's tmux session, read-only, or null. loop.py
// writes it only on macOS inside tmux, so elsewhere, or with an older loop.py, there's no button.
export function watch(seen: Seen): string | null {
  return attach(seen) && seen.hasWatchFile ? `${seen.root}/${WATCH_FILE}` : null
}

// What the window runs, to copy when it can't open: read-only, and the name matched exactly. Always
// quoted, because zsh reads a word starting with = as a command lookup.
export function watchCommand(seen: Seen): string | null {
  const name = seen.status?.tmux
  return attach(seen) && name ? `tmux attach -r -t '=${name.replace(/'/g, `'\\''`)}'` : null
}

// Jobs in view at once; the rest scroll.
export const PAGE = 3
// How long a finished job stays on the Finished tab.
export const FINISHED_MS = 24 * 60 * 60 * 1000

export const TABS: { tab: Tab; label: string }[] = [
  { tab: 'queue', label: 'Queue' },
  { tab: 'active', label: 'Active' },
  { tab: 'finished', label: 'Finished' },
]

export type Lists = { queue: QueueItem[]; active: Row[]; finished: Row[] }

// The three tabs' lists. A finished job counts from its last update, which loop.py writes in local
// time; one with no time, or older than a day, is left out.
export function lists(status: Status | null, now: number): Lists {
  const rows = status?.issues ?? []
  const finished = rows.filter(r => {
    if (!ENDED[r.state]) return false
    const at = r.updated ? Date.parse(r.updated) : Number.NaN
    return Number.isFinite(at) && now - at <= FINISHED_MS
  })
  return { queue: waiting(status), active: rows.filter(r => !ENDED[r.state]), finished }
}

// The tab to open on: what's being worked, else what's waiting, else what finished.
export function firstTab(l: Lists): Tab {
  if (l.active.length) return 'active'
  if (l.queue.length) return 'queue'
  return 'finished'
}

// Up to PAGE items from `start`, with `start` kept inside the list, and how many sit either side.
export function page<T>(items: T[], start: number): { shown: T[]; start: number; above: number; below: number } {
  const from = Math.max(0, Math.min(Math.trunc(start) || 0, items.length - PAGE))
  const shown = items.slice(from, from + PAGE)
  return { shown, start: from, above: from, below: items.length - from - shown.length }
}

// Ready issues not already being worked on.
export function waiting(status: Status | null): QueueItem[] {
  if (!status) return []
  const busy = new Set(status.issues.filter(r => r.state === 'working').map(r => r.number))
  return status.queue.filter(q => !busy.has(q.number))
}

// One issue: what it's on, or how it ended, and the last round's results under it.
export function describe(row: Row, isRunning: boolean): { head: Line; detail: string | null } {
  const ended = ENDED[row.state]
  let head: Line
  if (ended) {
    head = ended
  } else if (row.state === 'working' && !isRunning) {
    head = { tone: 'fail', text: `left at ${STEPS[row.step] ?? 'an unknown step'}` }
  } else {
    const step = STEPS[row.step] ?? (row.step.toLowerCase() || 'starting')
    const round = row.round > 0 ? `, round ${row.round}${row.max_rounds ? ` of ${row.max_rounds}` : ''}` : ''
    head = { tone: 'now', text: step + round }
  }
  const results = [row.tests && `tests ${row.tests}`, row.review && `review ${row.review}`].filter(Boolean).join(', ')
  const detail = [results, row.state === 'pr' ? '' : row.note].filter(Boolean).join('. ')
  return { head, detail: detail || null }
}

// The dot beside a job: whether it pulses, and its colour. It pulses only while the loop is alive and
// on that job, so a run that dies mid-step stops it, the same moment the row turns red.
export function dot(row: Row, isRunning: boolean): { tone: Tone; isPulsing: boolean } {
  const ended = ENDED[row.state]
  if (ended) return { tone: ended.tone, isPulsing: false }
  if (row.state === 'working' && !isRunning) return { tone: 'fail', isPulsing: false }
  return { tone: 'now', isPulsing: true }
}

// Whether any dot is pulsing, so the pane only redraws fast while one is.
export function isPulsing(seen: Seen | null): boolean {
  return !!seen?.isLocked && !!seen.status?.issues.some(r => dot(r, true).isPulsing)
}

const pad = (n: number): string => String(n).padStart(2, '0')
const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

// How long, the way a person reads it: 42s, 6m 05s, 1h 04m.
export function duration(ms: number): string {
  const s = Math.max(0, Math.floor(ms / 1000))
  if (s < 60) return `${s}s`
  const m = Math.floor(s / 60)
  if (m < 60) return `${m}m ${pad(s % 60)}s`
  return `${Math.floor(m / 60)}h ${pad(m % 60)}m`
}

// When a job started and how long it has been running, or took. loop.py writes local time with no
// zone, which Date.parse reads as local too. A start on another day carries its date. A row from an
// older loop.py has no start, so no clock.
export function clock(row: Row, isRunning: boolean, now: number): string | null {
  const from = row.started ? Date.parse(row.started) : Number.NaN
  if (!Number.isFinite(from)) return null
  const at = new Date(from)
  const time = `${pad(at.getHours())}:${pad(at.getMinutes())}`
  const when = at.toDateString() === new Date(now).toDateString() ? time : `${MONTHS[at.getMonth()]} ${at.getDate()} ${time}`
  if (dot(row, isRunning).isPulsing) return `started ${when} · running ${duration(now - from)}`
  const end = row.updated ? Date.parse(row.updated) : Number.NaN
  if (!Number.isFinite(end)) return `started ${when}`
  return `started ${when} · ${ENDED[row.state] ? 'took' : 'ran'} ${duration(end - from)}`
}

// A short line for each issue that has just reached an end: a pull request, a block or a stop.
// The first look has nothing to compare with, so it says nothing: opening the pane isn't news.
export function changes(before: Status | null, after: Status | null): string[] {
  if (!before || !after) return []
  const was = new Map((before?.issues ?? []).map(r => [r.number, r.state]))
  const out: string[] = []
  for (const row of after.issues) {
    if (was.get(row.number) === row.state) continue
    if (row.state === 'pr') out.push(`Loop: #${row.number} has a pull request`)
    else if (row.state === 'blocked') out.push(`Loop: #${row.number} is blocked`)
    else if (row.state === 'stopped') out.push(`Loop: #${row.number} stopped`)
  }
  return out
}

// The process id in .loop/lock, or null when it isn't a number.
export function lockPid(text: string): number | null {
  const pid = Number.parseInt(text.trim(), 10)
  return Number.isInteger(pid) && pid > 0 ? pid : null
}

// Fit one line to the pane, with an ellipsis where it was cut.
export function clip(text: string, width: number): string {
  if (width < 2) return ''
  return text.length <= width ? text : text.slice(0, width - 1) + '…'
}

// The nearest folder at or above `from` that holds the loop script. None means no loop here.
export async function findRoot(from: string, exists: (path: string) => Promise<boolean>): Promise<string | null> {
  let dir = from.replace(/\/+$/, '')
  while (dir) {
    if (await exists(`${dir}/${SCRIPT}`)) return dir
    dir = dir.slice(0, dir.lastIndexOf('/'))
  }
  return null
}

// Whether two looks differ in anything the pane draws.
export function sameSeen(a: Seen | null, b: Seen | null): boolean {
  return JSON.stringify(a) === JSON.stringify(b)
}
