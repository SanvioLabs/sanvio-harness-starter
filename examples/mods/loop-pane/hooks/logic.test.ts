import { describe as group, expect, test } from 'claude-code/testing'

import { changes, clip, describe, findRoot, headline, parseStatus, sameSeen, waiting } from './logic'
import type { Row, Seen, Status } from '../types'

const ROW: Row = {
  number: 12, title: 'Gate: a fee row with 0 hours passes', step: 'BUILD', state: 'working', round: 2,
  max_rounds: 5, tests: 'failed (1)', review: 'FIX', pr: null, note: '',
}

function status(rows: Row[], queue = [{ number: 12, title: 'a' }, { number: 15, title: 'b' }], running = true): Status {
  return { running, updated: '2026-10-09T18:19:55', queue, issues: rows }
}

function seen(s: Status | null, isLocked: boolean, isStopping = false): Seen {
  return { root: '/h/starter', status: s, isLocked, isStopping }
}

group('the status file', () => {
  test('what loop.py writes reads back', () => {
    const text = JSON.stringify({ running: false, updated: 'x', queue: [{ number: 3, title: 't' }], issues: [ROW] })
    const parsed = parseStatus(text)
    expect(parsed?.queue).toEqual([{ number: 3, title: 't' }])
    expect(parsed?.issues[0].round).toBe(2)
    expect(parsed?.issues[0].tests).toBe('failed (1)')
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
