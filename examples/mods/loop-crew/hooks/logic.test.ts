import { describe as group, expect, test } from 'claude-code/testing'

import { ACTS, FRAME_MS, STILL, act, cells, clip, figureCells, findRoot, fitting, lockPid, parseStatus, roundText, scene, stepLine, svg, word } from './logic'
import type { Row, Seen } from '../types'

const row = (over: Partial<Row>): Row => ({ number: 1, title: 'A job', step: 'BUILD', state: 'working', round: 1, ...over })
const ALL = [...Object.values(ACTS), STILL]

// The cells back from a Raster's base64, as [code point, foreground, background].
function decode(text: string): [number, number, number][] {
  const bytes = Uint8Array.from(atob(text), c => c.charCodeAt(0))
  const view = new DataView(bytes.buffer)
  const out: [number, number, number][] = []
  for (let i = 0; i < bytes.length; i += 12) out.push([view.getUint32(i, true), view.getUint32(i + 4, true), view.getUint32(i + 8, true)])
  return out
}

group("a step's word and act", () => {
  test('each step has its word and its own act', () => {
    const words: [string, string][] = [
      ['SHAPE', 'planning'], ['TEST', 'writing tests'], ['BUILD', 'building'],
      ['VALIDATE', 'checking'], ['SCALE', 'opening the pull request'],
    ]
    for (const [step, text] of words) {
      expect(word(step)).toBe(text)
      expect(act(step)).toBe(ACTS[step]!)
    }
    expect(new Set(words.map(([step]) => act(step))).size).toBe(5)
  })
  test('an empty step is starting, standing still', () => {
    expect(word('')).toBe('starting')
    expect(act('')).toBe(STILL)
  })
  test('an unknown step is lowercased as written, standing still', () => {
    expect(word('DEPLOY')).toBe('deploy')
    expect(act('DEPLOY')).toBe(STILL)
  })
  test("a step named like an object's own property is still unknown", () => {
    expect(word('constructor')).toBe('constructor')
    expect(act('constructor')).toBe(STILL)
  })
  test('a zero round says nothing, and any other says its number', () => {
    expect(roundText(0)).toBe('')
    expect(roundText(2)).toBe('round 2')
    expect(stepLine(row({ step: 'BUILD', round: 2 }))).toBe('building, round 2')
    expect(stepLine(row({ step: 'SHAPE', round: 0 }))).toBe('planning')
  })
})

group('the frames', () => {
  test('every frame of every act is 16 by 16, each pixel naming a colour in its palette', () => {
    for (const a of ALL) {
      for (const frame of a.frames) {
        expect(frame.length).toBe(16)
        for (const line of frame) {
          expect(line.length).toBe(16)
          for (const pixel of line) expect(a.palette[pixel]).toBeDefined()
        }
      }
    }
  })
  test('the acts have two to four frames, and standing still has one', () => {
    for (const a of Object.values(ACTS)) {
      expect(a.frames.length).toBeGreaterThan(1)
      expect(a.frames.length).toBeLessThan(5)
    }
    expect(STILL.frames.length).toBe(1)
  })
  test("an act's frames differ from one another", () => {
    for (const a of Object.values(ACTS)) expect(new Set(a.frames.map(f => f.join())).size).toBe(a.frames.length)
  })
})

group('the Raster cells', () => {
  test('decode to 16 by 8 triplets of width-1 characters', () => {
    const decoded = decode(figureCells('BUILD', 0))
    expect(decoded.length).toBe(16 * 8)
    for (const [code, fg, bg] of decoded) {
      expect(code).toBe(0x2580)
      expect(String.fromCodePoint(code).length).toBe(1)
      expect(fg).toBeLessThan(0x01000000)
      expect(bg).toBeLessThan(0x01000000)
    }
  })
  test("a cell's top pixel is its foreground and its bottom pixel its background", () => {
    const frame = Array.from({ length: 16 }, (_, y) => (y === 2 ? 'ab' : y === 3 ? 'ba' : 'aa').padEnd(16, 'a'))
    const decoded = decode(cells(frame, { a: 0x111111, b: 0x222222 }))
    expect(decoded[16]).toEqual([0x2580, 0x111111, 0x222222])
    expect(decoded[17]).toEqual([0x2580, 0x222222, 0x111111])
  })
  test('the frame counter walks the act and wraps', () => {
    const n = ACTS.BUILD!.frames.length
    expect(figureCells('BUILD', 1)).not.toBe(figureCells('BUILD', 0))
    expect(figureCells('BUILD', n)).toBe(figureCells('BUILD', 0))
    expect(figureCells('', 1)).toBe(figureCells('', 0))
  })
})

group('the Svg', () => {
  const longest = Object.values(ACTS).reduce((a, b) => (b.frames.length > a.frames.length ? b : a))
  test('the longest act fits, a group per frame, repeating, with no script', () => {
    const source = svg(longest)
    expect(source.length).toBeLessThan(131073)
    expect(source.match(/<g[ >]/g)?.length).toBe(longest.frames.length)
    expect(source.match(/<animate /g)?.length).toBe(longest.frames.length)
    expect(source).toContain('repeatCount="indefinite"')
    expect(source).toContain(`dur="${longest.frames.length * FRAME_MS}ms"`)
    expect(source).not.toContain('<script')
    expect(/\son\w*=/.test(source)).toBe(false)
  })
  test('every act fits, and only its first frame shows where SMIL does not run', () => {
    for (const a of ALL) {
      const source = svg(a)
      expect(source.length).toBeLessThan(131073)
      expect(source.match(/<g visibility="hidden">/g)?.length ?? 0).toBe(a.frames.length - 1)
    }
  })
  test('a one-frame act has one group and no animation', () => {
    const source = svg(STILL)
    expect(source.match(/<g[ >]/g)?.length).toBe(1)
    expect(source).not.toContain('<animate')
  })
})

group('the scene', () => {
  const look = (over: Partial<Seen>): Seen => ({ status: { issues: [] }, isLive: true, ...over })
  test('no status file comes first, even with a live lock', () => {
    expect(scene(look({ status: null })).message).toBe('No loop has run here yet.')
    expect(scene(null).message).toBe('No loop has run here yet.')
  })
  test('with no live lock there are no figures, even for rows left at working', () => {
    const seen = look({ isLive: false, status: { issues: [row({})] } })
    expect(scene(seen)).toEqual({ message: "The loop isn't running.", rows: [] })
  })
  test('with nothing working it says so', () => {
    expect(scene(look({ status: { issues: [row({ state: 'pr' })] } })).message).toBe('Nothing being built right now.')
  })
  test('working rows come in issue-number order, and others are left out', () => {
    const issues = [row({ number: 9 }), row({ number: 3 }), row({ number: 5, state: 'blocked' })]
    expect(scene(look({ status: { issues } })).rows.map(r => r.number)).toEqual([3, 9])
  })
})

group('how many figures fit', () => {
  test('all of them when all fit', () => {
    expect(fitting(3, 27)).toBe(3)
    expect(fitting(1, 9)).toBe(1)
  })
  test('otherwise as many as leave one row for the line under them', () => {
    expect(fitting(3, 26)).toBe(2)
    expect(fitting(4, 28)).toBe(3)
  })
  test('never fewer than one', () => {
    expect(fitting(3, 4)).toBe(1)
  })
  test('3 when the height is absent or not a number', () => {
    expect(fitting(5)).toBe(3)
    expect(fitting(5, Number.NaN)).toBe(3)
    expect(fitting(5, Number.POSITIVE_INFINITY)).toBe(3)
    expect(fitting(2)).toBe(2)
  })
})

group('the copied helpers', () => {
  test('the status file: a bad one is none, and a row without a number is dropped', () => {
    expect(parseStatus(null)).toBeNull()
    expect(parseStatus('{not json')).toBeNull()
    expect(parseStatus(JSON.stringify({ issues: [{ title: 'no number' }, { number: 4, title: 'T', step: 'BUILD', state: 'working', round: 2, pr: 'x' }] })))
      .toEqual({ issues: [{ number: 4, title: 'T', step: 'BUILD', state: 'working', round: 2 }] })
  })
  test("the lock's pid", () => {
    expect(lockPid('4242\n')).toBe(4242)
    expect(lockPid('nonsense')).toBeNull()
  })
  test('a clip cuts with an ellipsis', () => {
    expect(clip('abcdef', 4)).toBe('abc…')
    expect(clip('abc', 4)).toBe('abc')
  })
  test('the root is the nearest folder holding the script', async () => {
    const exists = async (path: string) => path === '/h/starter/scripts/loop.py'
    expect(await findRoot('/h/starter/projects/acme', exists)).toBe('/h/starter')
    expect(await findRoot('/elsewhere', exists)).toBeNull()
  })
})
