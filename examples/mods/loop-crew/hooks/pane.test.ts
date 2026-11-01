import { describe as group, expect, mock, test } from 'claude-code/testing'
import type { On } from 'claude-code'

import { figureCells } from './logic'

const ROOT = '/h/starter'
const HARNESS = `${ROOT}/.loop`
const ALPHA = `${ROOT}/.loop/projects/alpha`

const job = (number: number, step: string, over: object = {}) => ({ number, title: `Job ${number}`, step, state: 'working', round: 1, ...over })
const statusText = (...issues: object[]) => JSON.stringify({ running: true, queue: [], issues })

const PANE = {
  plugin: 'loop-crew',
  surface: 'terminal',
  component: 'Pane',
  requestId: 'loop-crew',
  props: { title: 'Loop crew', isFocused: true, bodyColumns: 60, placement: 'dock', scroll: { offset: 0, bodyRows: 30 }, view: {} },
} as const

// Work the timers left running; they await the engine a few times.
async function drain(): Promise<void> {
  for (let i = 0; i < 200; i++) await Promise.resolve()
}

// The engine beneath the mod: a harness whose loop files are `files`, by path, and a pane. The test
// changes `files` between polls, `panes` to stand a pane behind another, and `flip` to refuse a close,
// take the root away or leave the lock's holder gone.
function world(on: On, files: Map<string, string>) {
  const clock = mock.clock(on, { now: 1_800_000_000_000 })
  const ran: string[][] = []
  const reads: string[] = []
  const titles: string[] = []
  const blits: { key: string; cells: string }[] = []
  const invalidated: string[] = []
  const panes: { id: string; isShown: boolean; isPlaced: boolean }[] = []
  const flip = { closeFails: false, rootGone: false, staleLock: false, unplaced: false, closes: 0, blit: 'take' as 'take' | 'deny' | 'none', hold: null as Promise<void> | null }
  const process = (exitCode: number, stderr: string) => ({ value: { exitCode, stdout: '', stderr, isStdoutTruncated: false, isStderrTruncated: false } })
  on('session.root', async () => ({ value: ROOT }))
  on('fs.exists', async (_$, e) => ({ value: (e.path === `${ROOT}/scripts/loop.py` && !flip.rootGone) || files.has(e.path) }))
  on('fs.read', async (_$, e) => {
    reads.push(e.path)
    if (flip.hold && e.path === `${HARNESS}/status.json`) await flip.hold
    const text = files.get(e.path)
    return text === undefined ? { deny: `no ${e.path}` } : { value: text }
  })
  on('fs.list', async (_$, e) => {
    if (e.path !== `${ROOT}/.loop/projects`) return { deny: `no ${e.path}` }
    const names = [...files.keys()].flatMap(p => p.match(/\/\.loop\/projects\/([^/]+)\//)?.[1] ?? [])
    const dirs = [...new Set(names)].map(name => ({ name, kind: 'dir' as const, size: 0 }))
    return { value: [...dirs, { name: 'a-file', kind: 'file' as const, size: 0 }] } as never
  })
  on('process.run', async (_$, e) => {
    ran.push([...e.argv])
    return flip.staleLock ? process(1, `kill: (${e.argv[2]}) - No such process`) : process(0, '')
  })
  on('ui.open', async (_$, e) => {
    titles.push(e.title ?? '')
    if (!panes.some(p => p.isShown)) {
      panes.length = 0
      panes.push({ id: 'loop-crew', isShown: true, isPlaced: true })
    }
    return { value: { isPlaced: !flip.unplaced } }
  })
  on('ui.close', async () => {
    flip.closes++
    if (flip.closeFails) return { deny: 'refused' }
    panes.length = 0
    return { value: undefined }
  })
  on('ui.panes', async () => ({ value: [...panes] }) as never)
  on('ui.invalidate', async (_$, e, next) => {
    invalidated.push(e.event)
    return next(e)
  })
  on('ui.blit', async (_$, e, next) => {
    const args = e as unknown as { key: string; cells: string }
    blits.push({ key: args.key, cells: args.cells })
    if (flip.blit === 'deny') return { value: { deny: 'not mounted' } }
    // Left unanswered: nothing sits beneath, so the kit's own "no implementation" rejects it.
    if (flip.blit === 'none') return next(e)
    return { value: {} }
  })
  // Closes the pane, so both timers stop themselves and the next test can start its own.
  const close = async () => {
    panes.length = 0
    await clock.advance(2000)
    await drain()
  }
  return { clock, ran, reads, titles, blits, invalidated, panes, flip, close }
}

type Dollar = { command: { run: (i: object) => Promise<unknown> } }
const say = async ($: unknown, args = ''): Promise<string> => {
  const typed = { command: 'loop-crew', args, origin: { kind: 'composer' }, presentation: { isFullscreen: false, columns: 120 } }
  return ((await ($ as Dollar).command.run(typed)) as { text?: string }).text ?? ''
}

const twoWorking = () => new Map([
  [`${HARNESS}/status.json`, statusText(job(13, 'VALIDATE', { round: 2 }), job(12, 'BUILD', { round: 0 }))],
  [`${HARNESS}/lock`, '4242'],
])

group('the figures', () => {
  for (const surface of ['terminal', 'desktop', 'vscode', 'mobile'] as const) {
    test(`two working issues draw two figures with their words, in number order, on ${surface}`, async ($, on) => {
      const { close } = world(on, twoWorking())
      await say($)
      const ui = await $.ui.mount({ ...PANE, surface } as unknown as typeof PANE)
      const drawn = JSON.stringify(await ui.drawn())
      expect(drawn).toContain('#12 Job 12')
      expect(drawn).toContain('building')
      expect(drawn).toContain('checking, round 2')
      expect(drawn.indexOf('#12 Job 12')).toBeLessThan(drawn.indexOf('#13 Job 13'))
      expect(await ui.find({ key: 'figure-12' })).toBeDefined()
      expect(await ui.find({ key: 'figure-13' })).toBeDefined()
      await ui.unmount()
      await close()
    })
  }
  test('on the desktop each is one Svg that names its issue and step', async ($, on) => {
    const { close } = world(on, twoWorking())
    await say($)
    const ui = await $.ui.mount({ ...PANE, surface: 'desktop' })
    const figure = await ui.find({ key: 'figure-13' })
    expect(figure?.props.alt).toBe('Issue #13: checking')
    expect(figure?.props.isInteractive).toBe(true)
    expect(String(figure?.props.source)).toContain('<animate')
    expect(String(figure?.props.source)).not.toContain('Job 13')
    await ui.unmount()
    await close()
  })
  test('the desktop shows all of them, whatever the height', async ($, on) => {
    const issues = [1, 2, 3, 4, 5].map(n => job(n, 'BUILD'))
    const { close } = world(on, new Map([[`${HARNESS}/status.json`, statusText(...issues)], [`${HARNESS}/lock`, '1']]))
    await say($)
    const ui = await $.ui.mount({ ...PANE, surface: 'desktop', props: { ...PANE.props, scroll: { offset: 0, bodyRows: 10 } } })
    expect(await ui.find({ key: 'figure-5' })).toBeDefined()
    await ui.unmount()
    await close()
  })
  test('the terminal shows what fits, says how many more, and cuts a long title', async ($, on) => {
    const issues = [1, 2, 3, 4].map(n => job(n, 'BUILD', { title: 'x'.repeat(100) }))
    const { close } = world(on, new Map([[`${HARNESS}/status.json`, statusText(...issues)], [`${HARNESS}/lock`, '1']]))
    await say($)
    const ui = await $.ui.mount({ ...PANE, props: { ...PANE.props, bodyColumns: 40, scroll: { offset: 0, bodyRows: 20 } } })
    expect(await ui.find({ key: 'figure-2' })).toBeDefined()
    expect(await ui.find({ key: 'figure-3' })).toBeUndefined()
    const drawn = JSON.stringify(await ui.drawn())
    expect(drawn).toContain('and 2 more')
    // The whole line is cut to the width less 18, the ellipsis in it.
    expect(drawn).toContain(`#1 ${'x'.repeat(18)}…`)
    expect(drawn).not.toContain('x'.repeat(19))
    await ui.unmount()
    await close()
  })
})

group('the frames', () => {
  test('each of four 250 ms advances paints one more per figure on its key, and never redraws', async ($, on) => {
    const { clock, blits, close } = world(on, twoWorking())
    await say($)
    const ui = await $.ui.mount(PANE)
    const before = JSON.stringify(await ui.drawn())
    for (let i = 1; i <= 4; i++) {
      await clock.advance(250)
      await drain()
      expect(blits.filter(b => b.key === 'figure-12').length).toBe(i)
      expect(blits.filter(b => b.key === 'figure-13').length).toBe(i)
      expect(JSON.stringify(await ui.drawn())).toBe(before)
    }
    expect(blits.find(b => b.key === 'figure-12')?.cells).toBe(figureCells('BUILD', 1))
    await ui.unmount()
    await close()
  })
  for (const answer of ['deny', 'none'] as const) {
    test(`a blit answered ${answer === 'deny' ? 'with a deny' : 'by nothing'} changes nothing and throws nothing`, async ($, on) => {
      const { clock, blits, flip, close } = world(on, twoWorking())
      flip.blit = answer
      await say($)
      const ui = await $.ui.mount(PANE)
      const before = JSON.stringify(await ui.drawn())
      await clock.advance(250)
      await drain()
      await clock.advance(250)
      await drain()
      // Still ticking after the failures, on both figures.
      expect(blits.length).toBe(4)
      expect(JSON.stringify(await ui.drawn())).toBe(before)
      await ui.unmount()
      await close()
    })
  }
  test('a redraw after one advance draws an animated figure at its second frame, not its first', async ($, on) => {
    const { clock, close } = world(on, twoWorking())
    await say($)
    const ui = await $.ui.mount(PANE)
    expect((await ui.find({ key: 'figure-12' }))?.props.cells).toBe(figureCells('BUILD', 0))
    await clock.advance(250)
    await drain()
    await ui.redraw()
    expect((await ui.find({ key: 'figure-12' }))?.props.cells).toBe(figureCells('BUILD', 1))
    expect((await ui.find({ key: 'figure-12' }))?.props.cells).not.toBe(figureCells('BUILD', 0))
    await ui.unmount()
    await close()
  })
  test('no timer runs for frames on a surface that animates by itself', async ($, on) => {
    const { clock, blits, close } = world(on, twoWorking())
    await say($)
    const ui = await $.ui.mount({ ...PANE, surface: 'desktop' })
    await clock.advance(1000)
    await drain()
    expect(blits.length).toBe(0)
    await ui.unmount()
    await close()
  })
  test('the frames stop once the pane closes', async ($, on) => {
    const { clock, blits, panes, close } = world(on, twoWorking())
    await say($)
    const ui = await $.ui.mount(PANE)
    panes.length = 0
    await clock.advance(250)
    await drain()
    await clock.advance(1000)
    await drain()
    expect(blits.length).toBe(0)
    await ui.unmount()
    await close()
  })
})

group('the poll', () => {
  test('an unchanged read asks for no redraw, and a changed status file for one', async ($, on) => {
    const files = twoWorking()
    const { clock, invalidated, close } = world(on, files)
    await say($)
    const ui = await $.ui.mount(PANE)
    await drain()
    const first = invalidated.length
    await clock.advance(2000)
    await drain()
    expect(invalidated.length).toBe(first)
    files.set(`${HARNESS}/status.json`, statusText(job(12, 'SCALE')))
    await clock.advance(2000)
    await drain()
    expect(invalidated.length).toBe(first + 1)
    expect(JSON.stringify(await ui.drawn())).toContain('opening the pull request')
    await ui.unmount()
    await close()
  })
  test('it reads nothing once the pane closes, and runs nothing but kill -0', async ($, on) => {
    const { clock, ran, reads, panes, close } = world(on, twoWorking())
    await say($)
    await clock.advance(2000)
    await drain()
    panes.length = 0
    await clock.advance(2000)
    await drain()
    const after = reads.length
    await clock.advance(4000)
    await drain()
    expect(reads.length).toBe(after)
    expect(ran.length).toBeGreaterThan(0)
    for (const argv of ran) expect(argv).toEqual(['kill', '-0', '4242'])
    await close()
  })
  test('a read that a switch overtook is dropped', async ($, on) => {
    const files = twoWorking()
    files.set(`${ALPHA}/status.json`, statusText(job(30, 'BUILD')))
    files.set(`${ALPHA}/lock`, '4242')
    const { clock, flip, close } = world(on, files)
    await say($)
    let release = () => {}
    flip.hold = new Promise<void>(resolve => { release = resolve })
    await clock.advance(2000)
    await drain()
    await say($, 'alpha')
    flip.hold = null
    release()
    await drain()
    const ui = await $.ui.mount(PANE)
    const drawn = JSON.stringify(await ui.drawn())
    expect(drawn).toContain('#30 Job 30')
    expect(drawn).not.toContain('#12 Job 12')
    await ui.unmount()
    await close()
  })
})

group('what the pane shows, in its order', () => {
  type Mounts = { ui: { mount: (i: typeof PANE) => Promise<{ drawn: () => Promise<unknown>; unmount: () => Promise<void> }> } }
  const shown = async ($: Mounts) => {
    const ui = await $.ui.mount(PANE)
    const drawn = JSON.stringify(await ui.drawn())
    await ui.unmount()
    return drawn
  }
  test('no status file, even with a lock', async ($, on) => {
    const { close } = world(on, new Map([[`${HARNESS}/lock`, '4242']]))
    await say($)
    expect(await shown($ as never)).toContain('No loop has run here yet.')
    await close()
  })
  test('a status file that cannot be read counts as none', async ($, on) => {
    const { close } = world(on, new Map([[`${HARNESS}/status.json`, '{not json'], [`${HARNESS}/lock`, '4242']]))
    await say($)
    expect(await shown($ as never)).toContain('No loop has run here yet.')
    await close()
  })
  test('no lock: not running, with no figures, even for rows still at working', async ($, on) => {
    const { close } = world(on, new Map([[`${HARNESS}/status.json`, statusText(job(12, 'BUILD'))]]))
    await say($)
    const drawn = await shown($ as never)
    expect(drawn).toContain("The loop isn't running.")
    expect(drawn).not.toContain('figure-12')
    await close()
  })
  test("a stale lock: not running, whose holder is gone", async ($, on) => {
    const { flip, close } = world(on, twoWorking())
    flip.staleLock = true
    await say($)
    const drawn = await shown($ as never)
    expect(drawn).toContain("The loop isn't running.")
    expect(drawn).not.toContain('figure-12')
    await close()
  })
  test('a lock whose pid cannot be read counts as alive', async ($, on) => {
    const { flip, close } = world(on, new Map([[`${HARNESS}/status.json`, statusText(job(12, 'BUILD'))], [`${HARNESS}/lock`, 'nonsense']]))
    flip.staleLock = true
    await say($)
    expect(await shown($ as never)).toContain('#12 Job 12')
    await close()
  })
  test('a live lock with nothing working', async ($, on) => {
    const { close } = world(on, new Map([[`${HARNESS}/status.json`, statusText(job(12, 'BUILD', { state: 'pr' }))], [`${HARNESS}/lock`, '4242']]))
    await say($)
    expect(await shown($ as never)).toContain('Nothing being built right now.')
    await close()
  })
  test('a live lock with a job, one figure', async ($, on) => {
    const { close } = world(on, new Map([[`${HARNESS}/status.json`, statusText(job(12, 'BUILD'))], [`${HARNESS}/lock`, '4242']]))
    await say($)
    expect(await shown($ as never)).toContain('figure-12')
    await close()
  })
})

group('the command', () => {
  const both = () => {
    const files = twoWorking()
    files.set(`${ALPHA}/status.json`, statusText(job(30, 'SHAPE', { round: 0 })))
    files.set(`${ALPHA}/lock`, '4242')
    return files
  }
  test('no argument shows the harness, titled Loop crew', async ($, on) => {
    const { titles, close } = world(on, both())
    expect(await say($)).toBe('Loop crew opened.')
    expect(titles).toEqual(['Loop crew'])
    await close()
  })
  test("a project's name shows that project's loop, titled with its name", async ($, on) => {
    const { titles, close } = world(on, both())
    expect(await say($, 'alpha')).toBe('Loop crew opened.')
    expect(titles).toEqual(['Loop crew: alpha'])
    const ui = await $.ui.mount(PANE)
    const drawn = JSON.stringify(await ui.drawn())
    expect(drawn).toContain('#30 Job 30')
    expect(drawn).toContain('planning')
    expect(drawn).not.toContain('#12 Job 12')
    await ui.unmount()
    await close()
  })
  for (const name of ['nope', '../x', 'a-file', 'alpha/']) {
    test(`${name} answers no loop and opens or changes nothing`, async ($, on) => {
      const { titles, panes, flip, close } = world(on, both())
      expect(await say($, name)).toBe(`No loop for ${name} under .loop/projects/.`)
      expect(titles).toEqual([])
      expect(panes.length).toBe(0)
      expect(flip.closes).toBe(0)
      await close()
    })
  }
  test('an unknown name leaves an open pane on its loop', async ($, on) => {
    const { titles, panes, close } = world(on, both())
    await say($, 'alpha')
    await say($, '../x')
    expect(titles).toEqual(['Loop crew: alpha'])
    expect(panes.length).toBe(1)
    const ui = await $.ui.mount(PANE)
    expect(JSON.stringify(await ui.drawn())).toContain('#30 Job 30')
    await ui.unmount()
    await close()
  })
  test('no root answers so and opens nothing', async ($, on) => {
    const { titles, flip, close } = world(on, both())
    flip.rootGone = true
    expect(await say($)).toBe(`No scripts/loop.py at or above ${ROOT}, so there is no loop to show.`)
    expect(titles).toEqual([])
    await close()
  })
  test('a second /loop-crew on the same loop closes the pane', async ($, on) => {
    const { panes, close } = world(on, both())
    await say($)
    expect(await say($)).toBe('Loop crew closed.')
    expect(panes.length).toBe(0)
    await say($, 'alpha')
    expect(await say($, 'alpha')).toBe('Loop crew closed.')
    expect(panes.length).toBe(0)
    await close()
  })
  test('a close that fails says how else to close it', async ($, on) => {
    const { flip, close } = world(on, both())
    await say($)
    flip.closeFails = true
    expect(await say($)).toBe("The loop crew pane couldn't close. The × in its corner closes it.")
    await close()
  })
  test('naming another loop switches the open pane and its title, without closing it', async ($, on) => {
    const { titles, flip, panes, close } = world(on, both())
    await say($)
    await say($, 'alpha')
    expect(titles).toEqual(['Loop crew', 'Loop crew: alpha'])
    expect(flip.closes).toBe(0)
    expect(panes.length).toBe(1)
    const ui = await $.ui.mount(PANE)
    expect(JSON.stringify(await ui.drawn())).toContain('#30 Job 30')
    await ui.unmount()
    // And no argument, while a project is shown, goes back to the harness.
    await say($)
    expect(titles).toEqual(['Loop crew', 'Loop crew: alpha', 'Loop crew'])
    expect(flip.closes).toBe(0)
    await close()
  })
  test('a pane open but not shown opens on the loop named', async ($, on) => {
    const { titles, panes, flip, close } = world(on, both())
    await say($, 'alpha')
    panes[0]!.isShown = false
    expect(await say($, 'alpha')).toBe('Loop crew opened.')
    expect(titles).toEqual(['Loop crew: alpha', 'Loop crew: alpha'])
    expect(flip.closes).toBe(0)
    await close()
  })
  test('a surface with no room to place it says to widen the terminal', async ($, on) => {
    const { flip, close } = world(on, both())
    flip.unplaced = true
    expect(await say($)).toBe('Loop crew opened. Widen the terminal to see it.')
    await close()
  })
})
