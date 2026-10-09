# Harness lens

A harness works where you can't see it. The session just behaves better, and
nobody can say which part did that. This mod draws one line above the prompt
naming the layer that just acted:

```
◆ harness  steering: 3 always on + gates  skill: review-tests  gate: ✗ proposal  guard: ✗ refused Bash  review: reviewer
```

It's a Claude Code mod, so it works in Claude Code only. Codex and Kiro don't
have mods.

## Load it

From the harness root:

```bash
claude --plugin-dir examples/mods/harness-lens
```

That loads it for one session. To load it in every session, put the folder's
absolute path in `CLAUDE_CODE_PLUGIN_DIRS`, in the `env` block of your
`~/.claude/settings.json`:

```json
"env": { "CLAUDE_CODE_PLUGIN_DIRS": "/Users/<you>/<your-harness>/examples/mods/harness-lens" }
```

The project's own [`.claude/settings.json`](../../../.claude/settings.json) can't load a mod. It has to be the
command line or your user settings.

## Reading the band

| Segment | Shows |
|---|---|
| **steering** | How many steering files load into every session (the `@` lines in [`AGENTS.md`](../../../AGENTS.md)), plus any the agent read because they applied |
| **skill** | The last of this harness's skills the agent followed, whether you typed `/name` or it read the `SKILL.md` |
| **gate** | The last gate run and how it went. A commit the pre-commit hook refused shows as `✗ pre-commit`. A commit that got through shows nothing, because the hook is silent when it passes |
| **guard** | The last tool a guard refused. Never the reason: that's in the transcript, and it can name a file |
| **review** | The last reviewer agent the work went to |

Cyan means it happened this turn. A gate or guard result this turn is green or
red. Plain text happened earlier in the session, and dim means nothing yet. A
guard refusal and a failed gate also pop up a short notice.

`/lens` prints the whole session, layer by layer: every steering file read,
every skill followed, each gate with how many times it passed and failed, and
the refusals by tool.

## Try it

Load it, then:

1. Ask for something a steering file covers ("read the gates steering"), and
   watch **steering** pick it up.
2. Run the example's gate on a proposal with a `{{placeholder}}` in it, and
   watch **gate** go red.
3. Ask the agent to print `.env`. **guard** goes red with the tool it refused.
4. Type `/review-tests`, then hand the work to the `reviewer` agent.
5. Type `/lens`.

## What it doesn't do

It only looks. It never blocks a call or changes one: the guard in
[`.claude/hooks/guard.py`](../../../.claude/hooks/guard.py) and the gates do that, and they work without it.

It shows only this harness's own skills and agents. A skill from a plugin on
your machine never appears, so the band is safe to put on a projector. A
subagent's own file reads don't count either. The band is about the session
you're driving.

## Another layout

It looks for the starter's shape: [`AGENTS.md`](../../../AGENTS.md) beside [`steering/`](../../../steering/), skills in
[`skills/`](../../../skills/) and `examples/*/skills/`, agents in [`agents/`](../../../agents/), gates named
`*_gate.py`. A harness laid out differently says where its layers live in
`.claude/harness-lens.json` at its root. Every key is optional, and a key left
out keeps the starter's value:

```json
{
  "steering": [".studio/steering"],
  "always": ["CLAUDE.md"],
  "skills": [".studio/skills"],
  "skillPrefixes": ["studio:"],
  "agents": [".claude/agents"],
  "gates": ["check-gates\\.sh\\s+(\\S+)"]
}
```

`gates` are patterns for the shell command that runs a gate. The first group
in the pattern is the gate's name.

## Changing it

[`hooks/logic.ts`](hooks/logic.ts) holds the decisions as plain functions, so they can be tested.
[`hooks/register.tsx`](hooks/register.tsx) reads files, watches the session and calls into them.
From [`examples/mods/`](../):

```bash
claude plugin validate harness-lens
claude plugin test harness-lens
```

CI doesn't run these, because they need Claude Code installed.
