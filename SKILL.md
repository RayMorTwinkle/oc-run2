---
name: oc-run2-subagent
description: 让任意 Harness（ZCode/Claude Code/Codex…）把 OpenCode 2（opencode2 beta）当子 Agent 用：模型自由（不绑定主 Agent 供应商，可混用 DeepSeek/GLM/Kimi/免费档等任意套餐）、并行派活（≤6）、--session 原生续跑迭代、官方 API 跨项目历史查询、cost 花费统计、--agent/--variant 精细控制。当用户提到 oc-run2、opencode2 子 Agent、并行调度 opencode2、opencode2 中转站、续跑 opencode2 session、token 外包搜索时使用。
metadata:
  version: 1.0.0
  tested-on: opencode2 v0.0.0-beta-19059
compatibility:
  - zcode
  - claude-code
  - codex
  - cursor
  - opencode
  - gemini-cli
license: MIT
---

# oc-run2 — 把 OpenCode 2 变成任意 Harness 的子 Agent

主 Agent 负责指挥，OpenCode 2 子 Agent 负责干活——用任何模型，干任何活。OpenCode 2 本身 provider 中立，子 Agent 可以用任意配置的模型，不绑定主 Agent 同家供应商；"大量读"的活外包给便宜的模型，高级 token 只花在指挥决策上。

技术上是主 Agent 与 opencode2 子 Agent 之间的调度接口：给出若干"工作区目录 + 提示词"，它并行派发给独立子 Agent（≤6 个），完成后返回结构化汇总（session、动作次数、tokens、cost、最终报告）。子 Agent 的搜索、读码、思考都在隔离环境完成，不占主 Agent 上下文；`--session` 续跑由 OpenCode 2 **原生支持**（无 V1 的挂起 bug），保持记忆做多轮迭代。

> 仅支持 OpenCode 2（`opencode2` 命令，beta）。OpenCode 1.x 请用姊妹项目 **oc-run**；
> 华为 DevEco Code 子 Agent 调度见 **de-run**。

## 安装

前置要求：opencode2 CLI（`npm i -g @opencode-ai/cli@beta`，beta 阶段不支持 brew/docker）+ Python 3.9+。

```bash
# 把 oc-run2 放进 PATH（示例：软链到 ~/.local/bin）
ln -s "$(pwd)/scripts/oc-run2.py" ~/.local/bin/oc-run2
```

## 快速开始

```bash
# 单个任务（阻塞执行，跑完输出汇总）
oc-run2 --dir /path/to/project --prompt "分析这个项目的技术栈"

# 多个任务：工作目录与提示词一一对应（主用法，并行度默认 6、上限 6）
oc-run2 --dir /path/A --prompt "分析项目A" --dir /path/B --prompt "分析项目B"

# 多个目录共用同一个提示词（广播）
oc-run2 --dir /path/A --dir /path/B --prompt "用中文简述这个项目"

# 批量任务文件（每任务自定义 dir / prompt / title）
oc-run2 --tasks tasks.json   # 文件为 [{"dir": "...", "prompt": "...", "title": "..."}, ...]

# 续跑：接着某个 session 的上下文继续跑（OpenCode 2 原生支持，保持记忆）
oc-run2 --sessions                                   # 查看历史 session（跨所有项目，官方 API）
oc-run2 --dir /path/A --session ses_xxx --prompt "继续上次的分析"

# 指定模型 / 模型变体 / agent（不传则用 opencode2 配置）
oc-run2 --dir /path/A --prompt "..." --model volcengine/glm-5.3-flash
oc-run2 --dir /path/A --prompt "..." --model opencode-go/glm-5.3 --variant max
oc-run2 --dir /path/A --prompt "..." --agent plan

# 机器可读输出（给 LLM / 脚本消费，含 tokens 与 cost）
oc-run2 --dir /path/A --prompt "..." --json
```

完整参数见 `oc-run2 --help`（输出面向 LLM 的中文使用说明）。

## 读图 / 附带文件

读图或附带文件**无需任何额外参数**——把文件路径写进提示词，子 Agent 会用工具自行读取：

```bash
oc-run2 --dir /path --prompt "读取图片 /path/to/img.png 并描述内容"
```

## 从 LLM / Agent 中调用

把 oc-run2 当作可外包的执行单元，报告是唯一接口。两种推荐用法：

1. **token 外包（单轮）——大量读、简洁报**：派临时子 Agent 去读海量资料（网页/代码/文档），回报只要简洁结论+来源。子 Agent 独立上下文，读再多也不占你的上下文。
2. **主从循环（多轮）——强模型指挥弱模型**：用 `--session` 续跑同一子 Agent（保持记忆），按每次回报决定下一轮，循环直到结果达标。两条铁律：
   - 任务描述要详细：子 Agent 没有你的全局视野，prompt 就是它的世界
   - 回报格式要明确：你只能看到报告/最后发言——回报至少包含 结论 + 来源 + 不确定性 + 未完成项 + 关键函数或举措

两种用法均可并行（一次派多个，≤6）、可异步（借宿主环境的后台任务机制，完成自动通知）。

## 已知坑（opencode2 beta 相关）

- **OpenCode 2 处于 beta**（实测 v0.0.0-beta-19059）：server API 可能继续变化，oc-run2 已对未知事件类型/字段宽容处理；遇到异常先升级 opencode2（`opencode2 upgrade`）再复测
- **权限自动批准**：oc-run2 自动携带 `--auto`（V2 中替代 V1 的 `--dangerously-skip-permissions`）；只读分析类任务勿让 agent 改文件
- **共享后台服务**：V2 默认连接用户级共享后台服务（`opencode2 service status` 可查）；高并行度遇到异常可降低 `--max-parallel`
- **调试**：设 `OC_RUN2_DEBUG=1` 可把每个任务的原始 JSONL 事件流存到系统临时目录

## License

MIT
