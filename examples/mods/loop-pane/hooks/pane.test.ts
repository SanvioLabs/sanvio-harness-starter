import { describe as group, expect, mock, test } from 'claude-code/testing'
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

group('the header', () => {
  test('names the repo and the state, with Watch it and Copy attach command on one row and no bare attach line', async ($, on) => {
    seed(on, SEEN(true))
    const ui = await $.ui.mount(PANE)
    const drawn = JSON.stringify(await ui.drawn())
    expect(drawn).toContain('starter')
    // The state's dot is drawn apart from its words, so it can pulse; idle, it doesn't.
    expect(drawn).toContain('" Idle"')
    expect(JSON.stringify(await ui.find({ key: 'header' }))).not.toContain('cyan')
    expect(drawn).not.toContain('tmux attach')
    const row = await ui.find({ key: 'actions' })
    expect(row?.props.flexDirection).toBe('row')
    const inRow = JSON.stringify(row?.children)
    expect(inRow).toContain('Watch it')
    expect(inRow).toContain('Copy attach command')
    await ui.unmount()
  })
  test('takes the same rows above the tabs whether the loop is running or not', async ($, on) => {
    let seen = SEEN(true)
    on('state.get', async (_$, e, next) =>
      e.plugin === 'loop-pane' && e.key === 'seen' ? { value: { value: seen, version: 1 } } : next(e))
    // How many of the pane's lines come before the tabs.
    const above = async (): Promise<number> => {
      const ui = await $.ui.mount(PANE)
      const top = (await ui.drawn()) as unknown as { children: { props?: { key?: string } }[] }
      await ui.unmount()
      return top.children.findIndex(c => JSON.stringify(c).includes('"tab-queue"'))
    }
    const running = await above()
    seen = { ...SEEN(false), isLocked: false, status: { ...SEEN(false).status!, running: false, tmux: null } }
    expect(running).toBeGreaterThan(0)
    expect(await above()).toBe(running)
  })
})

group("a job's Watch button", () => {
  const withWindow: Seen = {
    ...SEEN(false),
    status: {
      running: true, updated: null, tmux: 'loop-starter', queue: [],
      issues: [{ number: 12, title: 'Gate', step: 'BUILD', state: 'working', round: 1, tests: null, review: null,
        pr: null, note: '', window: 'issue-12' }],
    },
  }
  test('opens the job watch file', async ($, on) => {
    const ran: string[][] = []
    on('process.run', async (_$, e) => {
      ran.push([...e.argv])
      return { value: { exitCode: 0, stdout: '', stderr: '', isStdoutTruncated: false, isStderrTruncated: false } }
    })
    seed(on, withWindow)
    const ui = await $.ui.mount(PANE)
    await ui.press({ key: 'watch-12' })
    await drain()
    expect(ran).toEqual([['open', '/h/starter/.loop/issue-12/watch.command']])
    await ui.unmount()
  })
  test("copies the job's read-only attach command when the window can't open", async ($, on) => {
    const copied: string[] = []
    on('process.run', async () => ({ value: { exitCode: 1, stdout: '', stderr: 'no', isStdoutTruncated: false, isStderrTruncated: false } }))
    on('ui.copy', async (_$, e) => {
      copied.push(e.text)
      return { value: { isCopied: true } }
    })
    on('ui.toast', async () => ({ value: undefined }))
    seed(on, withWindow)
    const ui = await $.ui.mount(PANE)
    await ui.press({ key: 'watch-12' })
    await drain()
    expect(copied).toEqual(["tmux attach -r -t '=loop-starter:issue-12'"])
    await ui.unmount()
  })
  test('a job with no window has none', async ($, on) => {
    seed(on, { ...withWindow, status: { ...withWindow.status!, issues: withWindow.status!.issues.map(r => ({ ...r, window: undefined })) } })
    const ui = await $.ui.mount(PANE)
    expect(await ui.find({ key: 'watch-12' })).toBeUndefined()
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
    expect(drawn).toContain(`started ${p(d.getHours())}:${p(d.getMinutes())} · running 6m 1`)
    await ui.unmount()
  })
  test('the clock has a line of its own under the title, apart from the step', async ($, on) => {
    seed(on, working)
    const ui = await $.ui.mount(PANE)
    const clockRow = JSON.stringify(await ui.find({ key: 'clock-12' }))
    expect(clockRow).toContain(`started ${p(d.getHours())}:${p(d.getMinutes())}`)
    expect(clockRow).not.toContain('building')
    expect(JSON.stringify(await ui.drawn())).not.toContain(' · started')
    await ui.unmount()
  })
  test('tokens and cost follow the time in the same single-line clock text', async ($, on) => {
    // Two jobs at once, one with usage and one without, so one mount compares their heights.
    const job = working.status!.issues[0]
    seed(on, { ...working, status: { ...working.status!, issues: [
      { ...job, tokens: 840_000, cost_usd: 3.4 }, { ...job, number: 13, title: 'Other' }] } })
    const ui = await $.ui.mount(PANE)
    const height = async (key: string) =>
      ((await ui.find({ key })) as unknown as { props?: { height?: number } } | undefined)?.props?.height
    // The job keeps the rows it has without usage.
    expect(await height('issue-12')).toBeDefined()
    expect(await height('issue-12')).toBe(await height('issue-13'))
    // One string in one Text under the clock key: usage is part of the time's line, not a row of its own.
    expect(JSON.stringify(await ui.find({ key: 'clock-12' }))).toMatch(/"started [^"]* · running [^"]* · 840k tokens · ~\$3\.40"/)
    expect(JSON.stringify(await ui.find({ key: 'clock-13' }))).not.toContain('tokens')
    await ui.unmount()
  })
  test('a job with no clock keeps the line, so every job takes the same rows', async ($, on) => {
    const old = { ...working, status: { ...working.status!, issues: [{ ...working.status!.issues[0], started: undefined }] } }
    seed(on, old)
    const ui = await $.ui.mount(PANE)
    expect(await ui.find({ key: 'clock-12' })).toBeDefined()
    expect(JSON.stringify(await ui.drawn())).not.toContain('started')
    await ui.unmount()
  })
  test("the header's Running dot pulses with the job's", async ($, on) => {
    seed(on, working)
    const ui = await $.ui.mount(PANE)
    type Node = { props?: Record<string, unknown>; children?: (Node | string)[] }
    const first = (n: Node | string | undefined): Node => (n as Node).children![0] as Node
    // The header's state is its second child: the dot, then the words. A job's dot leads its first row.
    const state = (await ui.find({ key: 'header' }) as unknown as Node).children![1] as Node
    const headerDot = first(state)
    const jobDot = first(first(await ui.find({ key: 'issue-12' }) as unknown as Node))
    expect(headerDot.children).toEqual(['●'])
    expect(JSON.stringify(state.children![1])).toContain(' Running')
    // Drawn from the same beat, so the two dots brighten and dim together.
    expect(headerDot.props).toEqual(jobDot.props)
    await ui.unmount()
  })
})

group('project loops', () => {
  const ROOT = '/h/starter'
  const HARNESS = `${ROOT}/.loop`
  const ALPHA = `${ROOT}/.loop/projects/alpha`
  const BETA = `${ROOT}/.loop/projects/beta`
  const statusText = (title: string, extra: object = {}) =>
    JSON.stringify({ running: false, tmux: null, queue: [{ number: 30, title }], issues: [], ...extra })
  const JOB = { number: 12, title: 'Gate', step: 'BUILD', state: 'working', round: 1, tests: null, review: null, pr: null, note: '', window: 'issue-12' }

  // The engine beneath the plugin: a harness whose loop files are `files`, by path, and an open pane.
  // The folders under .loop/projects come from those paths. The test changes `files` between polls.
  function world(on: On, files: Map<string, string>) {
    const clock = mock.clock(on, { now: 1_800_000_000_000 })
    const toasts: string[] = []
    const ran: string[][] = []
    let isUp = true
    on('session.root', async () => ({ value: ROOT }))
    on('fs.exists', async (_$, e) => ({ value: e.path === `${ROOT}/scripts/loop.py` || files.has(e.path) }))
    on('fs.read', async (_$, e) => {
      const text = files.get(e.path)
      return text === undefined ? { deny: `no ${e.path}` } : { value: text }
    })
    on('fs.list', async (_$, e) => {
      if (e.path !== `${ROOT}/.loop/projects`) return { deny: `no ${e.path}` }
      const names = [...files.keys()].flatMap(p => p.match(/\/\.loop\/projects\/([^/]+)\//)?.[1] ?? [])
      return { value: [...new Set(names)].map(name => ({ name, kind: 'dir' as const, size: 0 })) } as never
    })
    on('process.run', async (_$, e) => {
      ran.push([...e.argv])
      return { value: { exitCode: 0, stdout: '', stderr: '', isStdoutTruncated: false, isStderrTruncated: false } }
    })
    on('ui.open', async () => ({ value: { isPlaced: true } }))
    on('ui.panes', async () => ({ value: isUp ? [{ id: 'loop' }] : [] }) as never)
    on('ui.toast', async (_$, e) => {
      toasts.push(e.text)
      return { value: undefined }
    })
    // Closes the pane, so the poll stops itself and the next test can start its own.
    const close = async () => {
      isUp = false
      await clock.advance(500)
    }
    return { clock, toasts, close, opened: () => ran.filter(argv => argv[0] === 'open') }
  }

  type Dollar = { command: { run: (i: object) => Promise<unknown> } }
  const typed = { command: 'loop-pane', args: '', origin: { kind: 'composer' }, presentation: { isFullscreen: false, columns: 120 } }
  const open = async ($: Dollar) => { await $.command.run(typed) }
  // Past the poll's next read of the loop's files.
  const POLL = 2000

  const threeLoops = () => new Map([
    [`${HARNESS}/status.json`, statusText('harness job')],
    [`${ALPHA}/status.json`, statusText('alpha job')],
    [`${BETA}/status.json`, statusText('beta job')],
    [`${ROOT}/.loop/projects/never-ran/notes`, 'a clone with no status file'],
  ])
  const left = async (ui: { find: (q: { key: string }) => Promise<unknown> }) => JSON.stringify(await ui.find({ key: 'header' }))

  test('there is no row without projects', async ($, on) => {
    const { close } = world(on, new Map([[`${HARNESS}/status.json`, statusText('harness job')]]))
    await open($ as unknown as Dollar)
    const ui = await $.ui.mount(PANE)
    expect(await ui.find({ key: 'loops' })).toBeUndefined()
    expect(await ui.find({ key: 'tab-queue' })).toBeDefined()
    await ui.unmount()
    await close()
  })
  test('with projects, the row names the harness then each project in order, above the tabs', async ($, on) => {
    const { close } = world(on, threeLoops())
    await open($ as unknown as Dollar)
    const ui = await $.ui.mount(PANE)
    const row = await ui.find({ key: 'loops' })
    const labels = (row?.children as unknown as { props: { label: string } }[]).map(c => c.props.label)
    expect(labels).toEqual(['starter', 'alpha', 'beta'])
    const top = (await ui.drawn()) as unknown as { children: unknown[] }
    const at = (needle: string) => top.children.findIndex(c => JSON.stringify(c).includes(needle))
    expect(at('"loop-alpha"')).toBeGreaterThan(-1)
    expect(at('"loop-alpha"')).toBeLessThan(at('"tab-queue"'))
    await ui.unmount()
    await close()
  })
  test('a loop on one job marks its button, and on two adds the count', async ($, on) => {
    const files = threeLoops()
    files.set(`${ALPHA}/status.json`, statusText('alpha job', { issues: [JOB] }))
    files.set(`${ALPHA}/lock`, '4242')
    const { clock, close } = world(on, files)
    await open($ as unknown as Dollar)
    const ui = await $.ui.mount(PANE)
    expect((await ui.find({ key: 'loop-alpha' }))?.props.label).toBe('● alpha')
    expect((await ui.find({ key: 'loop-beta' }))?.props.label).toBe('beta')
    files.set(`${ALPHA}/status.json`, statusText('alpha job', { issues: [JOB, { ...JOB, number: 13 }] }))
    await clock.advance(POLL)
    expect((await ui.find({ key: 'loop-alpha' }))?.props.label).toBe('● alpha 2')
    await ui.unmount()
    await close()
  })
  test("a loop off screen shows its marker without its button lighting, and the header's left side has none", async ($, on) => {
    const files = threeLoops()
    for (const dir of [ALPHA, BETA]) {
      files.set(`${dir}/status.json`, statusText('a job', { issues: [JOB] }))
      files.set(`${dir}/lock`, '4242')
    }
    const { close } = world(on, files)
    await open($ as unknown as Dollar)
    const ui = await $.ui.mount(PANE)
    await ui.press({ key: 'loop-beta' })
    await drain()
    const alpha = await ui.find({ key: 'loop-alpha' })
    expect(alpha?.props.label).toBe('● alpha')
    expect(alpha?.props.variant).toBeUndefined()
    expect(alpha?.props.dimColor).toBe(true)
    const beta = await ui.find({ key: 'loop-beta' })
    expect(beta?.props.label).toBe('● beta')
    expect(beta?.props.variant).toBe('primary')
    const header = (await ui.find({ key: 'header' })) as unknown as { children: { children: string[] }[] }
    expect(header.children[0]?.children).toEqual(['beta'])
    await ui.unmount()
    await close()
  })
  test("pressing a project shows its queue, and its STOP shows as stopping", async ($, on) => {
    const files = threeLoops()
    files.set(`${ALPHA}/lock`, '4242')
    files.set(`${ALPHA}/STOP`, '')
    files.set(`${HARNESS}/lock`, '4242')
    const { close } = world(on, files)
    await open($ as unknown as Dollar)
    const ui = await $.ui.mount(PANE)
    expect(await titles(ui)).toEqual(['#30 harness job'])
    await ui.press({ key: 'loop-alpha' })
    await drain()
    expect(await titles(ui)).toEqual(['#30 alpha job'])
    const head = await left(ui)
    expect(head).toContain('alpha')
    expect(head).toContain('Stopping after this step')
    await ui.unmount()
    await close()
  })
  test("Watch it and a job's Watch open the project's own files", async ($, on) => {
    const files = threeLoops()
    files.set(`${ALPHA}/status.json`, statusText('alpha job', { tmux: 'loop-alpha', issues: [JOB] }))
    files.set(`${ALPHA}/lock`, '4242')
    files.set(`${ALPHA}/watch.command`, '')
    const { opened, close } = world(on, files)
    await open($ as unknown as Dollar)
    const ui = await $.ui.mount(PANE)
    await ui.press({ key: 'watch' })
    await ui.press({ key: 'watch-12' })
    await drain()
    expect(opened()).toEqual([['open', `${ALPHA}/watch.command`], ['open', `${ALPHA}/issue-12/watch.command`]])
    await ui.unmount()
    await close()
  })
  test('the pane opens on a running project, the pick then holds, and /loop-pane picks again', async ($, on) => {
    const files = threeLoops()
    files.set(`${BETA}/lock`, '4242')
    const { clock, close } = world(on, files)
    await open($ as unknown as Dollar)
    const ui = await $.ui.mount(PANE)
    expect(await titles(ui)).toEqual(['#30 beta job'])
    // The harness starts: it comes first when opening, but the pane doesn't jump to it.
    files.set(`${HARNESS}/lock`, '4242')
    await clock.advance(POLL)
    expect(await titles(ui)).toEqual(['#30 beta job'])
    await open($ as unknown as Dollar)
    expect(await titles(ui)).toEqual(['#30 harness job'])
    await ui.unmount()
    await close()
  })
  test("a picked project whose folder has gone falls back to the harness, on the harness's busiest tab", async ($, on) => {
    const files = threeLoops()
    const { clock, close } = world(on, files)
    await open($ as unknown as Dollar)
    const ui = await $.ui.mount(PANE)
    await ui.press({ key: 'loop-alpha' })
    await drain()
    await ui.press({ key: 'tab-finished' })
    await drain()
    files.delete(`${ALPHA}/status.json`)
    await clock.advance(POLL)
    expect(await titles(ui)).toEqual(['#30 harness job'])
    expect(await ui.find({ key: 'loop-alpha' })).toBeUndefined()
    await ui.unmount()
    await close()
  })
  test('switching loops raises no toast, and a change in a loop off screen raises one with its name', async ($, on) => {
    const files = threeLoops()
    const issues = [{ ...JOB, state: 'working' }]
    files.set(`${HARNESS}/status.json`, statusText('harness job', { issues }))
    files.set(`${BETA}/status.json`, statusText('beta job', { issues }))
    const { clock, toasts, close } = world(on, files)
    await open($ as unknown as Dollar)
    const ui = await $.ui.mount(PANE)
    await ui.press({ key: 'loop-alpha' })
    await drain()
    await clock.advance(POLL)
    await ui.press({ key: 'loop' })
    await drain()
    await clock.advance(POLL)
    expect(toasts).toEqual([])
    files.set(`${BETA}/status.json`, statusText('beta job', { issues: [{ ...JOB, state: 'pr', pr: 'https://x/pull/2' }] }))
    await clock.advance(POLL)
    expect(toasts).toEqual(['beta: #12 has a pull request'])
    await ui.unmount()
    await close()
  })
})

group('on Claude Desktop', () => {
  const DESKTOP = { ...PANE, surface: 'desktop' } as const
  const working: Seen = {
    ...SEEN(true),
    status: {
      running: true, updated: null, tmux: 'loop-starter', queue: [],
      issues: [{ number: 12, title: 'Gate', step: 'BUILD', state: 'working', round: 1, tests: null, review: null,
        pr: null, note: '', window: 'issue-12' }],
    },
  }
  test('draws the header, the buttons and a job with its Watch button', async ($, on) => {
    seed(on, working)
    const ui = await $.ui.mount(DESKTOP)
    const drawn = JSON.stringify(await ui.drawn())
    expect(drawn).toContain('starter')
    expect(drawn).toContain(' Running')
    expect(drawn).toContain('#12 Gate')
    expect(await ui.find({ key: 'watch' })).toBeDefined()
    expect(await ui.find({ key: 'watch-12' })).toBeDefined()
    await ui.unmount()
  })
  test('the header pushes the state right by layout, not by padding', async ($, on) => {
    seed(on, working)
    const ui = await $.ui.mount(DESKTOP)
    const header = await ui.find({ key: 'header' })
    expect(header?.props.justifyContent).toBe('space-between')
    expect(JSON.stringify(header?.children)).not.toMatch(/"\s{3,}"/)
    await ui.unmount()
  })
  for (const surface of ['desktop', 'vscode'] as const) {
    test(`on ${surface} long titles and lines show whole, not cut`, async ($, on) => {
      const title = 'A title that is much longer than the sixty columns the pane body has to draw it in'
      const queued = 'A queued title that is also much longer than the sixty columns the body has'
      const note = 'a long note that runs on well past two rows of the sixty columns the pane body has to show it in'
      seed(on, {
        ...working,
        status: {
          ...working.status!,
          queue: [{ number: 31, title: queued, waiting_on: [12] }],
          issues: [{ ...working.status!.issues[0], title, note }],
        },
      })
      const ui = await $.ui.mount({ ...DESKTOP, surface })
      const drawn = JSON.stringify(await ui.drawn())
      expect(drawn).toContain(`#12 ${title}`)
      expect(drawn).toContain(note)
      expect(drawn).not.toContain('…')
      expect((await ui.find({ key: 'issue-12' }))?.props.height).toBeUndefined()
      const detail = await ui.find({ key: 'detail-12' })
      expect(detail?.props.height).toBeUndefined()
      expect(detail?.props.overflow).toBeUndefined()
      await ui.press({ key: 'tab-queue' })
      await drain()
      const queue = JSON.stringify(await ui.drawn())
      expect(queue).toContain(`#31 ${queued}`)
      expect(queue).toContain('waiting on #12')
      expect(queue).not.toContain('…')
      await ui.unmount()
    })
  }
})
