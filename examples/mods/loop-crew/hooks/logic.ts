// The figures' decisions and drawings as plain functions, so they can be tested without a session.
import type { Row, Seen, Status } from '../types'

export const PROJECTS_DIR = '.loop/projects'
export const SCRIPT = 'scripts/loop.py'
export const FRAME_MS = 250
// A figure's rows on the terminal: its Raster's 8 and the blank one after it.
export const FIGURE_ROWS = 9

// The folder under the root holding one loop's files: the harness's, or a project's.
export function loopDir(project?: string): string {
  return project ? `${PROJECTS_DIR}/${project}` : '.loop'
}

const str = (v: unknown): string => (typeof v === 'string' ? v : '')
const num = (v: unknown): number => (typeof v === 'number' && Number.isFinite(v) ? v : 0)

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
  const rows = (raw as Record<string, unknown>).issues
  const issues: Row[] = (Array.isArray(rows) ? rows : [])
    .filter((r): r is Record<string, unknown> => !!r && typeof r === 'object' && num((r as Record<string, unknown>).number) > 0)
    .map(r => ({ number: num(r.number), title: str(r.title), step: str(r.step), state: str(r.state), round: num(r.round) }))
  return { issues }
}

// The process id in the lock, or null when it isn't a number.
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

const WORDS: Record<string, string> = {
  SHAPE: 'planning',
  TEST: 'writing tests',
  BUILD: 'building',
  VALIDATE: 'checking',
  SCALE: 'opening the pull request',
}

// What a step reads as. A step this doesn't know is shown lowercased, as written.
export function word(step: string): string {
  return Object.keys(WORDS).includes(step) ? WORDS[step]! : step.toLowerCase() || 'starting'
}

export function roundText(round: number): string {
  return round > 0 ? `round ${round}` : ''
}

// A figure's second line: building, round 2. The word alone at round 0.
export function stepLine(row: Row): string {
  return [word(row.step), roundText(row.round)].filter(Boolean).join(', ')
}

// What the pane says instead of figures, or the figures, in issue-number order. The lock is the truth
// about running: rows left at working by a killed run draw nothing.
export function scene(seen: Seen | null): { message: string | null; rows: Row[] } {
  if (!seen?.status) return { message: 'No loop has run here yet.', rows: [] }
  if (!seen.isLive) return { message: "The loop isn't running.", rows: [] }
  const rows = seen.status.issues.filter(r => r.state === 'working').sort((a, b) => a.number - b.number)
  return rows.length ? { message: null, rows } : { message: 'Nothing being built right now.', rows: [] }
}

// How many of `count` figures to draw in `bodyRows`: all that fit, or as many as leave one row for
// the "and n more" line, and never fewer than one. A height that isn't there gives 3.
export function fitting(count: number, bodyRows?: number): number {
  const room = bodyRows !== undefined && Number.isFinite(bodyRows)
    ? (count * FIGURE_ROWS <= bodyRows ? count : Math.max(1, Math.floor((bodyRows - 1) / FIGURE_ROWS)))
    : 3
  return Math.min(count, room)
}

// One step's animation: 2 to 4 frames, each 16 strings of 16 pixels, each pixel a key in the palette.
export type Act = { palette: Record<string, number>; frames: string[][] }

// '.' is a fixed dark backdrop, so a figure looks the same on a light surface and a dark one.
const FIGURE = { '.': 0x1a1d23, h: 0x8a5a2b, s: 0xe8b88a, b: 0x4c72b0, l: 0x3f5f8f, f: 0x9a6b45 }

const SHAPE: Act = {
  palette: { ...FIGURE, d: 0xd9c9a3, i: 0x4c72b0, p: 0xdd8452, w: 0x8a6a45 },
  frames: [
    [
      '................',
      '...hhhh.........',
      '...hhhh.........',
      '...ssss..dddddd.',
      '...ssss..diiiid.',
      '..bbbbbbspddddd.',
      '..bbbbbb.diiddd.',
      '.sbbbbbb.dddddd.',
      '.sbbbbbb.dddddd.',
      '..bbbbbb...ww...',
      '...llll....ww...',
      '...l..l....ww...',
      '...l..l....ww...',
      '...l..l...w..w..',
      '..ff..ff.w....w.',
      '................',
    ],
    [
      '................',
      '...hhhh.........',
      '...hhhh.........',
      '...ssss..dddddd.',
      '...ssss..diiiid.',
      '..bbbbbbssspddd.',
      '..bbbbbb.diiiid.',
      '.sbbbbbb.dddddd.',
      '.sbbbbbb.dddddd.',
      '..bbbbbb...ww...',
      '...llll....ww...',
      '...l..l....ww...',
      '...l..l....ww...',
      '...l..l...w..w..',
      '..ff..ff.w....w.',
      '................',
    ],
  ],
}

const TEST: Act = {
  palette: { ...FIGURE, o: 0x8a6a45, W: 0xf2f2ee, g: 0x3a9d5d, k: 0xc0392b },
  frames: [
    [
      '................',
      '...hhhh.oooooooo',
      '...hhhh.oWWWWWWo',
      '...ssss.oWggWWWo',
      '...ssss.oWWWWWWo',
      '..bbbbbbskWWWWWo',
      '..bbbbbboWWWWWWo',
      '.sbbbbbboWWWWWWo',
      '.sbbbbbboWWWWWWo',
      '..bbbbbboooooooo',
      '...llll.........',
      '...l..l.........',
      '...l..l.........',
      '...l..l.........',
      '..ff..ff........',
      '................',
    ],
    [
      '................',
      '...hhhh.oooooooo',
      '...hhhh.oWWWWWWo',
      '...ssss.oWggggWo',
      '...ssss.oWWWWWWo',
      '..bbbbbbsskWWWWo',
      '..bbbbbboWWWWWWo',
      '.sbbbbbboWWWWWWo',
      '.sbbbbbboWWWWWWo',
      '..bbbbbboooooooo',
      '...llll.........',
      '...l..l.........',
      '...l..l.........',
      '...l..l.........',
      '..ff..ff........',
      '................',
    ],
    [
      '................',
      '...hhhh.oooooooo',
      '...hhhh.oWWWWWWo',
      '...ssss.oWggggWo',
      '...ssss.oWWWWWWo',
      '..bbbbbbssskWWWo',
      '..bbbbbboWggWWWo',
      '.sbbbbbboWWWWWWo',
      '.sbbbbbboWWWWWWo',
      '..bbbbbboooooooo',
      '...llll.........',
      '...l..l.........',
      '...l..l.........',
      '...l..l.........',
      '..ff..ff........',
      '................',
    ],
  ],
}

const BUILD: Act = {
  palette: { ...FIGURE, m: 0xa8b0b8, w: 0x8a6a45, n: 0xd9c9a3, a: 0x5a6068 },
  frames: [
    [
      '..........mmmm..',
      '...hhhh...mmmm..',
      '...hhhh....w....',
      '...ssss....w....',
      '...ssss...ss....',
      '..bbbbbbbss.....',
      '..bbbbbb........',
      '.sbbbbbb........',
      '.sbbbbbb........',
      '..bbbbbb........',
      '...llll.........',
      '...l..l.........',
      '...l..l.....nn..',
      '...l..l.....nn..',
      '..ff..ff...aaaaa',
      '...........aaaaa',
    ],
    [
      '................',
      '...hhhh.........',
      '...hhhh.........',
      '...ssss......mm.',
      '...ssss......mm.',
      '..bbbbbbsswwwmm.',
      '..bbbbbb.....mm.',
      '.sbbbbbb.....mm.',
      '.sbbbbbb........',
      '..bbbbbb........',
      '...llll.........',
      '...l..l.........',
      '...l..l.....nn..',
      '...l..l.....nn..',
      '..ff..ff...aaaaa',
      '...........aaaaa',
    ],
    [
      '................',
      '...hhhh.........',
      '...hhhh.........',
      '...ssss.........',
      '...ssss.........',
      '..bbbbbbss......',
      '..bbbbbb..ww....',
      '.sbbbbbb...ww...',
      '.sbbbbbb....ww..',
      '..bbbbbb...mmmm.',
      '...llll....mmmm.',
      '...l..l.........',
      '...l..l.....nn..',
      '...l..l.....nn..',
      '..ff..ff...aaaaa',
      '...........aaaaa',
    ],
  ],
}

const VALIDATE: Act = {
  palette: { ...FIGURE, r: 0xa8b0b8, c: 0x8fd3e8, W: 0xf2f2ee, w: 0x8a6a45 },
  frames: [
    [
      '................',
      '...hhhh...rrrr..',
      '...hhhh..rccccr.',
      '...ssss..rccccr.',
      '...ssss..rccccr.',
      '..bbbbbb..rrrr..',
      '..bbbbbb.ww.....',
      '.sbbbbbbss......',
      '.sbbbbbb........',
      '..bbbbbb........',
      '...llll.........',
      '...l..l.........',
      '...l..l.........',
      '...l..l.........',
      '..ff..ff........',
      '................',
    ],
    [
      '..........rrrr..',
      '...hhhh..rccccr.',
      '...hhhh..rcWccr.',
      '...ssss..rccccr.',
      '...ssss...rrrr..',
      '..bbbbbb..ww....',
      '..bbbbbb.ww.....',
      '.sbbbbbbss......',
      '.sbbbbbb........',
      '..bbbbbb........',
      '...llll.........',
      '...l..l.........',
      '...l..l.........',
      '...l..l.........',
      '..ff..ff........',
      '................',
    ],
  ],
}

const SCALE: Act = {
  palette: { ...FIGURE, x: 0xc49a6c, t: 0x8a6a45 },
  frames: [
    [
      '................',
      '...hhhh.........',
      '...hhhh.........',
      '...ssss.........',
      '...ssss..xxxxxx.',
      '..bbbbbb.xxttxx.',
      '..bbbbbb.xxttxx.',
      '..bbbbbbssxttxx.',
      '..bbbbbb.xxxxxx.',
      '..bbbbbb........',
      '...llll.........',
      '...l..l.........',
      '...l..l.........',
      '...l..l.........',
      '..ff..ff........',
      '................',
    ],
    [
      '................',
      '...hhhh.........',
      '...hhhh.........',
      '...ssss.........',
      '...ssss..xxxxxx.',
      '..bbbbbb.xxttxx.',
      '..bbbbbb.xxttxx.',
      '..bbbbbbssxttxx.',
      '..bbbbbb.xxxxxx.',
      '..bbbbbb........',
      '...llll.........',
      '..ll..ll........',
      '.ll....ll.......',
      '.l......l.......',
      'ff......ff......',
      '................',
    ],
  ],
}

// Standing still, for any step that has no act of its own.
export const STILL: Act = {
  palette: FIGURE,
  frames: [
    [
      '................',
      '......hhhh......',
      '......hhhh......',
      '......ssss......',
      '......ssss......',
      '.....bbbbbb.....',
      '....sbbbbbbs....',
      '....sbbbbbbs....',
      '....sbbbbbbs....',
      '.....bbbbbb.....',
      '......llll......',
      '......l..l......',
      '......l..l......',
      '......l..l......',
      '.....ff..ff.....',
      '................',
    ],
  ],
}

export const ACTS: Record<string, Act> = { SHAPE, TEST, BUILD, VALIDATE, SCALE }

export function act(step: string): Act {
  return Object.keys(ACTS).includes(step) ? ACTS[step]! : STILL
}

const ALPHABET = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/'

// The cells as a Raster takes them: little-endian u32s, as padded base64.
export function encode(cells: Uint32Array): string {
  const bytes = new Uint8Array(cells.length * 4)
  const view = new DataView(bytes.buffer)
  cells.forEach((word, i) => view.setUint32(i * 4, word, true))
  let out = ''
  for (let i = 0; i < bytes.length; i += 3) {
    const [a, b, c] = [bytes[i] ?? 0, bytes[i + 1] ?? 0, bytes[i + 2] ?? 0]
    const n = (a << 16) | (b << 8) | c
    out += ALPHABET[(n >> 18) & 63]! + ALPHABET[(n >> 12) & 63]!
    out += i + 1 < bytes.length ? ALPHABET[(n >> 6) & 63]! : '='
    out += i + 2 < bytes.length ? ALPHABET[n & 63]! : '='
  }
  return out
}

const UPPER_HALF = 0x2580

// A frame as a Raster's cells, 16 by 8: an upper half block in every cell, its top pixel the
// foreground and its bottom pixel the background.
export function cells(frame: string[], palette: Record<string, number>): string {
  const out = new Uint32Array(16 * 8 * 3)
  const colour = (x: number, y: number): number => palette[frame[y]?.[x] ?? '.'] ?? 0
  for (let row = 0; row < 8; row++) {
    for (let x = 0; x < 16; x++) out.set([UPPER_HALF, colour(x, row * 2), colour(x, row * 2 + 1)], (row * 16 + x) * 3)
  }
  return encode(out)
}

// The cells of a step's frame at this tick of the frame counter.
export function figureCells(step: string, tick: number): string {
  const { frames, palette } = act(step)
  return cells(frames[tick % frames.length]!, palette)
}

const hex = (colour: number): string => `#${colour.toString(16).padStart(6, '0')}`

// One frame's pixels as rects, a run of one colour on a row being one rect.
function rects(frame: string[], palette: Record<string, number>): string {
  let out = ''
  frame.forEach((line, y) => {
    for (let x = 0; x < line.length;) {
      let end = x + 1
      while (line[end] === line[x]) end++
      out += `<rect x="${x}" y="${y}" width="${end - x}" height="1" fill="${hex(palette[line[x]!] ?? 0)}"/>`
      x = end
    }
  })
  return out
}

// A frame's turn in the loop of n, as a discrete animation of its visibility. Only colours and shapes
// reach the document: no text from the status file does.
function turn(i: number, n: number): string {
  const times = [...(i > 0 ? [0] : []), i / n, ...(i + 1 < n ? [(i + 1) / n] : [])]
  const values = [...(i > 0 ? ['hidden'] : []), 'visible', ...(i + 1 < n ? ['hidden'] : [])]
  return `<animate attributeName="visibility" calcMode="discrete" values="${values.join(';')}" ` +
    `keyTimes="${times.map(t => t.toFixed(4)).join(';')}" dur="${n * FRAME_MS}ms" repeatCount="indefinite"/>`
}

// An act as one Svg document: a group per frame, shown in turn with SMIL. Where SMIL doesn't run the
// first frame stands still. A one-frame act has nothing to animate.
export function svg(a: Act): string {
  const n = a.frames.length
  const groups = a.frames.map((frame, i) =>
    `<g${i > 0 ? ' visibility="hidden"' : ''}>${rects(frame, a.palette)}${n > 1 ? turn(i, n) : ''}</g>`)
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" width="64" height="64" shape-rendering="crispEdges">${groups.join('')}</svg>`
}
