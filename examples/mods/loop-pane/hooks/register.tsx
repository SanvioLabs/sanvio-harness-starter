import { atom, read, update } from 'claude-code'
import type { EngineInterface, Register } from 'claude-code'

import { LOCK_FILE, STATUS_FILE, STOP_FILE, changes, clip, describe, findRoot, headline, parseStatus, sameSeen, waiting } from './logic'
import type { Tone } from './logic'
import type { Seen } from '../types'

const PANE = 'loop'
// Not /loop: that's Claude Code's own command for running a prompt on a schedule.
const COMMAND = 'loop-pane'
const POLL_MS = 2000

const launchAtom = atom({ plugin: 'loop-pane', key: 'launch' } as const, null)
const seenAtom = atom({ plugin: 'loop-pane', key: 'seen' } as const, null)

const COLORS: Record<Tone, { color?: string; bold?: boolean; dimColor?: boolean }> = {
  now: { color: 'cyan', bold: true },
  pass: { color: 'green', bold: true },
  fail: { color: 'red', bold: true },
  quiet: { dimColor: true },
}

let stopPolling: (() => void) | null = null

async function rootOf($: EngineInterface): Promise<string | null> {
  const launch = await read($, launchAtom)
  return launch ? findRoot(launch, path => $.fs.exists(path)) : null
}

// One look at the loop's files. It only reads: the loop is the only writer.
async function look($: EngineInterface, root: string): Promise<Seen> {
  const text = await $.fs.read(`${root}/${STATUS_FILE}`).catch(() => null)
  return {
    root,
    status: parseStatus(text),
    isLocked: await $.fs.exists(`${root}/${LOCK_FILE}`),
    isStopping: await $.fs.exists(`${root}/${STOP_FILE}`),
  }
}

async function refresh($: EngineInterface): Promise<void> {
  const root = await rootOf($)
  if (!root) return
  const now = await look($, root)
  const before = await read($, seenAtom)
  if (sameSeen(before, now)) return
  await update($, seenAtom, () => now)
  for (const line of changes(before?.status ?? null, now.status)) $.ui.toast(line)
  $.ui.invalidate('ui.render')
}

// Poll only while the pane is up, so a session that never opens it reads nothing.
function startPolling($: EngineInterface): void {
  if (stopPolling) return
  stopPolling = $.clock.every(POLL_MS, () => {
    void (async () => {
      const isUp = (await $.ui.panes()).some(pane => pane.id === PANE)
      if (!isUp) {
        stopPolling?.()
        stopPolling = null
        return
      }
      await refresh($)
    })().catch(() => {})
  })
}

export const register: Register = on => {
  on('session.start', async ($, e, next) => {
    // A reload fires session.start again; the directory the session started in is the first one.
    await update($, launchAtom, prev => prev ?? e.cwd)
    await $.command.register({
      name: COMMAND,
      description: "Open a pane showing the loop: what's waiting, what each issue is on, and its pull request",
    })
    // A pane left open across a reload keeps updating.
    if ((await $.ui.panes()).some(pane => pane.id === PANE)) startPolling($)
    return next(e)
  })

  on('command.run', { command: COMMAND }, async $ => {
    try {
      const root = await rootOf($)
      if (!root) return { text: 'No scripts/loop.py at or above the folder this session started in, so there is no loop to show.' }
      await refresh($)
      const opened = await $.ui.open({ id: PANE, title: 'Loop' })
      startPolling($)
      return { text: opened.isPlaced ? 'Loop pane opened.' : 'Loop pane opened. Widen the terminal to see it.' }
    } catch {
      return { text: "The loop pane couldn't open. .loop/loop.log has the same story: tail -f .loop/loop.log" }
    }
  })

  on('ui.render', { component: 'Pane', requestId: PANE }, async ($, e) => {
    const { Box, Button, Text } = $.ui.resolve(e)
    const seen = await read($, seenAtom)
    const width = Math.max(10, e.props.bodyColumns)

    if (!seen) return <Text dimColor>Looking for the loop…</Text>

    const head = headline(seen)
    const queue = waiting(seen.status)
    const rows = seen.status?.issues ?? []

    return (
      <Box flexDirection="column">
        <Text {...COLORS[head.tone]}>{clip(head.text, width)}</Text>
        <Text dimColor>{clip(`${queue.length} waiting${queue.length ? `: ${queue.map(q => `#${q.number}`).join(' ')}` : ''}`, width)}</Text>
        {rows.length === 0 && (
          <Text dimColor>{clip('No issue taken yet. Label one loop-ready, then: python3 scripts/loop.py run --once', width * 3)}</Text>
        )}
        {rows.map(row => {
          const { head: state, detail } = describe(row, seen.isLocked)
          return (
            <Box key={`issue-${row.number}`} flexDirection="column" marginTop={1}>
              <Text bold>{clip(`#${row.number} ${row.title}`, width)}</Text>
              <Text {...COLORS[state.tone]}>{clip(state.text, width)}</Text>
              {detail && <Text dimColor>{clip(detail, width * 2)}</Text>}
              {row.pr && (
                <Button
                  key={`pr-${row.number}`}
                  label={clip('Copy pull request link', width)}
                  onPress={press => $.ui.copy({ text: row.pr ?? '', surface: press.surface })}
                />
              )}
            </Box>
          )
        })}
      </Box>
    )
  })
}
