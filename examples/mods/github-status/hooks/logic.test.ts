import { describe, expect, test } from 'claude-code/testing'

import { LIMIT_MS, QUERY, due, failed, lineFor, parseCounts, parseRemote } from './logic'
import type { Counts } from '../types'

const REPO = 'SanvioLabs/sanvio-harness-starter'
const NOW = 1_800_000_000_000
const COUNTS: Counts = { running: 2, queued: 0, pulls: 3, issues: 5 }

describe('the remote', () => {
  test('SSH remotes, with and without .git', () => {
    expect(parseRemote('git@github.com:SanvioLabs/sanvio-harness-starter.git\n')).toBe(REPO)
    expect(parseRemote('git@github.com:SanvioLabs/sanvio-harness-starter')).toBe(REPO)
    expect(parseRemote('ssh://git@github.com/SanvioLabs/sanvio-harness-starter.git')).toBe(REPO)
  })
  test('HTTPS remotes, with and without .git', () => {
    expect(parseRemote('https://github.com/SanvioLabs/sanvio-harness-starter')).toBe(REPO)
    expect(parseRemote('https://github.com/SanvioLabs/sanvio-harness-starter.git')).toBe(REPO)
  })
  test('a remote that is not GitHub is none, so gh is never called', () => {
    expect(parseRemote('git@gitlab.com:SanvioLabs/sanvio-harness-starter.git')).toBeNull()
    expect(parseRemote('https://github.com.evil.example/SanvioLabs/sanvio-harness-starter')).toBeNull()
    expect(parseRemote('/Users/someone/repos/starter')).toBeNull()
    expect(parseRemote('')).toBeNull()
  })
})

describe('the answer', () => {
  const graphql = JSON.stringify({ data: { repository: { pullRequests: { totalCount: 3 }, issues: { totalCount: 5 } } } })
  test('counts read from the GraphQL answer and the two run listings', () => {
    expect(parseCounts(graphql, '{"total_count": 2, "workflow_runs": []}', '{"total_count": 1}')).toEqual({ running: 2, queued: 1, pulls: 3, issues: 5 })
  })
  test('the wrong shape is none, never a throw', () => {
    expect(parseCounts('{"errors": [{}]}', '{"total_count": 2}', '{"total_count": 0}')).toBeNull()
    expect(parseCounts(graphql, 'not json', '{"total_count": 0}')).toBeNull()
  })
  test('the query reads issues, which leaves pull requests out, and changes nothing', () => {
    expect(QUERY.startsWith('query')).toBe(true)
    expect(QUERY).not.toContain('mutation')
    expect(QUERY).toContain('issues(states: OPEN)')
  })
})

describe('the line', () => {
  test('counts', () => {
    expect(lineFor({ kind: 'counts', repo: REPO, counts: COUNTS, at: NOW }, NOW)).toEqual({
      text: `${REPO} · 2 actions running · 3 open pull requests · 5 open issues`,
      tone: 'now',
    })
  })
  test('singular at one', () => {
    const one = { running: 1, queued: 0, pulls: 1, issues: 1 }
    expect(lineFor({ kind: 'counts', repo: REPO, counts: one, at: NOW }, NOW).text).toBe(`${REPO} · 1 action running · 1 open pull request · 1 open issue`)
  })
  test('queued runs follow the running count', () => {
    const queued = { ...COUNTS, queued: 4 }
    expect(lineFor({ kind: 'counts', repo: REPO, counts: queued, at: NOW }, NOW).text).toContain('2 actions running (4 queued)')
  })
  test('reading', () => {
    expect(lineFor({ kind: 'reading', repo: REPO }, NOW)).toEqual({ text: `${REPO} · reading…`, tone: 'now' })
  })
  test('unavailable, in yellow', () => {
    const line = lineFor({ kind: 'unavailable', repo: REPO }, NOW)
    expect(line.tone).toBe('warn')
    expect(line.text).toContain('GitHub unavailable')
  })
  test('stale: the last counts, their age, in yellow', () => {
    const line = lineFor({ kind: 'stale', repo: REPO, counts: COUNTS, at: NOW - 7 * 60_000 }, NOW)
    expect(line).toEqual({ text: `${REPO} · 2 actions running · 3 open pull requests · 5 open issues · as of 7m ago`, tone: 'warn' })
  })
  test('no remote, dim', () => {
    expect(lineFor({ kind: 'no-remote' }, NOW)).toEqual({ text: 'no GitHub remote', tone: 'quiet' })
  })
  test('a failed read keeps the last counts as stale, and with none is unavailable', () => {
    expect(failed({ kind: 'counts', repo: REPO, counts: COUNTS, at: NOW }, REPO)).toEqual({ kind: 'stale', repo: REPO, counts: COUNTS, at: NOW })
    expect(failed({ kind: 'reading', repo: REPO }, REPO)).toEqual({ kind: 'unavailable', repo: REPO })
    expect(failed(null, REPO)).toEqual({ kind: 'unavailable', repo: REPO })
  })
})

describe('the limit', () => {
  test('the first read is allowed', () => {
    expect(due(null, NOW)).toBe(true)
  })
  test('a second read inside two minutes is refused', () => {
    expect(due(NOW - LIMIT_MS + 1, NOW)).toBe(false)
  })
  test('one two minutes later is allowed', () => {
    expect(due(NOW - LIMIT_MS, NOW)).toBe(true)
  })
  test('one from /github is allowed whenever', () => {
    expect(due(NOW - 1_000, NOW, true)).toBe(true)
  })
})
