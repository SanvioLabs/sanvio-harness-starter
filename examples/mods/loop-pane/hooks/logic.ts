// The pane's decisions as plain functions, so they can be tested without a session.
import type { QueueItem, Row, Seen, Status } from '../types'

export type Tone = 'now' | 'pass' | 'fail' | 'quiet'
export type Line = { tone: Tone; text: string }

export const STATUS_FILE = '.loop/status.json'
export const LOCK_FILE = '.loop/lock'
export const STOP_FILE = '.loop/STOP'
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
      updated: orNull(r.updated) ?? undefined,
    }))
  return { running: data.running === true, updated: orNull(data.updated), queue, issues }
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
