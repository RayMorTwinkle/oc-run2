<div align="center">

> [English](./README_en.md) | 简体中文

<img src="oc-run2.svg" alt="oc-run2" width="320">

# oc-run2 — 把 OpenCode 2 变成任意 Harness 的子 Agent

![Python](https://img.shields.io/badge/Python-3.9%2B-blue) ![License](https://img.shields.io/badge/License-MIT-green) ![Deps](https://img.shields.io/badge/Dependencies-zero-brightgreen) ![OpenCode2](https://img.shields.io/badge/OpenCode%202-beta-8B5CF6) ![Type](https://img.shields.io/badge/Type-AI_Skill-orange)

**把你的主 Agent 从模型绑定中解放出来——主 Agent 负责指挥，OpenCode 2 子 Agent 负责干活，用任何模型，干任何活。**

</div>

---

## 它是什么

```
  你的主 Agent（ZCode / Claude Code / Codex …）
              │  oc-run2 --dir A --prompt "…" --dir B --prompt "…"
              ▼
        oc-run2 调度器 ──并行──▶ opencode2 子 Agent A（模型 X）
              │                  └── opencode2 子 Agent B（模型 Y）
              ▼
       结构化汇总：session / 动作次数 / tokens / cost / 最终报告
```

oc-run2 是一层薄薄的适配器：给出若干"工作区目录 + 提示词"，它并行派发给独立子 Agent（≤6 个），完成后返回结构化汇总。子 Agent 的搜索、读码、思考都在隔离环境完成，不占主 Agent 上下文；支持 `--session` 续跑同一子 Agent（OpenCode 2 **原生支持**，无 V1 挂起 bug），保持记忆做多轮迭代。纯 Python 标准库，零第三方依赖。

> 仅支持 OpenCode 2（`opencode2` 命令，beta，实测 v0.0.0-beta-19059）。
> 姊妹项目：**[oc-run](https://github.com/RayMorTwinkle/oc-run)** — OpenCode 1.x（`opencode` 命令）版；
> **[de-run](https://github.com/RayMorTwinkle/de-run)** — 把华为 DevEco Code 当子 Agent。

## ✨ 它能干什么

- 🎛️ **模型自由**：OpenCode 2 本身 provider 中立——子 Agent 可以用你配置的任何模型（DeepSeek、GLM、Kimi、免费档，甚至自定义 provider 里的 Claude），完全不绑定主 Agent 同家供应商
- 💰 **省高级 token + 花费透明**："大量读"的活外包给便宜的模型；汇总自动展示每个任务的真实 tokens 与 **cost（美元）**
- ⚡ **并行派活**：一次最多 6 个子 Agent 同时干活，各自独立工作目录与提示词
- 🔁 **原生续跑**：`--session` 接着同一子 Agent 继续，保持它的记忆，按报告循环指挥直到达标（V2 原生支持，无需 V1 的 serve 绕行方案）
- 🎯 **精细控制**：`--agent` 指定 OpenCode 2 agent（build/plan/…），`--variant` 指定推理强度（`provider/model#variant`）
- 📊 **官方 API 历史**：`--sessions` 经 OpenCode 2 官方 API 跨项目列出所有 session（V1 只能偷查 SQLite）
- 🧩 **任意环境可跑**：内置探测，PATH 精简环境（cron / 脚本 / Agent 子进程）也能找到 opencode2

## 🔧 安装

### 面向 AI 智能体（一键安装，推荐）

**把下面这段提示词直接复制给你的本地 AI Agent（ZCode / Claude Code / Codex 等），它就能自动完成安装：**

````markdown
请帮我安装 oc-run2 skill（GitHub: https://github.com/RayMorTwinkle/oc-run2）。

背景：oc-run2 让任何主 Agent（ZCode/Claude Code/Codex 等）都能把本机的 OpenCode 2（opencode2 命令，beta）当子 Agent 指挥——并行派活、自动汇总报告（含 tokens/cost）、--session 原生续跑、**子 Agent 可用任意模型，不绑定主 Agent 的模型供应商**。
它依赖本机已安装的 opencode2 CLI（npm i -g @opencode-ai/cli@beta）和 python3。

安装步骤：
1. 下载并解压（如果 ~/.agents/skills/oc-run2-subagent 已存在则先跳过，直接验证）：
   curl -L -o /tmp/oc-run2.zip https://github.com/RayMorTwinkle/oc-run2/archive/refs/heads/main.zip
   unzip -o /tmp/oc-run2.zip -d /tmp/ && mv /tmp/oc-run2-main ~/.agents/skills/oc-run2-subagent
   说明：~/.agents/skills/ 是多个 AI 工具共用的 skill 目录；如果你的平台用别的目录
   （如 Claude Code: ~/.claude/skills/，OpenCode: ~/.config/opencode/skills/），装到对应目录即可。
2. 验证 skill 结构：确认 ~/.agents/skills/oc-run2-subagent/SKILL.md 和 scripts/oc-run2.py 存在。
3. （可选但推荐）把 oc-run2 命令放进 PATH，方便直接调用：
   ln -sf ~/.agents/skills/oc-run2-subagent/scripts/oc-run2.py ~/.local/bin/oc-run2
4. 验证命令：oc-run2 --help 应输出中文使用说明；若 PATH 里没有，用 python3 ~/.agents/skills/oc-run2-subagent/scripts/oc-run2.py --help。
5. 端到端测试：oc-run2 --sessions 3 应列出最近 3 个 session（跨所有 git 项目）。
   若报"未找到 opencode2"，请先安装 OpenCode 2 beta 或告知用户；oc-run2 有内置探测，
   会按常见路径（~/.opencode/bin、homebrew 等）自动查找。
6. 向用户确认安装成功，并简述 oc-run2 的能力：并行派活 / 原生续跑（--session）/
   跨项目历史（--sessions）/ 模型可选（--model、--variant）/ agent 可选（--agent）/ cost 统计。
````

### 面向人类用户

1. 克隆或下载仓库：
   ```bash
   git clone https://github.com/RayMorTwinkle/oc-run2.git
   # 或下载 zip: https://github.com/RayMorTwinkle/oc-run2/archive/refs/heads/main.zip
   ```
2. 将 `oc-run2` 目录放入智能体的 skill 目录并**重命名为 `oc-run2-subagent`**（Claude Code: `~/.claude/skills/`；OpenCode: `~/.config/opencode/skills/`；通用共享: `~/.agents/skills/`）——skill 目录名须与 SKILL.md 的 `name` 一致
3. （可选）软链命令到 PATH：`ln -s "$(pwd)/oc-run2/scripts/oc-run2.py" ~/.local/bin/oc-run2`

前置要求：[OpenCode 2 beta](https://opencode.ai/v2/docs/)（`npm i -g @opencode-ai/cli@beta`）+ Python 3.9+。

## 🚀 快速开始

```bash
# 单个任务（阻塞执行，跑完输出汇总）
oc-run2 --dir /path/to/project --prompt "分析这个项目的技术栈"

# 多个任务：工作目录与提示词一一对应（主用法）
oc-run2 --dir /path/A --prompt "分析项目A" --dir /path/B --prompt "分析项目B"

# 只给 1 个提示词 = 广播到所有目录
oc-run2 --dir /path/A --dir /path/B --prompt "用中文简述这个项目"

# 批量任务文件
oc-run2 --tasks tasks.json

# 续跑（OpenCode 2 原生支持，保持记忆）
oc-run2 --sessions                                  # 查看历史（跨所有项目）
oc-run2 --dir /path/A --session ses_xxx --prompt "继续上次的分析"

# 模型 / 变体 / agent 精细控制
oc-run2 --dir /path/A --prompt "..." --model volcengine/glm-5.3-flash
oc-run2 --dir /path/A --prompt "..." --model opencode-go/glm-5.3 --variant max
oc-run2 --dir /path/A --prompt "..." --agent plan

# 机器可读输出（给 LLM / 脚本消费）
oc-run2 --dir /path/A --prompt "..." --json
```

<details>
<summary>📄 输出示例（人类可读）</summary>

```
oc-run2 汇总 · 2 个任务 · 并行度 2 · 成功 2/2 · 花费 $0.0023
────────────────────────────────────────────────────────────────────────
✅ [1] projectA
    session: ses_f7c0ada77ffeCFuvNs5qigdgC6
    动作:   5 次 (grep×2 · read×2 · glob×1)
    tokens: 41,236   cost: $0.0018
    结果:   该项目使用 Python 3.12 + FastAPI …

✅ [2] projectB
    session: ses_f7c0b1e9dffeKq2wMn8stCfWX
    动作:   3 次 (read×2 · bash×1)
    tokens: 22,871   cost: $0.0005
    结果:   主要文件清单如下 …
```

</details>

## 🆚 oc-run（V1）vs oc-run2（V2）

| | oc-run（OpenCode 1.x） | oc-run2（OpenCode 2 beta） |
|---|---|---|
| 续跑 `--session` | 原生命令挂起 bug，需自启 serve + attach 绕行 | **原生支持**，直接续跑 |
| 跨项目 session 历史 | 直查 SQLite（`opencode db`） | **官方 API** `/api/session` |
| 权限自动批准 | `--dangerously-skip-permissions` | `--auto` |
| 花费统计 | 无 | **每个任务 cost（美元）** |
| 模型变体 | — | `--variant` / `provider/model#variant` |
| 指定 agent | — | `--agent` |
| 工作目录 | `--dir` 参数 | 子进程 cwd（对调用方透明） |

## 🧠 从 LLM / Agent 中调用

把 oc-run2 当作可外包的执行单元，**报告是唯一接口**。两种推荐用法：

1. **token 外包（单轮）——大量读、简洁报**：派临时子 Agent 去读海量资料（网页/代码/文档），回报只要简洁结论+来源。子 Agent 独立上下文，读再多也不占你的上下文。
2. **主从循环（多轮）——强模型指挥弱模型**：用 `--session` 续跑同一子 Agent（保持记忆），按每次回报决定下一轮，循环直到结果达标。两条铁律：
   - 任务描述要详细：子 Agent 没有你的全局视野，prompt 就是它的世界
   - 回报格式要明确：你只能看到报告/最后发言——回报至少包含 **结论 + 来源 + 不确定性 + 未完成项 + 关键函数或举措**

两种用法均可并行（一次派多个，≤6）、可异步（借宿主环境如 ZCode / Claude Code 的后台任务机制，完成自动通知）。

## ❓ FAQ

**Q: opencode2 还是 beta，会不会哪天就坏了？**
A: 会。OpenCode 2 的 server API 仍可能变化（官方明示）。oc-run2 的解析器对未知事件类型/字段宽容处理，遇到异常先 `opencode2 upgrade` 再复测；README/SKILL 标注了实测版本 v0.0.0-beta-19059。

**Q: 和 oc-run 什么关系？装哪个？**
A: 你机器上装的是哪个就装哪个：`opencode`（1.x stable）→ [oc-run](https://github.com/RayMorTwinkle/oc-run)；`opencode2`（2.0 beta）→ oc-run2。两者可并存，命令互不冲突。

**Q: 子 Agent 会乱改我的文件吗？**
A: oc-run2 自动携带 `--auto`（自动批准权限），这是派活场景的默认需求。只读分析类任务请约束提示词（"只分析，不要修改任何文件"），或在 opencode2 配置里收紧权限。

**Q: 高并行会互相干扰吗？**
A: 各任务独立进程、独立目录、独立 session。OpenCode 2 默认共享一个用户级后台服务，极端高并发时若遇异常可降低 `--max-parallel`。

## License

MIT
