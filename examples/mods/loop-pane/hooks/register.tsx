import { atom, read, update } from 'claude-code'
import type { EngineInterface, Register } from 'claude-code'

import { LOCK_FILE, PAGE, STATUS_FILE, STOP_FILE, TABS, WATCH_FILE, attach, changes, clip, clock, describe, dot, findRoot, firstTab, header, isPulsing, jobAttach, jobWatchFile, lists, lockPid, page, parseStatus, sameSeen, waitingOn, watch, watchCommand } from './logic'
import type { Lists, Tone } from './logic'
import type { Row, Seen, Tab, View } from '../types'

const PANE = 'loop'
// Not /loop: that's Claude Code's own command for running a prompt on a schedule.
const COMMAND = 'loop-pane'
const POLL_MS = 2000
// The pulse's half beat. The pane redraws this often only while a job's dot is pulsing.
const TICK_MS = 500

const launchAtom = atom({ plugin: 'loop-pane', key: 'launch' } as const, null)
const seenAtom = atom({ plugin: 'loop-pane', key: 'seen' } as const, null)
const viewAtom = atom({ plugin: 'loop-pane', key: 'view' } as const, null)

const COLORS: Record<Tone, { color?: string; bold?: boolean; dimColor?: boolean }> = {
  now: { color: 'cyan', bold: true },
  pass: { color: 'green', bold: true },
  fail: { color: 'red', bold: true },
  quiet: { dimColor: true },
  idle: { color: 'green', dimColor: true },
}

// A working job's dot, on alternate ticks. Bright and dim rather than on and off: a dot that vanishes
// every other frame reads as a redraw glitch.
const PULSE = { bright: { color: 'cyan', bold: true }, dim: { color: 'cyan', dimColor: true } } as const
let beat = true

// A job's rows: its title, where it is, two for the last round's results, and its pull request.
const JOB_ROWS = 5

const EMPTY: Record<Tab, string> = {
  queue: 'Nothing waiting. Label an issue loop-ready to queue it.',
  active: 'Nothing being worked on.',
  finished: 'Nothing finished in the last 24 hours.',
}

let stopPolling: (() => void) | null = null

// Open a read-only Terminal window from a watch file; when it can't, copy the command that does the
// same and say so. Closing the window leaves the loop running.
function openWatch($: EngineInterface, file: string, copy: () => Promise<unknown>): void {
  void (async () => {
    const ran = await $.process.run(['open', file]).catch(() => null)
    if (ran?.exitCode === 0) return
    await copy()
    $.ui.toast("Couldn't open a window, so the read-only attach command is copied")
  })().catch(() => {})
}

// The tab in view and its first job, kept inside the list. Before the person picks, the busiest tab.
function current(view: View | null, l: Lists): View {
  const tab = view?.tab ?? firstTab(l)
  return { tab, start: page(l[tab], view?.tab ? view.start : 0).start }
}

// Move the tab's list by `by` jobs. Says whether it moved: at either end it doesn't.
async function move($: EngineInterface, by: number): Promise<boolean> {
  const seen = await read($, seenAtom)
  const l = lists(seen?.status ?? null, Date.now())
  const now = current(await read($, viewAtom), l)
  const next = page(l[now.tab], now.start + by).start
  if (next === now.start) return false
  await update($, viewAtom, () => ({ tab: now.tab, start: next }))
  return true
}

async function rootOf($: EngineInterface): Promise<string | null> {
  const launch = await read($, launchAtom)
  return launch ? findRoot(launch, path => $.fs.exists(path)) : null
}

// Whether the process named in the lock is alive. A killed run leaves its lock behind.
async function lockHolderAlive($: EngineInterface, root: string): Promise<boolean | null> {
  const text = await $.fs.read(`${root}/${LOCK_FILE}`).catch(() => null)
  if (text === null) return null
  const pid = lockPid(text)
  if (pid === null) return true
  const ran = await $.process.run(['kill', '-0', String(pid)]).catch(() => null)
  // kill -0 also fails on another user's process; count only "no such process" as gone.
  return !ran || ran.exitCode === 0 || !/no such process/i.test(ran.stderr)
}

// One look at the loop's files. It only reads: the loop is the only writer.
async function look($: EngineInterface, root: string): Promise<Seen> {
  const text = await $.fs.read(`${root}/${STATUS_FILE}`).catch(() => null)
  const alive = await lockHolderAlive($, root)
  return {
    root,
    status: parseStatus(text),
    isLocked: alive === true,
    isStaleLock: alive === false,
    isStopping: await $.fs.exists(`${root}/${STOP_FILE}`),
    hasWatchFile: await $.fs.exists(`${root}/${WATCH_FILE}`),
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
  // every() hands back a timer, not a function: calling it threw, so the poll outlived the pane.
  // It ticks at the pulse's pace and reads the loop's files on every POLL_MS / TICK_MS-th tick.
  let ticks = 0
  const timer = $.clock.every(TICK_MS, () => {
    void (async () => {
      const isUp = (await $.ui.panes()).some(pane => pane.id === PANE)
      if (!isUp) {
        stopPolling?.()
        stopPolling = null
        return
      }
      beat = !beat
      const isRead = ticks++ % (POLL_MS / TICK_MS) === 0
      if (isRead) await refresh($)
      // The dot and the running clock move between reads, so redraw for them while a job is on. The
      // header's uptime moves too, so a live loop redraws at least at every read.
      const seen = await read($, seenAtom)
      if (isPulsing(seen) || (isRead && seen?.isLocked)) $.ui.invalidate('ui.render')
    })().catch(() => {})
  })
  stopPolling = () => timer.cancel()
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

  // The wheel and scroll keys move the job list, under a header that stays put. At either end of the
  // list, or with nothing to move, the pane scrolls as usual.
  on('ui.scroll', { component: 'Pane', requestId: PANE }, async ($, e, next) => {
    const moved = e.by !== 0 && (await move($, Math.sign(e.by)).catch(() => false))
    return moved ? {} : next(e)
  })

  on('ui.render', { component: 'Pane', requestId: PANE }, async ($, e) => {
    const { Box, Button, Text } = $.ui.resolve(e)
    const seen = await read($, seenAtom)
    const width = Math.max(10, e.props.bodyColumns)
    // A job's lines sit under its title, past the dot.
    const inner = width - 2
    const now = Date.now()

    if (!seen) return <Text dimColor>Looking for the loop…</Text>

    const top = header(seen, now, width)
    const tmux = attach(seen)
    const watchFile = watch(seen)
    const l = lists(seen.status, now)
    const view = current(await read($, viewAtom), l)
    const queue = page(l.queue, view.start)
    const jobs = view.tab === 'queue' ? null : page(l[view.tab], view.start)
    const { above, below } = jobs ?? queue
    const isEmpty = (jobs ?? queue).shown.length === 0

    // Every job takes the same rows, and the list always takes three jobs' worth, so nothing below it
    // moves as jobs scroll by or gain a result.
    const job = (row: Row) => {
      const { head: state, detail } = describe(row, seen.isLocked)
      const mark = dot(row, seen.isLocked)
      const time = clock(row, seen.isLocked, now)
      const stateText = clip(state.text, inner)
      const jobCommand = jobAttach(seen, row)
      // Every job has a dot, in the same column, so a title never moves as its job starts or ends.
      return (
        <Box key={`issue-${row.number}`} flexDirection="column" marginTop={1} height={JOB_ROWS}>
          <Box flexDirection="row" columnGap={1}>
            <Text {...(mark.isPulsing ? PULSE[beat ? 'bright' : 'dim'] : COLORS[mark.tone])}>●</Text>
            <Text bold>{clip(`#${row.number} ${row.title}`, inner)}</Text>
          </Box>
          <Box flexDirection="column" marginLeft={2}>
            <Box flexDirection="row">
              <Text {...COLORS[state.tone]}>{stateText}</Text>
              {time && <Text dimColor>{clip(` · ${time}`, inner - stateText.length)}</Text>}
            </Box>
            <Box height={2} overflow="hidden">
              <Text dimColor>{detail ? clip(detail, inner * 2) : ' '}</Text>
            </Box>
            {jobCommand || row.pr ? (
              <Box flexDirection="row" columnGap={1}>
                {jobCommand && (
                  <Button
                    key={`watch-${row.number}`}
                    label="Watch"
                    onPress={press =>
                      openWatch($, `${seen.root}/${jobWatchFile(row.number)}`, () =>
                        $.ui.copy({ text: jobCommand, surface: press.surface }))}
                  />
                )}
                {row.pr ? (
                  <Button
                    key={`pr-${row.number}`}
                    label={clip('Copy pull request link', inner)}
                    onPress={press => $.ui.copy({ text: row.pr ?? '', surface: press.surface })}
                  />
                ) : null}
              </Box>
            ) : (
              <Text> </Text>
            )}
          </Box>
        </Box>
      )
    }
    const gap = (n: number, rows: number) =>
      Array.from({ length: n }, (_, i) => <Box key={`gap-${i}`} marginTop={rows > 1 ? 1 : 0} height={rows} />)
    const shownCount = (jobs ?? queue).shown.length

    return (
      <Box flexDirection="column">
        {/* Two rows whatever the state, so nothing under the header moves when it wraps. */}
        <Box key="header" flexDirection="row">
          <Text bold>{top.left}</Text>
          {!top.wraps && <Text>{' '.repeat(width - top.left.length - top.right.text.length)}</Text>}
          {!top.wraps && <Text {...COLORS[top.right.tone]}>{top.right.text}</Text>}
        </Box>
        {top.wraps ? <Text {...COLORS[top.right.tone]}>{top.right.text}</Text> : <Text> </Text>}
        {/* The buttons' row stays when there are none, so the tabs don't move as the loop starts or stops. */}
        {!tmux && <Text key="actions"> </Text>}
        {tmux && (
          <Box key="actions" flexDirection="row" flexWrap="wrap" columnGap={1}>
            {watchFile && (
              <Button
                key="watch"
                label="Watch it"
                onPress={press =>
                  openWatch($, watchFile, () => $.ui.copy({ text: watchCommand(seen) ?? '', surface: press.surface }))}
              />
            )}
            <Button
              key="tmux"
              label="Copy attach command"
              onPress={press => $.ui.copy({ text: tmux, surface: press.surface })}
            />
          </Box>
        )}
        <Text dimColor>{'─'.repeat(width)}</Text>
        <Box flexDirection="row" flexWrap="wrap" columnGap={1}>
          {TABS.map(({ tab, label }) => (
            <Button
              key={`tab-${tab}`}
              label={`${label} ${l[tab].length}`}
              variant={tab === view.tab ? 'primary' : undefined}
              dimColor={tab !== view.tab}
              onPress={() => update($, viewAtom, () => ({ tab, start: 0 }))}
            />
          ))}
        </Box>
        {/* The lines above and below the list are always there, so it doesn't jump as it scrolls. */}
        {above > 0 ? (
          <Button key="up" plain label={`▲ ${above} more`} dimColor onPress={() => move($, -1)} />
        ) : (
          <Text> </Text>
        )}
        {isEmpty && (
          <Box marginTop={jobs ? 1 : 0} height={jobs ? JOB_ROWS : 1} overflow="hidden">
            <Text dimColor>{clip(EMPTY[view.tab], width)}</Text>
          </Box>
        )}
        {jobs
          ? jobs.shown.map(job)
          : queue.shown.map(q => {
              // The title gives way to what it waits on, down to a short stub.
              const note = waitingOn(q)
              const tag = note ? ` · ${note}` : ''
              const title = clip(`#${q.number} ${q.title}`, Math.max(width - tag.length, Math.min(width, 16)))
              return (
                <Box key={`queue-${q.number}`} flexDirection="row">
                  <Text>{title}</Text>
                  {tag ? <Text dimColor>{clip(tag, width - title.length)}</Text> : null}
                </Box>
              )
            })}
        {gap(PAGE - shownCount - (isEmpty ? 1 : 0), jobs ? JOB_ROWS : 1)}
        {below > 0 ? (
          <Button key="down" plain label={`▼ ${below} more`} dimColor onPress={() => move($, 1)} />
        ) : (
          <Text> </Text>
        )}
      </Box>
    )
  })
}
