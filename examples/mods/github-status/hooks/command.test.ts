import { describe, expect, mock, test } from 'claude-code/testing'
import type { FsEntry, On } from 'claude-code'

const ROOT = '/h/starter'
const COUNTS = (pulls: number) => JSON.stringify({ data: { repository: { pullRequests: { totalCount: pulls }, issues: { totalCount: 1 } } } })

// A harness at ROOT with three folders under projects/: acme and beta are clones on GitHub, notes is a plain folder.
// gh answers each repo with its own pull request count, and fails for beta when beta-fails is set.
function world(on: On, options: { betaFails?: boolean } = {}): string[][] {
  const ran: string[][] = []
  mock.clock(on, { now: 1_800_000_000_000 })
  // The engine beneath the plugins: a session that starts, and a command it takes.
  on('session.start', async (_$, e) => ({ cwd: e.cwd }))
  on('session.root', async () => ({ value: ROOT }))
  on('command.register', async (_$, e) => ({ value: { command: e.name } }))
  on('fs.list', async (_$, e, next) =>
    e.path === `${ROOT}/projects`
      ? { value: [
          ...['acme', 'beta', 'notes', '.cache'].map((name): FsEntry => ({ name, kind: 'dir', size: 0, mtimeMs: 0, isLink: false })),
          { name: 'README.md', kind: 'file', size: 1, mtimeMs: 0, isLink: false } satisfies FsEntry,
        ] }
      : next(e))
  on('fs.exists', async (_$, e, next) =>
    e.path.startsWith(`${ROOT}/projects/`) ? { value: /\/projects\/(acme|beta)\/\.git$/.test(e.path) } : next(e))
  on('process.run', async (_$, e) => {
    const argv = [...e.argv]
    ran.push(argv)
    const ok = (stdout: string) => ({ value: { exitCode: 0, stdout, stderr: '', isStdoutTruncated: false, isStderrTruncated: false } })
    const fail = { value: { exitCode: 1, stdout: '', stderr: 'no', isStdoutTruncated: false, isStderrTruncated: false } }
    if (argv[0] === 'git') {
      const remotes: Record<string, string> = {
        [ROOT]: 'git@github.com:SanvioLabs/sanvio-harness-starter.git',
        [`${ROOT}/projects/acme`]: 'https://github.com/acme/app.git',
        [`${ROOT}/projects/beta`]: 'git@github.com:beta/site.git',
        // Not a clone: git inside it finds the harness's own repo.
        [`${ROOT}/projects/notes`]: 'git@github.com:SanvioLabs/sanvio-harness-starter.git',
      }
      const url = remotes[argv[2] ?? '']
      return url ? ok(url) : fail
    }
    const text = argv.join(' ')
    if (options.betaFails && text.includes('beta')) return fail
    if (text.includes('graphql')) return ok(COUNTS(text.includes('owner=acme') ? 4 : text.includes('owner=beta') ? 7 : 2))
    return ok('{"total_count": 0}')
  })
  return ran
}

// What the person sees after typing /github with these arguments, as a command run from the prompt.
const typed = (args: string) =>
  ({ command: 'github', args, origin: { kind: 'composer' }, presentation: { isFullscreen: false, columns: 120 } }) as const

type Dollar = { session: { start: (i: { cwd: string; surface: null; isInteractive: boolean }) => Promise<unknown> }; command: { run: (i: ReturnType<typeof typed>) => Promise<unknown> } }

async function github($: Dollar, args: string): Promise<string> {
  await $.session.start({ cwd: ROOT, surface: null, isInteractive: true })
  const result = await $.command.run(typed(args))
  return (result as { text?: string }).text ?? ''
}

describe('/github on a project', () => {
  test('reads the project folder named, with or without projects/', async ($, on) => {
    world(on)
    expect(await github($, 'acme')).toBe('acme: acme/app · 0 actions running · 4 open pull requests · 1 open issue')
    expect(await github($, 'projects/beta')).toBe('beta: beta/site · 0 actions running · 7 open pull requests · 1 open issue')
  })
  test('a folder with no GitHub remote, or no folder, says so and never calls gh', async ($, on) => {
    const ran = world(on)
    expect(await github($, 'notes')).toBe('projects/notes has no GitHub origin remote, so there\'s nothing to read.')
    expect(await github($, 'nope')).toBe("projects/nope isn't a folder.")
    expect(ran.filter(a => a[0] === 'gh' && a.join(' ').includes('notes'))).toEqual([])
  })
  test('a name that could leave projects/ runs nothing', async ($, on) => {
    const ran = world(on)
    await $.session.start({ cwd: ROOT, surface: null, isInteractive: true })
    const text = ((await $.command.run(typed('../secrets'))) as { text?: string }).text ?? ''
    expect(text).toContain("isn't a project")
    expect(ran.filter(a => a.join(' ').includes('secrets'))).toEqual([])
  })
  test('a failed read shows that repo as unavailable', async ($, on) => {
    world(on, { betaFails: true })
    expect(await github($, 'beta')).toBe('beta: beta/site · GitHub unavailable (is gh installed and signed in?)')
  })
})

describe('/github after a /clear', () => {
  // A /clear starts a new session with no session.start, so a folder saved there is gone or the last session's.
  test('with no session.start, reads the project from the session root', async ($, on) => {
    world(on)
    const text = ((await $.command.run(typed('acme'))) as { text?: string }).text ?? ''
    expect(text).toBe('acme: acme/app · 0 actions running · 4 open pull requests · 1 open issue')
  })
})

describe('/github all', () => {
  test('the harness, each project with a remote in name order, and a count of the rest', async ($, on) => {
    world(on, { betaFails: true })
    expect(await github($, 'all')).toBe([
      'harness: SanvioLabs/sanvio-harness-starter · 0 actions running · 2 open pull requests · 1 open issue',
      'acme: acme/app · 0 actions running · 4 open pull requests · 1 open issue',
      'beta: beta/site · GitHub unavailable (is gh installed and signed in?)',
      '1 folder under projects/ has no GitHub remote.',
    ].join('\n'))
  })
  test('the line above the prompt stays the harness\'s', async ($, on) => {
    world(on)
    on('ui.render', async () => ({ type: 'Box', props: {}, children: [] }) as never)
    await github($, 'acme')
    const ui = await $.ui.mount({ plugin: 'github-status', surface: 'terminal', component: 'AbovePrompt', props: {} as never })
    const drawn = JSON.stringify(await ui.drawn())
    expect(drawn).toContain('SanvioLabs/sanvio-harness-starter')
    expect(drawn).not.toContain('acme/app')
    await ui.unmount()
  })
})
