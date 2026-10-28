import { describe as group, expect, test } from 'claude-code/testing'

import { activity, conversations, day, evals, findRoot, missing, money, outcome, parseDoc, sections, spend, state, throughput, tokens, waiting } from './logic'
import type { Doc, Seen } from '../types'

// The shape scripts/dashboard_data.py --json prints, with every section filled. The numbers and
// titles are made up.
const DOC: Doc = {
  generated: '2026-10-27T11:00:00-07:00',
  since: '2026-10-13',
  loop_spend: {
    today: { tokens: 12_000_000, cost_usd: 16 },
    last_7_days: { tokens: 60_000_000, cost_usd: 70 },
    since: { tokens: 60_000_000, cost_usd: 70 },
    by_issue: { 'issue-11': { tokens: 3_000_000, cost_usd: 3.5 }, 'issue-12': { tokens: 3_600_000, cost_usd: 5 },
      'issue-13': { tokens: 1_000_000, cost_usd: 2 }, 'app/issue-3': { tokens: 5, cost_usd: 0.25 } },
    by_step: { build: { tokens: 1, cost_usd: 1 } },
    by_model: { 'claude-opus-5-5': { tokens: 3, cost_usd: 5, label: 'claude-opus-5-5' },
      null: { tokens: 2, cost_usd: 20, label: 'model not recorded' } },
    cost_per_pr: 2.5,
  },
  loop_throughput: { issues: 20, by_state: { pr: 19, blocked: 1 }, rounds: {}, more_than_one_round: 4 },
  activity: { skills: { 'review-pr': 5, learn: 1 }, agents: { reviewer: 5 }, commands: {},
    guard_refusals: { 'credential-file': 3 }, asks: 2 },
  evals: {
    reviewer: { saved: '2026-10-26T09:00:00+00:00', stable: 9, flaky: 0, failing: 1, failing_cases: ['03-c'],
      stale: true, changed: ['agents/reviewer.md', 'scripts/eval_agents.py'], newest_change: '2026-10-27T08:30:00-07:00' },
    'security-reviewer': { saved: '2026-10-27T10:00:00-07:00', stable: 10, flaky: 0, failing: 0, failing_cases: [],
      stale: false, changed: [], newest_change: null },
  },
  conversations: {
    harness: { by_model: { 'claude-opus-5-5': { total: 3_000_000 }, '<synthetic>': { total: 0 }, 'claude-haiku-5-5': { total: 450_000 } }, sessions: 30 },
    loop: { by_model: { 'claude-opus-5-5': { total: 20_000_000 } }, sessions: 40 },
  },
  waiting: {
    pull_requests: [
      { number: 41, title: 'Add a gate', opened: 'x', hours_waited: 2, loop_issue: 31, draft: false, checks: 'pass', conflicts: null },
      { number: 42, title: 'Fix the docs', opened: 'x', hours_waited: 3.5, loop_issue: 32, draft: false, checks: 'fail', conflicts: true },
    ],
    blocked: [{ issue: 'issue-38', number: 38, title: 'Link the loop section', note: 'still failing after 5 rounds', updated: 'x' }],
  },
  loop_rework: { merged: 10, reworked: 2, pull_requests: [
    { number: 21, title: 'a', merges_from_base: 0, other_commits: 1 },
    { number: 22, title: 'b', merges_from_base: 1, other_commits: 0 },
  ] },
}

const GONE = (why: string) => ({ value: null, why })
const text = (lines: { text: string }[]) => lines.map(l => l.text).join('\n')

group('the document', () => {
  test("reads what the script prints, and nothing that isn't it", () => {
    expect(parseDoc(JSON.stringify(DOC))?.since).toBe('2026-10-13')
    expect(parseDoc('Traceback (most recent call last):')).toBeNull()
    expect(parseDoc('[1, 2]')).toBeNull()
    expect(parseDoc('{"since": "2026-10-13"}')).toBeNull()
  })
  test('a section the script says is missing gives its why', () => {
    expect(missing(GONE('gh unavailable'))).toBe('gh unavailable')
    expect(missing({ value: null })).toBe('unavailable')
    expect(missing({ today: {} })).toBeNull()
    expect(missing([])).toBeNull()
  })
  test("a run that failed, was cut off or printed something else is a failure, not a document", () => {
    const run = (exitCode: number, stdout: string, isStdoutTruncated = false) => ({ exitCode, stdout, isStdoutTruncated })
    expect('doc' in outcome(run(0, JSON.stringify(DOC)))).toBe(true)
    expect(outcome(null)).toEqual({ failure: "the script didn't finish" })
    expect(outcome(run(1, ''))).toEqual({ failure: 'the script exited 1' })
    expect(outcome(run(0, JSON.stringify(DOC), true))).toEqual({ failure: 'the output was cut off' })
    expect(outcome(run(0, 'hello'))).toEqual({ failure: "the output wasn't the dashboard's JSON" })
  })
  test('the sections come in order, what needs the person first', () => {
    expect(sections(DOC).map(s => s.key)).toEqual(['waiting', 'spend', 'throughput', 'evals', 'conversations', 'activity'])
  })
  test('a document from an older script, with none of the sections, still draws', () => {
    for (const s of sections({ generated: 'x' })) expect(s.lines.length).toBeGreaterThan(0)
  })
})

group('numbers', () => {
  test('tokens, dollars and days read the way a person reads them', () => {
    expect(tokens(312)).toBe('312')
    expect(tokens(840_400)).toBe('840k')
    expect(tokens(12_000_000)).toBe('12.0M')
    expect(tokens(null)).toBe('?')
    expect(money(16)).toBe('$16.00')
    expect(money(null)).toBe('?')
    expect(day('2026-10-13')).toBe('Oct 13')
    expect(day('2026-10-27T08:30:00-07:00')).toBe('Oct 27')
    expect(day(null)).toBe('?')
  })
})

group('the header', () => {
  const seen = (over: Partial<Seen>): Seen => ({ root: '/h/starter', doc: DOC, readAt: Date.parse('2026-10-27T11:43:00'), isReading: false, failedAt: null, failure: null, ...over })
  test('says the first read can take a while', () => {
    expect(state(null).text).toContain('can take a minute')
    expect(state(seen({ doc: null, isReading: true })).text).toContain('can take a minute')
  })
  test('says when it last read, and when a refresh failed it says so and what it still shows', () => {
    expect(state(seen({})).text).toBe('Updated 11:43')
    const failed = state(seen({ failedAt: Date.parse('2026-10-27T11:45:00'), failure: 'the script exited 1' }))
    expect(failed).toEqual({ tone: 'fail', text: 'Refresh failed 11:45 · showing 11:43' })
  })
})

group('waiting on you', () => {
  test('a table of pull requests, red when checks fail or it conflicts, then the blocked issues and why', () => {
    const section = waiting(DOC)
    const [prs, blocked] = section.tables ?? []
    expect(prs?.head).toEqual(['Pull request', 'Waiting', 'Checks', 'Conflicts'])
    expect(prs?.rows).toEqual([['#41 Add a gate', '2h', 'pass', 'unknown'], ['#42 Fix the docs', '3.5h', 'fail', 'yes']])
    expect(prs?.tones).toEqual(['plain', 'fail'])
    expect(blocked?.head).toEqual(['Blocked issue', 'Since'])
    expect(blocked?.rows[0]?.[0]).toBe('#38 Link the loop section')
    expect(text(section.lines)).toBe('#38: still failing after 5 rounds')
  })
  test("pull requests gh couldn't read say so in red, and never read as nothing waiting", () => {
    const section = waiting({ ...DOC, waiting: { pull_requests: GONE('gh unavailable'), blocked: [] } })
    expect(section.lines).toEqual([{ tone: 'fail', text: 'Pull requests: gh unavailable' }])
    expect(section.tables).toEqual([])
  })
  test("a list in a shape it doesn't know, or none at all, is unreadable, not empty", () => {
    for (const pull_requests of [undefined, { items: [] }, 'none']) {
      const section = waiting({ ...DOC, waiting: { pull_requests, blocked: [] } })
      expect(section.lines).toEqual([{ tone: 'fail', text: "Pull requests: couldn't read them" }])
    }
    expect(text(waiting({ ...DOC, waiting: { pull_requests: [] } }).lines)).toBe("Blocked issues: couldn't read them")
  })
  test('nothing open and nothing blocked says nothing is waiting', () => {
    expect(text(waiting({ ...DOC, waiting: { pull_requests: [], blocked: [] } }).lines)).toBe('Nothing waiting on you')
  })
})

group('loop spend', () => {
  test('a table of today, the week, since the date and per pull request, each with its cost and tokens', () => {
    const periods = spend(DOC).tables?.[0]
    expect(periods?.head).toEqual(['', 'Cost', 'Tokens'])
    expect(periods?.rows).toEqual([
      ['Today', '$16.00', '12.0M'], ['7 days', '$70.00', '60.0M'], ['Since Oct 13', '$70.00', '60.0M'],
      ['Per pull request', '~$2.50', '']])
  })
  test('a table of the costliest issues, a project issue keeping its project, then one of each model', () => {
    const [, issues, models] = spend(DOC).tables ?? []
    expect(issues?.head).toEqual(['Costliest issues', 'Cost', 'Tokens'])
    expect(issues?.rows).toEqual([['#12', '$5.00', '3.6M'], ['#11', '$3.50', '3.0M'], ['#13', '$2.00', '1.0M'],
      ['app/#3', '$0.25', '5']])
    expect(models?.rows).toEqual([['model not recorded', '$20.00', '2'], ['opus-5-5', '$5.00', '3']])
    expect(text(spend(DOC).lines)).toContain('not a bill')
  })
  test('every table row is as long as its header', () => {
    for (const t of spend(DOC).tables ?? []) for (const r of t.rows) expect(r.length).toBe(t.head.length)
  })
  test('no pull request yet says so rather than showing nothing', () => {
    const doc = { ...DOC, loop_spend: { ...(DOC.loop_spend as object), cost_per_pr: null } }
    expect(spend(doc).tables?.[0]?.rows[3]).toEqual(['Per pull request', 'none yet', ''])
  })
  test("the chart starts on the day the loop's records do", () => {
    const by_day = [{ day: '2026-10-21', tokens: 0, cost_usd: 0 }, { day: '2026-10-22', tokens: 5, cost_usd: 2.5 }]
    const section = spend({ ...DOC, loop_spend: { ...(DOC.loop_spend as object), by_day, first_run: '2026-10-22' } })
    expect(section.chart?.points).toEqual([{ date: '2026-10-22', value: 2.5 }])
  })
  test("says when the loop's records start, only when that's after the date counted from", () => {
    const at = (first_run: string | null) => text(spend({ ...DOC, loop_spend: { ...(DOC.loop_spend as object), first_run } }).lines)
    expect(at('2026-10-22')).toContain("The loop's records start Oct 22")
    expect(at('2026-10-13')).not.toContain('records start')
    expect(at(null)).not.toContain('records start')
  })
  test('a missing section shows its why', () => {
    expect(text(spend({ ...DOC, loop_spend: GONE('no loop records') }).lines)).toBe('no loop records')
  })
  test('with daily figures it carries a chart of the dollars and names the busiest day', () => {
    const by_day = [{ day: '2026-10-26', tokens: 9, cost_usd: 1.5 }, { day: '2026-10-27', tokens: 3, cost_usd: 16 }]
    const section = spend({ ...DOC, loop_spend: { ...(DOC.loop_spend as object), by_day } })
    expect(section.chart?.points).toEqual([{ date: '2026-10-26', value: 1.5 }, { date: '2026-10-27', value: 16 }])
    expect(section.chart?.unit).toBe('money')
    expect(section.chart?.caption).toBe('Daily, Oct 26 to Oct 27: most $16.00 on Oct 27')
    expect(text(section.lines)).not.toContain('Daily')
  })
  test("each bar is labelled with its day, its cost and its tokens", () => {
    const by_day = [{ day: '2026-10-26', tokens: 9_000_000, cost_usd: 1.5 }, { day: '2026-10-27', tokens: 300, cost_usd: 16 }]
    const chart = spend({ ...DOC, loop_spend: { ...(DOC.loop_spend as object), by_day } }).chart
    expect(chart?.columns).toEqual(['Day', 'Cost', 'Tokens'])
    expect(chart?.labels).toEqual([['Oct 26', '$1.50', '9.0M'], ['Oct 27', '$16.00', '300']])
  })
  test("a day whose runs recorded no cost is labelled ?, never $0.00, and isn't the busiest", () => {
    const by_day = [{ day: '2026-10-26', tokens: 9_000_000, cost_usd: null }, { day: '2026-10-27', tokens: 300, cost_usd: 1 }]
    const chart = spend({ ...DOC, loop_spend: { ...(DOC.loop_spend as object), by_day } }).chart
    expect(chart?.labels[0]).toEqual(['Oct 26', '?', '9.0M'])
    expect(chart?.caption).toBe('Daily, Oct 26 to Oct 27: most $1.00 on Oct 27')
  })
  test("without them it says the script doesn't give them yet, and draws no chart", () => {
    const section = spend(DOC)
    expect(section.chart).toBeUndefined()
    expect(text(section.lines)).toContain("No daily figures: this dashboard_data.py doesn't give them yet")
  })
})

group('throughput and rework', () => {
  test('a table of how recent issues ended and the repeats, then one of rework split into fixes and merges', () => {
    const [issues, rework] = throughput(DOC).tables ?? []
    expect(issues?.head).toEqual(['20 recent issues', 'Count'])
    expect(issues?.rows).toEqual([['Opened a pull request', '19'], ['Blocked', '1'], ['Took more than one round', '4']])
    expect(rework?.rows).toEqual([['Merged', '10'], ['Needed a commit first', '2 (20%)'], ['  with a fix', '1'], ['  only a merge from main', '1']])
  })
  test("rework gh couldn't read says so, beside the issues it could", () => {
    const section = throughput({ ...DOC, loop_rework: GONE('gh failed') })
    expect(section.tables?.map(t => t.key)).toEqual(['throughput-issues'])
    expect(text(section.lines)).toBe('Rework: gh failed')
  })
  test("a merged count it can't read says so, not that nothing merged", () => {
    expect(text(throughput({ ...DOC, loop_rework: { pull_requests: [] } }).lines)).toBe("Rework: couldn't read it")
  })
})

group('evals', () => {
  test('a table row per reviewer, red with a failing case and plain when current, then what fails and why it is stale', () => {
    const section = evals(DOC)
    const t = section.tables?.[0]
    expect(t?.head).toEqual(['Reviewer', 'Stable', 'Flaky', 'Failing', 'Saved', 'Stale'])
    expect(t?.rows).toEqual([['reviewer', '9', '0', '1', 'Oct 26', 'yes'], ['security-reviewer', '10', '0', '0', 'Oct 27', 'no']])
    expect(t?.tones).toEqual(['fail', 'plain'])
    expect(text(section.lines)).toContain('reviewer failing: 03-c')
    expect(text(section.lines)).toContain('reviewer stale: 2 files changed, newest Oct 27. Run it again')
  })
  test("one git couldn't check is unknown, not current", () => {
    const doc = { ...DOC, evals: { reviewer: { saved: 'x', stable: 1, flaky: 0, failing: 0, stale: null, why: 'no git' } } }
    expect(evals(doc).tables?.[0]?.rows[0]?.[5]).toBe('unknown')
    expect(text(evals(doc).lines)).toContain('reviewer stale unknown: no git')
  })
  test("a failing count it can't read is ?, in yellow, not a pass", () => {
    const t = evals({ ...DOC, evals: { reviewer: { saved: 'x', stable: 1, flaky: 0, stale: false } } }).tables?.[0]
    expect(t?.rows[0]?.[3]).toBe('?')
    expect(t?.tones).toEqual(['now'])
  })
  test('none saved says how to save one', () => {
    expect(text(evals({ ...DOC, evals: GONE('no saved evals') }).lines)).toContain('eval_agents.py --save')
  })
})

group('conversations', () => {
  test('a table of each side with its tokens and sessions, then one of the biggest models, none that used nothing', () => {
    const [sides, models] = conversations(DOC).tables ?? []
    expect(sides?.rows).toEqual([['Harness', '3.5M', '30'], ['Loop worktrees', '20.0M', '40']])
    expect(models?.head).toEqual(['Model', 'Harness', 'Loop'])
    expect(models?.rows).toEqual([['opus-5-5', '3.0M', '20.0M'], ['haiku-5-5', '450k', '0']])
  })
  test("with daily figures its chart adds the harness's and the loop's tokens day by day", () => {
    const c = DOC.conversations as { harness: object; loop: object }
    const doc = { ...DOC, conversations: {
      harness: { ...c.harness, by_day: [{ day: '2026-10-26', tokens: 10 }, { day: '2026-10-27', tokens: 20 }] },
      loop: { ...c.loop, by_day: [{ day: '2026-10-27', tokens: 5 }] } } }
    expect(conversations(doc).chart?.points).toEqual([{ date: '2026-10-26', value: 10 }, { date: '2026-10-27', value: 25 }])
    expect(conversations(DOC).chart).toBeUndefined()
  })
})

group('activity', () => {
  test('a table each of skills, agents and what the guard refused, none for an empty one, then the asks', () => {
    const section = activity(DOC)
    expect(section.tables?.map(t => t.head[0])).toEqual(['Skill', 'Agent', 'Guard refused'])
    expect(section.tables?.[0]?.rows).toEqual([['review-pr', '5'], ['learn', '1']])
    expect(section.tables?.[2]?.rows).toEqual([['credential-file', '3']])
    expect(text(section.lines)).toBe('Guard asked 2 times, since Oct 13')
  })
})

group('the root', () => {
  test('is the nearest folder up that has the dashboard script', async () => {
    const has = new Set(['/h/starter/scripts/dashboard_data.py'])
    expect(await findRoot('/h/starter/projects/app/', async p => has.has(p))).toBe('/h/starter')
    expect(await findRoot('/elsewhere', async p => has.has(p))).toBeNull()
  })
})
