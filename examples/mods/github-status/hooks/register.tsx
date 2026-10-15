import { atom, read, update } from 'claude-code'
import type { EngineInterface, Register } from 'claude-code'

import { QUERY, due, failed, lineFor, parseCounts, parseRemote } from './logic'
import type { Tone } from './logic'

const COMMAND = 'github'
// How often the timer asks whether a read is due. due() holds reads to one per two minutes.
const TICK_MS = 15_000
const GIT_TIMEOUT_MS = 5_000
const GH_TIMEOUT_MS = 15_000

const launchAtom = atom({ plugin: 'github-status', key: 'launch' } as const, null)
const statusAtom = atom({ plugin: 'github-status', key: 'status' } as const, null)
const attemptAtom = atom({ plugin: 'github-status', key: 'attempt' } as const, null)

const COLORS: Record<Tone, { color?: string; dimColor?: boolean }> = {
  quiet: { dimColor: true },
  now: { color: 'cyan' },
  warn: { color: 'yellow' },
}

// Set on session.start from the origin remote. Null means no GitHub remote, and gh is never called.
let repo: string | null = null
let isReading = false

async function originRepo($: EngineInterface, cwd: string): Promise<string | null> {
  const ran = await $.process.run(['git', '-C', cwd, 'remote', 'get-url', 'origin'], { timeoutMs: GIT_TIMEOUT_MS }).catch(() => null)
  return ran && ran.exitCode === 0 ? parseRemote(ran.stdout) : null
}

// A read through gh. Each call is a GET or a GraphQL query: nothing here changes GitHub.
async function gh($: EngineInterface, args: string[]): Promise<string> {
  const ran = await $.process.run(['gh', ...args], { timeoutMs: GH_TIMEOUT_MS })
  if (ran.exitCode !== 0) throw new Error('gh failed')
  return ran.stdout
}

const runs = (name: string, status: 'in_progress' | 'queued') =>
  ['api', '--method', 'GET', `repos/${name}/actions/runs?status=${status}&per_page=1`]

// One read of GitHub, if one is due. Every failure is caught and shows as unavailable, or as stale counts.
async function refresh($: EngineInterface, isAsked = false): Promise<void> {
  const name = repo
  if (!name || isReading) return
  const now = Date.now()
  if (!due(await read($, attemptAtom), now, isAsked)) return
  isReading = true
  try {
    await update($, attemptAtom, () => now)
    await update($, statusAtom, prev => (prev && prev.kind !== 'no-remote' && prev.repo === name ? prev : { kind: 'reading', repo: name }))
    const [owner, short] = name.split('/') as [string, string]
    const [graphql, running, queued] = await Promise.all([
      gh($, ['api', 'graphql', '-f', `query=${QUERY}`, '-f', `owner=${owner}`, '-f', `name=${short}`]),
      gh($, runs(name, 'in_progress')),
      gh($, runs(name, 'queued')),
    ])
    const counts = parseCounts(graphql, running, queued)
    if (!counts) throw new Error('unexpected answer')
    await update($, statusAtom, () => ({ kind: 'counts', repo: name, counts, at: Date.now() }))
  } catch {
    await update($, statusAtom, prev => failed(prev, name)).catch(() => {})
  } finally {
    isReading = false
  }
}

export const register: Register = on => {
  on('session.start', async ($, e, next) => {
    // A reload fires session.start again; the directory the session started in is the first one.
    await update($, launchAtom, prev => prev ?? e.cwd)
    await $.command.register({
      name: COMMAND,
      description: "Read GitHub now: the repo's running actions, open pull requests and open issues",
    })
    const launch = await read($, launchAtom)
    repo = launch ? await originRepo($, launch) : null
    if (!repo) await update($, statusAtom, () => ({ kind: 'no-remote' }))
    else {
      void refresh($).catch(() => {})
      $.clock.every(TICK_MS, () => void refresh($).catch(() => {}))
    }
    return next(e)
  })

  on('command.run', { command: COMMAND }, async $ => {
    if (!repo) return { text: "This session's folder has no GitHub origin remote, so there's nothing to read." }
    await refresh($, true).catch(() => {})
    const status = await read($, statusAtom)
    return { text: status ? lineFor(status, Date.now()).text : 'Nothing read yet.' }
  })

  // Drawn above the prompt, then whatever another mod draws there: two bands stack, neither hides the other.
  // It only reads the atom: GitHub is read on the timer and by /github, never while drawing.
  on('ui.render', { component: 'AbovePrompt' }, async ($, e, next) => {
    const status = await read($, statusAtom)
    if (!status || e.props.hasSurvey) return next(e)
    const { Box, Text } = $.ui.resolve(e)
    const line = lineFor(status, Date.now())
    const below = await next(e)
    return (
      <Box flexDirection="column">
        <Box flexWrap="wrap" columnGap={2}>
          <Text bold>◆ github</Text>
          <Text {...COLORS[line.tone]}>{line.text}</Text>
        </Box>
        {below}
      </Box>
    )
  })
}
