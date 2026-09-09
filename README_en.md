<div align="center">

> 简体中文 | [English](./README.md)

<img src="oc-run2.svg" alt="oc-run2" width="320">

# oc-run2 — Turn OpenCode 2 into a Sub-Agent for Any Harness

![Python](https://img.shields.io/badge/Python-3.9%2B-blue) ![License](https://img.shields.io/badge/License-MIT-green) ![Deps](https://img.shields.io/badge/Dependencies-zero-brightgreen) ![OpenCode2](https://img.shields.io/badge/OpenCode%202-beta-8B5CF6) ![Type](https://img.shields.io/badge/Type-AI_Skill-orange)

**Free your main agent from vendor lock-in — the main agent directs, OpenCode 2 sub-agents do the work, with any model, on any task.**

</div>

---

## What is it

```
  Your main agent (ZCode / Claude Code / Codex …)
              │  oc-run2 --dir A --prompt "…" --dir B --prompt "…"
              ▼
        oc-run2 dispatcher ──parallel──▶ opencode2 sub-agent A (model X)
              │                          └── opencode2 sub-agent B (model Y)
              ▼
       Structured summary: session / tool calls / tokens / cost / final report
```

oc-run2 is a thin adapter: give it a set of "working directory + prompt" tasks, and it dispatches them in parallel to independent sub-agents (up to 6), returning a structured summary when done. All the sub-agent's searching, code reading, and thinking happen in an isolated context, never touching yours. `--session` resumes the same sub-agent (natively supported by OpenCode 2 — no V1 hang-around needed), preserving memory for multi-turn iterations. Pure Python standard library, zero third-party dependencies.

> Requires OpenCode 2 (`opencode2` command, beta; tested on v0.0.0-beta-19059).
> Sister projects: **[oc-run](https://github.com/RayMorTwinkle/oc-run)** for OpenCode 1.x (`opencode` command);
> **[de-run](https://github.com/RayMorTwinkle/de-run)** for Huawei DevEco Code as a sub-agent.

## ✨ Highlights

- 🎛️ **Model freedom**: OpenCode 2 is provider-neutral — sub-agents can use any configured model (DeepSeek, GLM, Kimi, free tiers, even Claude via custom providers), completely decoupled from the main agent's vendor
- 💰 **Save premium tokens + cost transparency**: outsource heavy reading to cheap models; the summary shows real tokens and **cost (USD) per task**
- ⚡ **Parallel dispatch**: up to 6 sub-agents working simultaneously, each with its own working directory and prompt
- 🔁 **Native resume**: `--session` continues the same sub-agent with memory intact, looping until results meet the bar (natively supported in V2)
- 🎯 **Fine-grained control**: `--agent` selects an OpenCode 2 agent (build/plan/…), `--variant` sets reasoning effort (`provider/model#variant`)
- 📊 **Official API history**: `--sessions` lists all sessions across projects via the official OpenCode 2 API (V1 had to poke SQLite)
- 🧩 **Runs anywhere**: built-in probing finds opencode2 even in stripped PATH environments (cron / scripts / agent subprocesses)

## 🔧 Install

### For AI agents (one-shot, recommended)

**Copy this prompt to your local AI agent (ZCode / Claude Code / Codex etc.) and it will handle the installation:**

````markdown
Please install the oc-run2 skill (GitHub: https://github.com/RayMorTwinkle/oc-run2).

Background: oc-run2 lets any main agent (ZCode/Claude Code/Codex etc.) use the local OpenCode 2 (`opencode2` command, beta) as a sub-agent — parallel dispatch, structured summaries (tokens/cost), native --session resume, **sub-agents can use any model regardless of the main agent's provider**.
It requires the opencode2 CLI (npm i -g @opencode-ai/cli@beta) and python3.

Steps:
1. Download and unzip (skip if ~/.agents/skills/oc-run2-subagent already exists, then just verify):
   curl -L -o /tmp/oc-run2.zip https://github.com/RayMorTwinkle/oc-run2/archive/refs/heads/main.zip
   unzip -o /tmp/oc-run2.zip -d /tmp/ && mv /tmp/oc-run2-main ~/.agents/skills/oc-run2-subagent
   Note: ~/.agents/skills/ is a shared skill directory for multiple AI tools; adapt the path
   for your platform (Claude Code: ~/.claude/skills/, OpenCode: ~/.config/opencode/skills/).
2. Verify: ~/.agents/skills/oc-run2-subagent/SKILL.md and scripts/oc-run2.py exist.
3. (Optional but recommended) link the command into PATH:
   ln -sf ~/.agents/skills/oc-run2-subagent/scripts/oc-run2.py ~/.local/bin/oc-run2
4. Verify: `oc-run2 --help` should print usage in Chinese; if not in PATH, run
   python3 ~/.agents/skills/oc-run2-subagent/scripts/oc-run2.py --help.
5. End-to-end check: `oc-run2 --sessions 3` should list the 3 most recent sessions (across all projects).
   If "opencode2 not found", install OpenCode 2 beta first; oc-run2 probes common paths automatically.
6. Confirm success to the user and summarize oc-run2's capabilities: parallel dispatch /
   native resume (--session) / cross-project history (--sessions) / model choice (--model, --variant) /
   agent choice (--agent) / cost stats.
````

### For humans

1. Clone or download:
   ```bash
   git clone https://github.com/RayMorTwinkle/oc-run2.git
   # or: https://github.com/RayMorTwinkle/oc-run2/archive/refs/heads/main.zip
   ```
2. Put the `oc-run2` directory into your agent's skill directory and **rename it to `oc-run2-subagent`** (Claude Code: `~/.claude/skills/`; OpenCode: `~/.config/opencode/skills/`; shared: `~/.agents/skills/`) — the directory name must match SKILL.md's `name`
3. (Optional) symlink into PATH: `ln -s "$(pwd)/oc-run2/scripts/oc-run2.py" ~/.local/bin/oc-run2`

Prerequisites: [OpenCode 2 beta](https://opencode.ai/v2/docs/) (`npm i -g @opencode-ai/cli@beta`) + Python 3.9+.

## 🚀 Quick start

```bash
# Single task (blocking; summary printed when done)
oc-run2 --dir /path/to/project --prompt "Analyze this project's tech stack"

# Multiple tasks: dirs and prompts pair up in order (main usage)
oc-run2 --dir /path/A --prompt "Analyze A" --dir /path/B --prompt "Analyze B"

# One prompt = broadcast to all dirs
oc-run2 --dir /path/A --dir /path/B --prompt "Summarize this repo"

# Batch task file
oc-run2 --tasks tasks.json

# Resume (native in OpenCode 2, memory preserved)
oc-run2 --sessions                                  # history across all projects
oc-run2 --dir /path/A --session ses_xxx --prompt "Continue the analysis"

# Model / variant / agent control
oc-run2 --dir /path/A --prompt "..." --model volcengine/glm-5.3-flash
oc-run2 --dir /path/A --prompt "..." --model opencode-go/glm-5.3 --variant max
oc-run2 --dir /path/A --prompt "..." --agent plan

# Machine-readable output (for LLMs / scripts, includes tokens & cost)
oc-run2 --dir /path/A --prompt "..." --json
```

## 🆚 oc-run (V1) vs oc-run2 (V2)

| | oc-run (OpenCode 1.x) | oc-run2 (OpenCode 2 beta) |
|---|---|---|
| Resume `--session` | native command hangs; serve+attach workaround | **native**, just works |
| Cross-project history | direct SQLite query | **official API** `/api/session` |
| Permission auto-approve | `--dangerously-skip-permissions` | `--auto` |
| Cost stats | none | **per-task cost (USD)** |
| Model variants | — | `--variant` / `provider/model#variant` |
| Agent selection | — | `--agent` |
| Working directory | `--dir` flag | subprocess cwd (transparent to callers) |

## 🧠 Calling from LLMs / agents

Treat oc-run2 as an outsourceable execution unit; **the report is the only interface**. Two recommended patterns:

1. **Token outsourcing (single turn) — read a lot, report briefly**: dispatch a temp sub-agent to read massive material (web/code/docs); the report only needs concise conclusions + sources. Sub-agent context is isolated, so reading never bloats yours.
2. **Master-servant loop (multi-turn) — strong model directs weak model**: resume the same sub-agent with `--session` (memory kept), decide the next round from each report, loop until the result is good enough. Two iron rules:
   - Be detailed: the sub-agent has no global view — your prompt is its entire world
   - Specify the report format: you only see the final report — require conclusions + sources + uncertainties + unfinished items + key functions or actions

Both patterns support parallelism (up to 6 at once) and async execution (via the host environment's background tasks, with completion notifications).

## ❓ FAQ

**Q: opencode2 is beta — will it break someday?**
A: Possibly. The V2 server API may still change (officially stated). oc-run2's parser tolerates unknown event types/fields; if something breaks, run `opencode2 upgrade` first. The tested version (v0.0.0-beta-19059) is noted in the README/SKILL.

**Q: Relationship with oc-run? Which one do I install?**
A: Whichever binary you have: `opencode` (1.x stable) → [oc-run](https://github.com/RayMorTwinkle/oc-run); `opencode2` (2.0 beta) → oc-run2. They coexist without conflict.

**Q: Will sub-agents mess with my files?**
A: oc-run2 passes `--auto` (auto-approve permissions) — the default for dispatch scenarios. For read-only analysis, constrain the prompt ("analyze only, do not modify files") or tighten permissions in your opencode2 config.

**Q: Does high parallelism cause interference?**
A: Each task runs in its own process, directory, and session. OpenCode 2 shares one user-level background service by default; if you hit anomalies at extreme concurrency, lower `--max-parallel`.

## License

MIT
