# Decision Record 2026-09-27: Agent Tool Interfaces (CLI, MCP, AXI)

## Status timeline

2026-09-27: Proposed by Claude, at JC's request

2026-09-27: Amended by Claude, at JC's request: output formats use standard CSV and NDJSON; TOON is optional, not the default.

## Objective Context

### Simple, lovable, complete must haves

#### Functional

One rule for how agents reach tools in this repo: our own tools, outside services, and hooks. It must work with pi, the chosen harness ([Vendor-Neutral AI Harness](2026-09-26-vendor-neutral-ai-harness.md)), and with any harness we might swap to.

#### Non-functional

Cheap in tokens and turns, reliable, and portable across harnesses. Revisited with evidence from our own evals, not public benchmarks alone.

### Nice to haves

#### Functional

Hooks (guardrails, context injection, checks at the end of a run) that behave the same in every harness.

#### Non-functional

### Avoid out of scope runaway rabbit hole risks

#### Functional

Wrapping every existing CLI in an agent-specific version before an eval shows it pays off.
Writing our own MCP servers or protocol layers.

#### Non-functional

## Decision

### Terms

- **CLI**: the agent runs a command through a shell tool (pi's `bash`). Output is usually written for people.
- **MCP** (Model Context Protocol): the harness registers typed tool schemas, and the model calls them as structured tool calls.
- **AXI** (Agent eXperience Interface, [axi.md](https://axi.md/)): not a protocol but 10 design principles for CLIs whose main user is an agent:
  1. compact output (AXI suggests TOON; see Output formats for what this repo uses)
  2. 3–4 fields per list item by default
  3. truncation with size hints and a `--full` flag
  4. counts and statuses computed up front
  5. explicit empty states ("0 results")
  6. structured errors and exit codes, idempotent changes, no prompts
  7. ambient context through session hooks or skills
  8. no arguments shows live data, not help text
  9. each output suggests the next command
  10. short help for each subcommand

### Rules

1. **Our own tools are CLIs written AXI-style.** This covers `make` targets, `evals/run`, and checks and scripts under `scripts/` or a project folder. Apply the principles that fit the tool. At a minimum: no interactive prompts, meaningful exit codes, definitive empty states, compact output by default with a `--full` flag, and a suggested next step when there is an obvious one.
2. **Existing, well-known CLIs are used as they are** (`git`, `gh`, `curl`, `jq`, `nix`). Models know them from training. Pipe or filter their output (`| head`, `--json` with `| jq`) rather than wrapping them.
3. **MCP only for outside services** that have no good CLI, or that need OAuth or permissions the harness manages. In pi this goes through [pi-mcp-adapter](https://github.com/nicobailon/pi-mcp-adapter). Declare it as a pinned package in `.pi/settings.json`, and put servers in the project `.mcp.json` so other harnesses read the same config. Cover each MCP server we rely on with an eval case.
4. **Output formats are standard, not new.** See Output formats below.
5. **Hooks call a script.** Hook logic lives in a script in the repo. Each harness's hook calls that script: in pi, a thin project extension that subscribes to the event with `pi.on(...)`; in Claude Code, a command hook in `.claude/settings.json`. The logic is then written once, and only the small adapter is specific to a harness.

### Output formats

| Output | Format | Why |
|---|---|---|
| Lists and tables (default) | CSV with a header row, then a total line such as `# 50 of 213, --full for all` | cheapest format with real escaping; models know it well; any tool reads it |
| Nested or single-record output | short `key: value` lines, or TOON if a tool really needs nested data | CSV can't nest |
| `--json` | NDJSON, one object per line | for scripts, `jq`, streaming, and eval results; safest when a model must write the data |
| Errors | one line on stderr (`error: <code>: <message>`), plus a non-zero exit code | structured and greppable |

Write CSV with a real CSV writer, never by joining strings. Values with commas, quotes, or newlines must be quoted.

Measured on a sample list of 50 issues with 5 fields (o200k tokenizer, 2026-09-27), as a share of pretty JSON's tokens:

| Format | Share |
|---|---|
| TSV | 35–36% |
| CSV | 37–39% |
| TOON | 42–43% |
| NDJSON | 61–62% |
| Minified JSON | 59% |

For flat lists, TOON is CSV plus an item count and an indent on each row. It adds nesting, which CSV lacks, but here it cost about 12% more than CSV. Its authors report about 40% savings against pretty JSON with similar accuracy for data a model reads ([toon-format/toon](https://github.com/toon-format/toon)). A 2026 paper found plain JSON more accurate when a model has to write the data ([arXiv 2603.03306](https://arxiv.org/abs/2603.03306)). TSV was cheapest, but it breaks on tabs and newlines inside values and has no escaping, so it isn't the default.

### Why the protocol matters less than it did

MCP used to cost more in two ways:

1. **Schemas in context every turn.** Mostly solved. Lazy loading loads a tool's definition only when it's needed: Claude Code's MCP tool search, the Claude API's tool search tool with `defer_loading`, and pi-mcp-adapter's single proxy tool of about 200 tokens. Reported savings are about 85% of schema tokens, with higher accuracy on large tool sets (Opus 4.5 went from 79.5% to 88.1% on Anthropic's MCP evals). Prompt caching cuts the remaining cost further.
2. **Verbose output and extra turns.** Not solved. Tool search only changes what loads, not what a tool returns, and each lookup costs a turn. In the AXI GitHub benchmark, MCP with ToolSearch still used 154K input tokens and 8 turns per task, against 46K and 3 for AXI.

So the choice now depends mostly on how well a tool's output is designed, whether output can be piped, whether models already know the tool, where it runs, and how portable it is. The protocol comes second.

### pi specifics (September 2026)

- **CLI and AXI:** they work out of the box through `bash`. This is pi's intended style: four built-in tools, and an agent that extends itself with scripts and skills.
- **MCP:** pi has none built in, deliberately. It needs pi-mcp-adapter (`pi install npm:pi-mcp-adapter`), a community package with one maintainer. It lazy-loads through one `mcp` proxy tool and reads `.mcp.json`, `~/.config/mcp/mcp.json`, and `.pi/mcp-adapter.json`.
- **Hooks:** there is no separate hooks feature. TypeScript extensions subscribe to events with `pi.on(...)`, and project extensions can be committed. The rough match to Claude Code hooks:

| Claude Code hook | pi event | Can |
|---|---|---|
| `SessionStart` / `SessionEnd` | `session_start` / `session_shutdown` | set up and clean up |
| `PreToolUse` | `tool_call` | change a tool's input or block the call |
| `PostToolUse` | `tool_result` | rewrite the result |
| `UserPromptSubmit` | `before_agent_start`, `context` | change the prompt, active tools, model, or messages |
| `Stop` | `agent_end`, `agent_settled`, `turn_end` | act when a run finishes |

pi also has `cache_warming_decision` and `project_trust`, which Claude Code lacks.

### High-level C4(context/container/component/code) diagram

```
agent (pi, or another harness)
  ├── bash ──> AXI-style repo CLIs (make, evals/run, scripts)   ← default for our tools
  │       └──> well-known CLIs (git, gh, curl, jq, nix)          ← used as they are
  ├── mcp (pi-mcp-adapter proxy, lazy) ──> outside services with no good CLI or with managed auth
  └── hooks: pi extension / Claude Code hook ──> one shared script in the repo
```

### Choices and Tradeoffs/Risks

- **AXI-style CLIs over MCP for our own tools:** they work in any harness with a shell and need no extension. The cost is designing the output for agents. The evidence is mostly the AXI author's own benchmarks (one repo, one model that also served as judge), so treat the size of the gains as unproven until our evals confirm it.
- **MCP through a community adapter:** one maintainer and no vendor backing, the same risk the harness record accepts for `pi-web-access`. Pin the version. If it goes away, fall back to a CLI or a small skill that calls the service's API with `curl`.
- **Security:** MCP servers and hooks run with the agent's permissions, and their output reaches the model. Treat tool output as untrusted data. Only commit hooks and MCP servers the repo trusts, since pi's `project_trust` runs before project extensions load.
- **CSV over TOON by default:** CSV is standard, cheaper for flat lists, and readable by every tool. It gives up types, nesting, and a declared item count; the total line covers truncation. Revisit if our evals show TOON improving accuracy on our output.
- **Lazy loading is not free:** each discovery step costs a turn, and in the benchmark MCP with ToolSearch took more turns than MCP loading every schema up front. Keep often-used tools loaded up front, and leave lazy loading for large tool sets.

### Dependencies

- [Vendor-Neutral AI Harness](2026-09-26-vendor-neutral-ai-harness.md): pi as the harness and the eval runner that measures these choices.
- [SPEC-0002](../../specs/SPEC-0002-vendor-neutral-ai-harness.md): the evals that this record's key results rely on.

### Interfaces

- Repo CLIs: CSV or `key: value` on stdout by default, NDJSON with `--json`, errors on stderr, meaningful exit codes, and no prompts.
- MCP: the project `.mcp.json`, plus `.pi/mcp-adapter.json` for pi-only overrides.
- Hooks: a script in the repo, called by each harness's thin adapter.

## Key Results and retrospective feedback

- Once evals exist, add a case that runs the same task through an existing CLI (such as `gh`), an MCP server (such as GitHub's), and an AXI-style wrapper if one exists. Record pass rate, tokens, turns, and cost per completed task. Amend this record with the results.
- Revisit when pi gains built-in MCP support, when a harness adds a new way to load tools, or when an eval shows MCP beating a CLI on our tasks.

Sources checked on 2026-09-27:

- [AXI: Agent eXperience Interface](https://axi.md/) and its [GitHub benchmark study](https://github.com/kunchenguid/axi/blob/main/bench-github/published-results/STUDY.md)
- [pi extensions docs](https://github.com/badlogic/pi-mono/blob/main/packages/coding-agent/docs/extensions.md)
- [pi-mcp-adapter](https://github.com/nicobailon/pi-mcp-adapter)
- [Pi: The Minimal Agent Within OpenClaw (Armin Ronacher)](https://lucumr.pocoo.org/2026/1/31/pi/)
- [Tool search tool, Claude Platform Docs](https://platform.claude.com/docs/en/agents-and-tools/tool-use/tool-search-tool)
- [Introducing advanced tool use (Anthropic)](https://www.anthropic.com/engineering/advanced-tool-use)
- [What is MCP Tool Search? (Cyrus)](https://www.atcyrus.com/stories/mcp-tool-search-claude-code-context-pollution-guide)
