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
