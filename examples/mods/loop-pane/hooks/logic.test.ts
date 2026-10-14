import { describe as group, expect, test } from 'claude-code/testing'

import { FINISHED_MS, attach, changes, clip, describe, findRoot, firstTab, headline, lists, lockPid, page, parseStatus, sameSeen, waiting, watch, watchCommand } from './logic'
import type { Row, Seen, Status } from '../types'

const ROW: Row = {
  number: 12, title: 'Gate: a fee row with 0 hours passes', step: 'BUILD', state: 'working', round: 2,
  max_rounds: 5, tests: 'failed (1)', review: 'FIX', pr: null, note: '',
}

function status(rows: Row[], queue = [{ number: 12, title: 'a' }, { number: 15, title: 'b' }], running = true, tmux: string | null = null): Status {
  return { running, updated: '2026-10-09T18:19:55', tmux, queue, issues: rows }
}

function seen(s: Status | null, isLocked: boolean, isStopping = false, isStaleLock = false, hasWatchFile = false): Seen {
  return { root: '/h/starter', status: s, isLocked, isStaleLock, isStopping, hasWatchFile }
}

group('the status file', () => {
  test('what loop.py writes reads back', () => {
    const text = JSON.stringify({ running: false, updated: 'x', queue: [{ number: 3, title: 't' }], issues: [ROW] })
    const parsed = parseStatus(text)
    expect(parsed?.queue).toEqual([{ number: 3, title: 't' }])
    expect(parsed?.issues[0]?.round).toBe(2)
    expect(parsed?.issues[0]?.tests).toBe('failed (1)')
  })
  test('no file, broken JSON or the wrong shape is null or empty, never a throw', () => {
    expect(parseStatus(null)).toBeNull()
    expect(parseStatus('{half')).toBeNull()
    expect(parseStatus('[1, 2]')?.issues).toEqual([])
    expect(parseStatus('{"issues": [{"title": "no number"}, 7]}')?.issues).toEqual([])
  })
})

group('the headline', () => {
  test('the lock decides running, not the file', () => {
    expect(headline(seen(status([ROW], undefined, false), true)).text).toBe('Running')
    expect(headline(seen(status([ROW], undefined, true), false)).text).toContain("didn't finish cleanly")
    expect(headline(seen(status([ROW], undefined, false), false)).text).toBe('Not running')
  })
  test('a stop request while running, and a loop that never ran', () => {
    expect(headline(seen(status([ROW]), true, true)).text).toBe('Stopping after this step')
    expect(headline(seen(null, false)).text).toBe("Hasn't run here yet")
  })
  test('a lock whose process is gone is a killed run, in red', () => {
    const line = headline(seen(status([ROW], undefined, true), false, false, true))
    expect(line.tone).toBe('fail')
    expect(line.text).toContain('killed')
  })
  test('the pid in the lock file', () => {
    expect(lockPid('4242\n')).toBe(4242)
    expect(lockPid('')).toBeNull()
    expect(lockPid('abc')).toBeNull()
  })
})

group('the tmux session', () => {
  test('the status file names it', () => {
    expect(parseStatus(JSON.stringify({ tmux: 'loop-starter', issues: [] }))?.tmux).toBe('loop-starter')
    expect(parseStatus('{"issues": []}')?.tmux).toBeNull()
  })
  test('a running loop in tmux offers the attach command', () => {
    expect(attach(seen(status([ROW], undefined, true, 'loop-starter'), true))).toBe('tmux attach -t loop-starter')
  })
  test('a name with a space is quoted', () => {
    expect(attach(seen(status([ROW], undefined, true, 'my loop'), true))).toBe("tmux attach -t 'my loop'")
  })
  test('no session, or a run that is no longer alive, offers nothing', () => {
    expect(attach(seen(status([ROW]), true))).toBeNull()
    expect(attach(seen(status([ROW], undefined, true, 'loop-starter'), false))).toBeNull()
  })
})

group('watching it', () => {
  const inTmux = (isLocked: boolean, hasWatchFile: boolean, name = 'loop-starter') =>
    seen(status([ROW], undefined, true, name), isLocked, false, false, hasWatchFile)
  test('a running loop with a watch file offers it', () => {
    expect(watch(inTmux(true, true))).toBe('/h/starter/.loop/watch.command')
  })
  test('no watch file (not macOS, or an older loop.py), no session, or not running: no button', () => {
    expect(watch(inTmux(true, false))).toBeNull()
    expect(watch(seen(status([ROW]), true, false, false, true))).toBeNull()
    expect(watch(inTmux(false, true))).toBeNull()
  })
  test('the fallback command is read-only, exact and always quoted', () => {
    expect(watchCommand(inTmux(true, true))).toBe("tmux attach -r -t '=loop-starter'")
    expect(watchCommand(inTmux(true, true, "it's"))).toBe("tmux attach -r -t '=it'\\''s'")
    expect(watchCommand(inTmux(false, true))).toBeNull()
  })
})

group('an issue', () => {
  test('in progress: the step and the round, and the last round under it', () => {
    const { head, detail } = describe(ROW, true)
    expect(head).toEqual({ tone: 'now', text: 'building, round 2 of 5' })
    expect(detail).toBe('tests failed (1), review FIX')
  })
  test('planning has no round yet', () => {
    expect(describe({ ...ROW, step: 'SHAPE', round: 0, tests: null, review: null }, true)).toEqual({
      head: { tone: 'now', text: 'planning' }, detail: null,
    })
  })
  test('ended: a pull request, a block with its reason', () => {
    expect(describe({ ...ROW, state: 'pr', pr: 'https://x/pull/2', tests: 'passed', review: 'PASS' }, false).head.text).toBe('pull request open')
    const blocked = describe({ ...ROW, state: 'blocked', note: 'still failing after 5 rounds' }, false)
    expect(blocked.head.tone).toBe('fail')
    expect(blocked.detail).toBe('tests failed (1), review FIX. still failing after 5 rounds')
  })
  test('working with no loop running was left part way', () => {
    expect(describe(ROW, false).head).toEqual({ tone: 'fail', text: 'left at building' })
  })
})

group('what to tell the person', () => {
  test('only an issue that just reached an end', () => {
    const before = status([ROW])
    const after = status([{ ...ROW, state: 'pr', pr: 'u' }, { ...ROW, number: 9, state: 'blocked' }])
    expect(changes(before, after)).toEqual(['Loop: #12 has a pull request', 'Loop: #9 is blocked'])
    expect(changes(after, after)).toEqual([])
    expect(changes(null, after)).toEqual([])
    expect(changes(before, status([{ ...ROW, round: 3 }]))).toEqual([])
  })
  test('waiting leaves out the issue being worked on', () => {
    expect(waiting(status([ROW])).map(q => q.number)).toEqual([15])
    expect(waiting(null)).toEqual([])
  })
})

group('fitting and finding', () => {
  test('a long line is cut with an ellipsis', () => {
    expect(clip('abcdef', 4)).toBe('abc…')
    expect(clip('abc', 4)).toBe('abc')
  })
  test('the root is the nearest folder holding the loop script', async () => {
    const files = new Set(['/h/starter/scripts/loop.py'])
    const exists = async (p: string) => files.has(p)
    expect(await findRoot('/h/starter/examples/proposal', exists)).toBe('/h/starter')
    expect(await findRoot('/h/elsewhere', exists)).toBeNull()
  })
  test('two looks with the same content are the same', () => {
    expect(sameSeen(seen(status([ROW]), true), seen(status([ROW]), true))).toBe(true)
    expect(sameSeen(seen(status([ROW]), true), seen(status([ROW]), false))).toBe(false)
  })
})

group('the tabs', () => {
  const NOW = Date.parse('2026-10-14T12:00:00')
  const ended = (number: number, state: string, updated?: string): Row => ({ ...ROW, number, state, updated })
  test('finished keeps an ended job from the last 24 hours, and drops an older or undated one', () => {
    const rows = [
      ended(1, 'pr', '2026-10-14T09:00:00'),
      ended(2, 'blocked', '2026-10-13T12:00:00'),
      ended(3, 'pr', '2026-10-12T12:23:36'),
      ended(4, 'stopped'),
    ]
    expect(lists(status(rows), NOW).finished.map(r => r.number)).toEqual([1, 2])
    expect(NOW - Date.parse('2026-10-13T12:00:00')).toBe(FINISHED_MS)
  })
  test('active is what is being worked; queue leaves it out', () => {
    const l = lists(status([ROW, ended(3, 'pr', '2026-10-14T09:00:00')]), NOW)
    expect(l.active.map(r => r.number)).toEqual([12])
    expect(l.queue.map(q => q.number)).toEqual([15])
  })
  test('opens on active, else queue, else finished', () => {
    expect(firstTab(lists(status([ROW]), NOW))).toBe('active')
    expect(firstTab(lists(status([]), NOW))).toBe('queue')
    expect(firstTab(lists(status([], []), NOW))).toBe('finished')
  })
  test('three at a time, with the start kept inside the list', () => {
    const five = [1, 2, 3, 4, 5]
    expect(page(five, 0)).toEqual({ shown: [1, 2, 3], start: 0, above: 0, below: 2 })
    expect(page(five, 1)).toEqual({ shown: [2, 3, 4], start: 1, above: 1, below: 1 })
    expect(page(five, 9).start).toBe(2)
    expect(page(five, -4).start).toBe(0)
    expect(page([1, 2], 1)).toEqual({ shown: [1, 2], start: 0, above: 0, below: 0 })
    expect(page([], 3)).toEqual({ shown: [], start: 0, above: 0, below: 0 })
  })
})
