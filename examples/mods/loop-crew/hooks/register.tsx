import { atom, read, update } from 'claude-code'
import type { EngineInterface, Register } from 'claude-code'

import { FRAME_MS, PROJECTS_DIR, act, clip, figureCells, findRoot, fitting, lockPid, loopDir, parseStatus, scene, stepLine, svg, word } from './logic'
import type { Seen } from '../types'

const PANE = 'loop-crew'
const COMMAND = 'loop-crew'
const POLL_MS = 2000
// A figure's Raster and the room its text gives up: the Raster's 16 columns and the two spaces after.
const FIGURE_COLUMNS = 16
const FIGURE_HEIGHT = 8
const BESIDE_FIGURE = FIGURE_COLUMNS + 2

const launchAtom = atom({ plugin: 'loop-crew', key: 'launch' } as const, null)
const shownAtom = atom({ plugin: 'loop-crew', key: 'shown' } as const, '')
const seenAtom = atom({ plugin: 'loop-crew', key: 'seen' } as const, null)

let stopPolling: (() => void) | null = null
let stopFrames: (() => void) | null = null
// Not an atom: a write would redraw the pane, and the frames are painted with no redraw. A drawing
// reads it, so a redraw keeps each figure on its current frame.
let frame = 0

const figureKey = (n: number): string => `figure-${n}`
const paneIsUp = async ($: EngineInterface): Promise<boolean> => (await $.ui.panes()).some(pane => pane.id === PANE)

// The folder saved at session.start first, then the session's root: a /clear starts a new session
// without a session.start, so the saved folder can be missing or the last session's.
async function rootOf($: EngineInterface): Promise<string | null> {
  const exists = (path: string) => $.fs.exists(path)
  const launch = await read($, launchAtom)
  return (launch && (await findRoot(launch, exists))) || findRoot(await $.session.root(), exists)
}

// Whether the process named in the lock is alive. A killed run leaves its lock behind.
async function lockHolderAlive($: EngineInterface, root: string, project?: string): Promise<boolean | null> {
  const text = await $.fs.read(`${root}/${loopDir(project)}/lock`).catch(() => null)
  if (text === null) return null
  const pid = lockPid(text)
  if (pid === null) return true
  const ran = await $.process.run(['kill', '-0', String(pid)]).catch(() => null)
  // kill -0 also fails on another user's process; count only "no such process" as gone.
  return !ran || ran.exitCode === 0 || !/no such process/i.test(ran.stderr)
}

// One look at one loop's files. It only reads: the loop is the only writer.
async function look($: EngineInterface, root: string, project?: string): Promise<Seen> {
  const text = await $.fs.read(`${root}/${loopDir(project)}/status.json`).catch(() => null)
  const isLive = (await lockHolderAlive($, root, project)) === true
  return { ...(project ? { project } : {}), status: parseStatus(text), isLive }
}

// Read the shown loop, and ask for a redraw only when the read differs from the last. A read that a
// switch overtook is dropped. The project is part of what's compared, so a switch always counts.
async function refresh($: EngineInterface): Promise<void> {
  const root = await rootOf($)
  if (!root) return
  const name = await read($, shownAtom)
  const next = await look($, root, name || undefined)
  if ((await read($, shownAtom)) !== name) return
  if (JSON.stringify(await read($, seenAtom)) === JSON.stringify(next)) return
  await update($, seenAtom, () => next)
  $.ui.invalidate('ui.render')
}

// Poll only while the pane is up, so a session that never opens it reads nothing.
function startPolling($: EngineInterface): void {
  if (stopPolling) return
  const timer = $.clock.every(POLL_MS, () => {
    void (async () => {
      if (await paneIsUp($)) return refresh($)
      stopPolling?.()
      stopPolling = null
    })().catch(() => {})
  })
  stopPolling = () => timer.cancel()
}

// A figure that isn't mounted, one past the fit or one gone since the last read, answers with a deny
// or a rejection. Neither matters: the next tick paints again.
async function paint($: EngineInterface, key: string, step: string): Promise<void> {
  try {
    await $.ui.blit({ requestId: PANE, key, cells: figureCells(step, frame) })
  } catch {
    // Ignored, as above.
  }
}

// Move every figure on a frame by painting it, never by redrawing the pane. Started from a terminal
// drawing, so other surfaces, where SMIL does this, run no timer.
function startFrames($: EngineInterface): void {
  if (stopFrames) return
  frame = 0
  const timer = $.clock.every(FRAME_MS, () => {
    void (async () => {
      if (!(await paneIsUp($))) {
        stopFrames?.()
        stopFrames = null
        return
      }
      frame++
      const { rows } = scene(await read($, seenAtom))
      await Promise.all(rows.map(row => paint($, figureKey(row.number), row.step)))
    })().catch(() => {})
  })
  stopFrames = () => timer.cancel()
}

export const register: Register = on => {
  on('session.start', async ($, e, next) => {
    // A reload fires session.start again; the directory the session started in is the first one.
    await update($, launchAtom, prev => prev ?? e.cwd)
    await $.command.register({
      name: COMMAND,
      description: 'A pane of animated figures, one for each issue the loop is working on, each acting out its step',
      argumentHint: '[project]',
    })
    // A pane left open across a reload keeps updating. The load's own drawing restarts its frames.
    if (await paneIsUp($)) startPolling($)
    return next(e)
  })

  on('command.run', { command: COMMAND }, async ($, e) => {
    try {
      const name = e.args.trim()
      const root = await rootOf($)
      if (!root) return { text: `No scripts/loop.py at or above ${await $.session.root()}, so there is no loop to show.` }
      if (name) {
        // Only a name the folder lists, exactly, so nothing typed can reach outside it.
        const entries = await $.fs.list(`${root}/${PROJECTS_DIR}`).catch(() => [])
        if (!entries.some(entry => entry.kind === 'dir' && entry.name === name)) {
          return { text: `No loop for ${name} under .loop/projects/.` }
        }
      }
      const isShown = (await $.ui.panes()).some(pane => pane.id === PANE && pane.isShown)
      if (isShown && (await read($, shownAtom)) === name) {
        try {
          await $.ui.close({ id: PANE })
          return { text: 'Loop crew closed.' }
        } catch {
          return { text: "The loop crew pane couldn't close. The × in its corner closes it." }
        }
      }
      await update($, shownAtom, () => name)
      await refresh($)
      // On a pane already open this retitles it.
      const opened = await $.ui.open({ id: PANE, title: name ? `Loop crew: ${name}` : 'Loop crew' })
      startPolling($)
      return { text: opened.isPlaced ? 'Loop crew opened.' : 'Loop crew opened. Widen the terminal to see it.' }
    } catch {
      return { text: "The loop crew pane couldn't open." }
    }
  })

  on('ui.render', { component: 'Pane', requestId: PANE }, async ($, e) => {
    const elements = $.ui.resolve(e)
    const { Box, Text } = elements
    if (e.surface === 'terminal') startFrames($)
    const seen = await read($, seenAtom)
    if (!seen) return <Text dimColor>Looking for the loop…</Text>
    const { message, rows } = scene(seen)
    if (message) return <Text key="message" dimColor>{message}</Text>

    // On the terminal each figure takes 9 rows, its text cut to fit beside it.
    if (e.surface === 'terminal' && 'Raster' in elements) {
      const { Raster } = elements
      const shown = rows.slice(0, fitting(rows.length, e.props.scroll?.bodyRows))
      const room = e.props.bodyColumns - BESIDE_FIGURE
      return (
        <Box flexDirection="column">
          {shown.map(row => (
            <Box key={`issue-${row.number}`} flexDirection="column">
              <Box flexDirection="row">
                <Raster key={figureKey(row.number)} columns={FIGURE_COLUMNS} rows={FIGURE_HEIGHT} cells={figureCells(row.step, frame)} />
                <Box flexDirection="column" marginLeft={2}>
                  <Text bold>{clip(`#${row.number} ${row.title}`, room)}</Text>
                  <Text dimColor>{clip(stepLine(row), room)}</Text>
                </Box>
              </Box>
              <Text> </Text>
            </Box>
          ))}
          {shown.length < rows.length && <Text key="more" dimColor>{`and ${rows.length - shown.length} more`}</Text>}
        </Box>
      )
    }

    // Every other surface shows them all, animated by the document itself, and wraps the text.
    const Svg = 'Svg' in elements ? elements.Svg : null
    return (
      <Box flexDirection="column" rowGap={1}>
        {rows.map(row => (
          <Box key={`issue-${row.number}`} flexDirection="row" columnGap={2}>
            {Svg && <Svg key={figureKey(row.number)} source={svg(act(row.step))} alt={`Issue #${row.number}: ${word(row.step)}`} isInteractive />}
            <Box flexDirection="column">
              <Text bold>{`#${row.number} ${row.title}`}</Text>
              <Text dimColor>{stepLine(row)}</Text>
            </Box>
          </Box>
        ))}
      </Box>
    )
  })
}
