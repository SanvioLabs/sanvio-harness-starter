import { describe, expect, test } from 'claude-code/testing'

import { STARTER, alwaysSteering, bandSegments, emptyLens, gateRun, harnessSkill, lensReport, parseConfig, parseScope, record, relative, remember, scopeFiles, scopeText, skillFromPath, steeringName } from './logic'

const ROOT = '/h/my-harness'

describe('config', () => {
  test('no file is the starter layout', () => {
    expect(parseConfig(null)).toEqual(STARTER)
  })
  test('a key given replaces that key only', () => {
    const config = parseConfig('{"steering": [".studio/steering"]}')
    expect(config.steering).toEqual(['.studio/steering'])
    expect(config.skills).toEqual(STARTER.skills)
  })
  test('broken JSON or a wrong shape falls back rather than failing', () => {
    expect(parseConfig('not json')).toEqual(STARTER)
    expect(parseConfig('{"steering": "steering"}').steering).toEqual(STARTER.steering)
  })
})

describe('paths', () => {
  test('inside the root, relative to it', () => {
    expect(relative(`${ROOT}/steering/gates.md`, ROOT)).toBe('steering/gates.md')
  })
  test('a sibling with a shared prefix is outside', () => {
    expect(relative('/h/my-harness-old/steering/gates.md', ROOT)).toBeNull()
  })
  test('a steering file, not its README or a nested file', () => {
    expect(steeringName('steering/gates.md', STARTER)).toBe('gates')
    expect(steeringName('steering/README.md', STARTER)).toBeNull()
    expect(steeringName('steering/old/gates.md', STARTER)).toBeNull()
  })
  test('a skill read from its file, including an example job', () => {
    expect(skillFromPath('skills/learn/SKILL.md', STARTER)).toBe('learn')
    expect(skillFromPath('examples/proposal/skills/draft-proposal/SKILL.md', STARTER)).toBe('draft-proposal')
    expect(skillFromPath('skills/learn/notes.md', STARTER)).toBeNull()
  })
})

describe('always-on steering', () => {
  test('reads the @ lines that name steering files', () => {
    const agents = 'Steering\n\n@steering/operating.md\n@steering/response-style.md\n@company/COMPANY.md\nsee @steering/gates.md inline\n'
    expect(alwaysSteering([agents], STARTER)).toEqual(['operating', 'response-style'])
  })
  test('another layout, from its config', () => {
    const config = parseConfig('{"steering": [".studio/steering"], "always": ["CLAUDE.md"]}')
    expect(alwaysSteering(['@.studio/steering/studio.md\n@.studio/steering/writer.md'], config)).toEqual(['studio', 'writer'])
  })
})

describe('skills', () => {
  test("only the harness's own, so a projector never lists personal plugins", () => {
    expect(harnessSkill('learn', ['learn', 'orientation'], STARTER)).toBe('learn')
    expect(harnessSkill('sales:call-prep', ['learn'], STARTER)).toBeNull()
  })
  test('a configured plugin namespace counts', () => {
    const config = parseConfig('{"skillPrefixes": ["studio:"]}')
    expect(harnessSkill('studio:phase-gate', [], config)).toBe('phase-gate')
  })
})

describe('gates', () => {
  test('a gate that passed', () => {
    expect(gateRun('python3 gates/proposal_gate.py out.md', 'PASS out.md', false, STARTER)).toEqual({ name: 'proposal', ok: true })
  })
  test('a gate that failed, piped through tail so the exit code is lost', () => {
    expect(gateRun('python3 examples/proposal/gates/proposal_gate.py bad.md | tail -20', 'FAIL bad.md\n  missing Fees', false, STARTER)).toEqual({
      name: 'proposal',
      ok: false,
    })
  })
  test('an error exit is a failure whatever it printed', () => {
    expect(gateRun('python3 gates/status_gate.py', '', true, STARTER)).toEqual({ name: 'status', ok: false })
  })
  test("output that doesn't say isn't counted as a pass", () => {
    expect(gateRun('python3 gates/proposal_gate.py out.md > log.txt', '', false, STARTER)).toBeNull()
  })
  test('the pre-commit hook refusing a commit', () => {
    expect(gateRun("git commit -m 'x'", "FAIL a.md\nCommit blocked. Fix what's named above.", false, STARTER)).toEqual({ name: 'pre-commit', ok: false })
  })
  test('a hook that prints its refusal in colour', () => {
    expect(gateRun('git commit -m x', '\x1b[0;31mBLOCKED: 1 violation(s) found.\x1b[0m', false, STARTER)).toEqual({ name: 'pre-commit', ok: false })
  })
  test('a commit that went through says nothing: the hook is silent when it passes', () => {
    expect(gateRun("git commit -m 'x'", '[main 070be4f] x', false, STARTER)).toBeNull()
  })
  test('an ordinary command is no gate', () => {
    expect(gateRun('ls -la', 'PASS', false, STARTER)).toBeNull()
  })
  test('a configured pattern, and a bad one is skipped', () => {
    const config = parseConfig('{"gates": ["(", "check-gates\\\\.sh\\\\s+(\\\\S+)"]}')
    expect(gateRun('.studio/skills/run-gates/scripts/check-gates.sh build_to_validate', '✗ File missing', false, config)).toEqual({
      name: 'build_to_validate',
      ok: false,
    })
  })
})

describe('the band', () => {
  const lens = { ...emptyLens(ROOT, ['operating', 'response-style', 'data-and-tools']), turn: 2 }

  test('a fresh session: three always on, nothing else yet', () => {
    expect(bandSegments(lens).map(segment => `${segment.label}: ${segment.text}`)).toEqual([
      'steering: 3 always on',
      'skill: none yet',
      'gate: none run',
      'guard: no refusals',
      'review: none yet',
    ])
  })
  test('what acted this turn stands out, a failure in red', () => {
    const now = {
      ...lens,
      steering: [{ name: 'gates', turn: 2 }],
      skills: [{ name: 'learn', turn: 2 }],
      gates: [{ name: 'proposal', ok: false, turn: 2 }],
      refusals: [{ name: 'Bash', turn: 2 }],
    }
    const segments = bandSegments(now)
    expect(segments[0]).toEqual({ label: 'steering', text: '3 always on + gates', tone: 'now' })
    expect(segments[2]).toEqual({ label: 'gate', text: '✗ proposal', tone: 'fail' })
    expect(segments[3]).toEqual({ label: 'guard', text: '✗ refused Bash', tone: 'fail' })
  })
  test('what acted in an earlier turn is dim, and steering read earlier is counted', () => {
    const earlier = { ...lens, steering: [{ name: 'gates', turn: 1 }], gates: [{ name: 'proposal', ok: true, turn: 1 }] }
    const segments = bandSegments(earlier)
    expect(segments[0]).toEqual({ label: 'steering', text: '3 always on + 1 read', tone: 'earlier' })
    expect(segments[2]?.tone).toBe('earlier')
  })
})

describe('lists and the report', () => {
  test('a name seen again moves to the end', () => {
    expect(remember([{ name: 'a', turn: 1 }, { name: 'b', turn: 1 }], { name: 'a', turn: 2 }).map(hit => hit.name)).toEqual(['b', 'a'])
  })
  test('/lens counts repeat gates and never shows a reason', () => {
    let lens = emptyLens(ROOT, ['operating'])
    lens = { ...lens, gates: record(record(lens.gates, { name: 'proposal', ok: false, turn: 1 }), { name: 'proposal', ok: true, turn: 2 }) }
    lens = { ...lens, refusals: record(record(lens.refusals, { name: 'Bash', turn: 1 }), { name: 'Bash', turn: 2 }) }
    const report = lensReport(lens)
    expect(report).toContain('Gates: passed proposal; failed proposal')
    expect(report).toContain('Guard refusals: Bash ×2 (the reasons are in the transcript)')
  })
})

describe('scope', () => {
  const config = parseConfig(JSON.stringify({
    scope: ['.studio/hooks/.client-scope.{session}.json', '.studio/hooks/.client-scope.shared.json', '.studio/hooks/.focus.{session}.json'],
  }))
  test('the starter declares no scope, so its band and report are unchanged', () => {
    expect(STARTER.scope).toEqual([])
    const lens = emptyLens(ROOT, [])
    expect(bandSegments(lens).map(s => s.label)).not.toContain('scope')
    expect(lensReport(lens)).not.toContain('Scope')
  })
  test('the session id fills {session}, in the order given', () => {
    expect(scopeFiles(config, '0a1d3a7a-eccd')).toEqual([
      '.studio/hooks/.client-scope.0a1d3a7a-eccd.json',
      '.studio/hooks/.client-scope.shared.json',
      '.studio/hooks/.focus.0a1d3a7a-eccd.json',
    ])
  })
  test('without a usable session id, a pattern that needs one is skipped', () => {
    expect(scopeFiles(config, null)).toEqual(['.studio/hooks/.client-scope.shared.json'])
    expect(scopeFiles(config, '../../etc')).toEqual(['.studio/hooks/.client-scope.shared.json'])
  })
  test('a pattern climbing out of the root is never read', () => {
    expect(scopeFiles(parseConfig('{"scope": ["../outside.json"]}'), null)).toEqual([])
  })
  test('a client guard file and a focus file both read', () => {
    expect(parseScope('{"client": " Acme "}')).toEqual({ kind: 'client', name: 'acme' })
    expect(parseScope('{"kind": "partner", "name": "fabrikam", "path": "partners/fabrikam"}')).toEqual({ kind: 'partner', name: 'fabrikam' })
    expect(parseScope('{"client": ""}')).toBeNull()
    expect(parseScope('not json')).toBeNull()
  })
  test('the segment comes first, names the kind, and says none when nothing is set', () => {
    const lens = { ...emptyLens(ROOT, []), scope: { kind: 'partner', name: 'fabrikam' } }
    expect(bandSegments(lens, true)[0]).toEqual({ label: 'scope', text: 'partner fabrikam', tone: 'earlier' })
    expect(bandSegments(emptyLens(ROOT, []), true)[0]).toEqual({ label: 'scope', text: 'none', tone: 'quiet' })
    expect(scopeText({ kind: 'harness', name: 'harness' })).toBe('harness')
    expect(lensReport(lens, true)).toContain('Scope: partner fabrikam')
  })
})
