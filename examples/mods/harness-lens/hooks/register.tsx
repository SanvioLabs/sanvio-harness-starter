import { atom, read, update } from 'claude-code'
import type { EngineInterface, Register } from 'claude-code'

import { CONFIG_FILE, STARTER, alwaysSteering, bandSegments, emptyLens, gateRun, harnessSkill, lensReport, parseConfig, record, relative, remember, skillFromPath, steeringName } from './logic'
import type { Config, Tone } from './logic'
import type { Lens } from '../types'

const launchAtom = atom({ plugin: 'harness-lens', key: 'launch' } as const, null)
const lensAtom = atom({ plugin: 'harness-lens', key: 'lens' } as const, null)

// Rebuilt on every load, so a new skill or agent shows up after a reload.
let config: Config = STARTER
let skills: string[] = []
let agents: string[] = []

const COLORS: Record<Tone, { color?: string; bold?: boolean; dimColor?: boolean }> = {
  now: { color: 'cyan', bold: true },
  pass: { color: 'green', bold: true },
  fail: { color: 'red', bold: true },
  earlier: {},
  quiet: { dimColor: true },
}

async function readOr($: EngineInterface, path: string): Promise<string | null> {
  return $.fs.read(path).catch(() => null)
}

// The harness root: the nearest folder above the launch directory with a lens config, or with the
// starter's own shape (AGENTS.md beside steering/). None means this session isn't in a harness.
async function findRoot($: EngineInterface, from: string): Promise<string | null> {
  let dir = from.replace(/\/+$/, '')
  while (dir) {
    if (await $.fs.exists(`${dir}/${CONFIG_FILE}`)) return dir
    if ((await $.fs.exists(`${dir}/AGENTS.md`)) && (await $.fs.exists(`${dir}/steering`))) return dir
    dir = dir.slice(0, dir.lastIndexOf('/'))
  }
  return null
}

// A configured folder, with each `*` part expanded to the folders actually there.
async function folders($: EngineInterface, root: string, pattern: string): Promise<string[]> {
  let found = [root]
  for (const part of pattern.replace(/^\.\//, '').replace(/\/+$/, '').split('/')) {
    const next: string[] = []
    for (const dir of found) {
      if (part !== '*') {
        next.push(`${dir}/${part}`)
        continue
      }
      const entries = await $.fs.list(dir).catch(() => [])
      for (const entry of entries) if (entry.kind === 'dir') next.push(`${dir}/${entry.name}`)
    }
    found = next
  }
  return found
}

async function names($: EngineInterface, root: string, patterns: readonly string[], kind: 'skill' | 'agent'): Promise<string[]> {
  const out: string[] = []
  for (const pattern of patterns) {
    for (const dir of await folders($, root, pattern)) {
      for (const entry of await $.fs.list(dir).catch(() => [])) {
        const name = kind === 'skill' ? (entry.kind !== 'file' ? entry.name : null) : entry.name.endsWith('.md') ? entry.name.slice(0, -3) : null
        if (name && name.toLowerCase() !== 'readme' && !out.includes(name)) out.push(name)
      }
    }
  }
  return out
}

async function load($: EngineInterface): Promise<void> {
  const launch = await read($, launchAtom)
  const root = launch ? await findRoot($, launch) : null
  if (!root) {
    await update($, lensAtom, () => null)
    return
  }
  config = parseConfig(await readOr($, `${root}/${CONFIG_FILE}`))
  skills = await names($, root, config.skills, 'skill')
  agents = await names($, root, config.agents, 'agent')
  const texts: string[] = []
  for (const file of config.always) {
    const text = await readOr($, `${root}/${file}`)
    if (text !== null) texts.push(text)
  }
  const always = alwaysSteering(texts, config)
  // A reload keeps what the session has already seen; a new root starts clean.
  await update($, lensAtom, prev => (prev && prev.root === root ? { ...prev, always } : emptyLens(root, always)))
}

async function change($: EngineInterface, edit: (lens: Lens) => Lens): Promise<void> {
  await update($, lensAtom, prev => (prev ? edit(prev) : prev))
}

export const register: Register = on => {
  on('session.start', async ($, e, next) => {
    // A reload fires session.start again; the directory the session started in is the first one.
    await update($, launchAtom, prev => prev ?? e.cwd)
    await $.command.register({
      name: 'lens',
      description: 'Show what the harness did this session: steering, skills, gates, guard refusals and reviewers',
    })
    await load($).catch(() => {})
    return next(e)
  })

  on('command.run', { command: 'lens' }, async $ => {
    const lens = await read($, lensAtom)
    return { text: lens ? lensReport(lens) : "This session didn't start inside a harness, so there's nothing to show." }
  })

  on('turn.start', async ($, e, next) => {
    await change($, lens => ({ ...lens, turn: lens.turn + 1 }))
    return next(e)
  })

  on('skill.prompt', async ($, e, next) => {
    const out = await next(e)
    const name = harnessSkill(e.skill, skills, config)
    if (name) await change($, lens => ({ ...lens, skills: remember(lens.skills, { name, turn: lens.turn }) })).catch(() => {})
    return out
  })

  // The harness's guards run beneath this hook, and their answer goes back exactly as it came: the lens
  // only looks. No .catch on purpose: a hook that throws is skipped and the guards' decision stands.
  on('classic.PreToolUse', async ($, e, next) => {
    const decision = await next(e)
    if (decision.deny) {
      try {
        const tool = String(e.tool)
        await change($, lens => ({ ...lens, refusals: record(lens.refusals, { name: tool, turn: lens.turn }) }))
        $.ui.toast(`🛡 The guard refused ${tool}`)
      } catch {}
    }
    return decision
  })

  on('tool.call', async ($, e, next) => {
    const result = await next(e)
    try {
      const lens = await read($, lensAtom)
      // A subagent's own reads are its business. The main session's are what the band is about.
      if (!lens || result.deny || (e as { agentId?: string }).agentId) return result
      const input = e as unknown as Record<string, unknown>
      const tool = String(e.tool)
      if (tool === 'Read' && typeof input.file_path === 'string') {
        const rel = relative(input.file_path, lens.root)
        const steering = rel ? steeringName(rel, config) : null
        const skill = rel ? skillFromPath(rel, config) : null
        if (steering && !lens.always.includes(steering)) {
          await change($, l => ({ ...l, steering: remember(l.steering, { name: steering, turn: l.turn }) }))
        }
        if (skill) await change($, l => ({ ...l, skills: remember(l.skills, { name: skill, turn: l.turn }) }))
      } else if (tool === 'Bash' && typeof input.command === 'string') {
        const run = gateRun(input.command, String(result.text ?? ''), Boolean(result.isError), config)
        if (run) {
          await change($, l => ({ ...l, gates: record(l.gates, { ...run, turn: l.turn }) }))
          if (!run.ok) $.ui.toast(`✗ The ${run.name} gate failed`)
        }
      } else if (tool === 'Agent' && typeof input.subagent_type === 'string' && agents.includes(input.subagent_type)) {
        const name = input.subagent_type
        await change($, l => ({ ...l, reviews: remember(l.reviews, { name, turn: l.turn }) }))
      }
    } catch {}
    return result
  })

  // Drawn above the prompt, then whatever another mod draws there: two bands stack, neither hides the other.
  on('ui.render', { component: 'AbovePrompt' }, async ($, e, next) => {
    const lens = await read($, lensAtom)
    if (!lens || e.props.hasSurvey) return next(e)
    const { Box, Text } = $.ui.resolve(e)
    const below = await next(e)
    return (
      <Box flexDirection="column">
        <Box flexWrap="wrap" columnGap={2}>
          <Text bold>◆ harness</Text>
          {bandSegments(lens).map(segment => (
            <Text key={segment.label}>
              <Text dimColor>{segment.label}: </Text>
              <Text {...COLORS[segment.tone]}>{segment.text}</Text>
            </Text>
          ))}
        </Box>
        {below}
      </Box>
    )
  })
}
