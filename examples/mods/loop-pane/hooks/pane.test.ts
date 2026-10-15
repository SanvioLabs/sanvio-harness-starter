import { describe as group, expect, test } from 'claude-code/testing'
import type { On } from 'claude-code'

import type { Seen } from '../types'

const SEEN = (hasWatchFile: boolean): Seen => ({
  root: '/h/starter',
  status: { running: true, updated: null, tmux: 'loop-starter', queue: [], issues: [] },
  isLocked: true,
  isStaleLock: false,
  isStopping: false,
  hasWatchFile,
})

// Stands in for the pane's last look at the loop's files.
function seed(on: On, seen: Seen): void {
  on('state.get', async (_$, e, next) =>
    e.plugin === 'loop-pane' && e.key === 'seen' ? { value: { value: seen, version: 1 } } : next(e))
}

// The press runs the open in the background; let it finish.
async function drain(): Promise<void> {
  for (let i = 0; i < 20; i++) await Promise.resolve()
}

const PANE = {
  plugin: 'loop-pane',
  surface: 'terminal',
  component: 'Pane',
  requestId: 'loop',
  props: { title: 'Loop', isFocused: true, bodyColumns: 60, placement: 'dock', scroll: { offset: 0, bodyRows: 30 }, view: {} },
} as const

group('the Watch it button', () => {
  test('opens the watch file', async ($, on) => {
    const ran: string[][] = []
    on('process.run', async (_$, e) => {
      ran.push([...e.argv])
      return { value: { exitCode: 0, stdout: '', stderr: '', isStdoutTruncated: false, isStderrTruncated: false } }
    })
    seed(on, SEEN(true))
    const ui = await $.ui.mount(PANE)
    await ui.press({ key: 'watch' })
    await drain()
    expect(ran).toEqual([['open', '/h/starter/.loop/watch.command']])
    await ui.unmount()
  })
  test("copies the read-only attach command when the window can't open", async ($, on) => {
    const copied: string[] = []
    on('process.run', async () => ({ value: { exitCode: 1, stdout: '', stderr: 'no', isStdoutTruncated: false, isStderrTruncated: false } }))
    const toasts: string[] = []
    on('ui.copy', async (_$, e) => {
      copied.push(e.text)
      return { value: { isCopied: true } }
    })
    on('ui.toast', async (_$, e) => {
      toasts.push(e.text)
      return { value: undefined }
    })
    seed(on, SEEN(true))
    const ui = await $.ui.mount(PANE)
    await ui.press({ key: 'watch' })
    await drain()
    expect(copied).toEqual(["tmux attach -r -t '=loop-starter'"])
    expect(toasts.length).toBe(1)
    await ui.unmount()
  })
  test('is absent without the watch file', async ($, on) => {
    seed(on, SEEN(false))
    const ui = await $.ui.mount(PANE)
    expect(await ui.find({ key: 'watch' })).toBeUndefined()
    expect(await ui.find({ key: 'tmux' })).toBeDefined()
    await ui.unmount()
  })
})

// A local time, as loop.py writes it, `hours` ago.
function hoursAgo(hours: number): string {
  const d = new Date(Date.now() - hours * 3600_000)
  const two = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${two(d.getMonth() + 1)}-${two(d.getDate())}T${two(d.getHours())}:${two(d.getMinutes())}:${two(d.getSeconds())}`
}

const FINISHED = (number: number, hours: number) => ({
  number, title: `job ${number}`, step: 'SCALE', state: 'pr', round: 1, tests: 'passed', review: 'PASS',
  pr: `https://example.test/pull/${number}`, note: '', updated: hoursAgo(hours),
})

const MANY: Seen = {
  root: '/h/starter',
  status: {
    running: false, updated: null, tmux: null,
    queue: [{ number: 30, title: 'next up' }],
    issues: [FINISHED(21, 1), FINISHED(22, 2), FINISHED(23, 3), FINISHED(24, 4), FINISHED(25, 5), FINISHED(9, 30)],
  },
  isLocked: false, isStaleLock: false, isStopping: false, hasWatchFile: false,
}

const titles = async (ui: { findAll: (q: { type: string; text: RegExp }) => Promise<{ text: string }[]> }) =>
  (await ui.findAll({ type: 'Text', text: /^#\d+ / })).map(t => t.text)

group('the tabs', () => {
  test('nothing active opens on the queue; finished shows three from the last day, the rest below', async ($, on) => {
    seed(on, MANY)
    const ui = await $.ui.mount(PANE)
    expect((await ui.find({ key: 'tab-queue' }))?.props.label).toBe('Queue 1')
    expect((await ui.find({ key: 'tab-active' }))?.props.label).toBe('Active 0')
    expect((await ui.find({ key: 'tab-finished' }))?.props.label).toBe('Finished 5')
    expect(await titles(ui)).toEqual(['#30 next up'])
    await ui.press({ key: 'tab-finished' })
    await drain()
    expect(await titles(ui)).toEqual(['#21 job 21', '#22 job 22', '#23 job 23'])
    expect((await ui.find({ key: 'down' }))?.props.label).toBe('▼ 2 more')
    expect(await ui.find({ key: 'up' })).toBeUndefined()
    await ui.unmount()
  })
  test('the more line moves the list a job at a time', async ($, on) => {
    seed(on, MANY)
    const ui = await $.ui.mount(PANE)
    await ui.press({ key: 'tab-finished' })
    await drain()
    await ui.press({ key: 'down' })
    await drain()
    expect(await titles(ui)).toEqual(['#22 job 22', '#23 job 23', '#24 job 24'])
    expect((await ui.find({ key: 'up' }))?.props.label).toBe('▲ 1 more')
    await ui.unmount()
  })
  test('a tab press shows that list', async ($, on) => {
    seed(on, MANY)
    const ui = await $.ui.mount(PANE)
    await ui.press({ key: 'tab-queue' })
    await drain()
    expect(await titles(ui)).toEqual(['#30 next up'])
    await ui.press({ key: 'tab-active' })
    await drain()
    expect(await ui.find({ text: 'Nothing being worked on.' })).toBeDefined()
    await ui.unmount()
  })
})

group('a job in the pane', () => {
  // Six minutes and twelve seconds ago, as loop.py writes it: local, to the second, with no zone.
  const d = new Date(Math.floor(Date.now() / 1000) * 1000 - 372_000)
  const p = (n: number) => String(n).padStart(2, '0')
  const started = `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}T${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`
  const working: Seen = {
    ...SEEN(false),
    status: {
      running: true, updated: null, tmux: 'loop-starter', queue: [],
      issues: [{ number: 12, title: 'Gate', step: 'BUILD', state: 'working', round: 2, max_rounds: 5,
        tests: null, review: null, pr: null, note: '', started }],
    },
  }
  test('has a dot and says when it started and how long it has been running', async ($, on) => {
    seed(on, working)
    const ui = await $.ui.mount(PANE)
    const drawn = JSON.stringify(await ui.drawn())
    expect(drawn).toContain('●')
    expect(drawn).toContain(` · started ${p(d.getHours())}:${p(d.getMinutes())} · running 6m 1`)
    await ui.unmount()
  })
})
