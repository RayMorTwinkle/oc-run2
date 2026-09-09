#!/usr/bin/env python3
"""
oc-run2 — opencode2 中转站（批量并行调度 + 结果汇总）

把若干"工作区目录 + 提示词"任务并行交给 opencode2 CLI（OpenCode 2 beta）执行，
全部结束后自动解析 opencode2 输出的 JSONL 事件流，并通过官方 API 补全
每个 Agent 的 session ID、动作次数、tokens、花费与最终结果。

无参数运行或 --help 输出详细使用说明（面向大模型）。
纯 Python 标准库，零第三方依赖。

姊妹项目: oc-run（OpenCode 1.x / `opencode` 命令版）
本工具仅支持 OpenCode 2（`opencode2` 命令，beta）。
实测版本: opencode2 v0.0.0-beta-19059（beta API 可能继续变化）。
"""

import argparse
import glob
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed

PROG = "oc-run2"
DEFAULT_MAX_PARALLEL = 6
MAX_PARALLEL_LIMIT = 6
DEFAULT_TIMEOUT = 900
TESTED_ON = "v0.0.0-beta-19059"

HELP = f"""oc-run2 — 主 Agent 与 opencode2 子 Agent 之间的调度接口
==========================================================

你给出若干"工作区目录 + 提示词"，oc-run2 并行派发给独立子 Agent
（OpenCode 2 beta），完成后返回结构化汇总（每个子 Agent 的 session、
动作次数、tokens、花费、最终报告）。子 Agent 的搜索、读码、思考都在
隔离环境完成，不占你的上下文；也支持 --session 续跑同一子 Agent
（OpenCode 2 原生支持，保持记忆做多轮迭代）。

仅支持 OpenCode 2（`opencode2` 命令）。OpenCode 1.x 请用姊妹工具 oc-run。
实测版本: {TESTED_ON}（beta，server API 可能继续变化）。

用法示例
--------
1) 单个任务（阻塞执行，跑完输出汇总）:
   {PROG} --dir /path/to/project --prompt "分析这个项目的技术栈"

2) 多个任务：工作目录与提示词一一对应（主用法，并行度默认 {DEFAULT_MAX_PARALLEL}、上限 {MAX_PARALLEL_LIMIT}）:
   {PROG} --dir /path/A --prompt "分析项目A" --dir /path/B --prompt "分析项目B"
   只给 1 个提示词则广播到所有目录: {PROG} --dir /path/A --dir /path/B --prompt "..."

3) 批量任务文件（每个任务自定义 dir / prompt / title）:
   {PROG} --tasks tasks.json   # 文件为 [{{"dir": "...", "prompt": "...", "title": "..."}}, ...]

4) 接着某个 session 的上下文继续跑（续跑，OpenCode 2 原生支持）:
   {PROG} --sessions                                      # 查看历史 session（跨所有项目）
   {PROG} --dir /path/A --session ses_xxx --prompt "继续上次的分析"
   说明: 续跑的工作目录语义由 OpenCode 2 决定（跟随 session 所属 project），
   --dir 仅作展示，不影响续跑。

推荐用法
--------
1) token 外包（单轮）——大量读、简洁报:
   派临时 agent 去读海量资料（网页/代码/文档），回报只要简洁结论+来源。
   子 agent 独立上下文，读再多也不占你的上下文；免费档模型成本可忽略。

2) 主从循环（多轮）——强模型指挥弱模型:
   用 --session 续跑同一 agent（保持它的记忆），按每次回报决定下一轮，
   循环直到结果达标。两条铁律:
   - 任务描述要详细：agent 没有你的全局视野，prompt 就是它的世界
   - 回报格式要明确：你只能看到报告/最后发言——回报至少包含
     结论 + 来源 + 不确定性 + 未完成项 + 关键函数或举措

两种用法均可并行（一次派多个，≤{MAX_PARALLEL_LIMIT}）、可异步（借宿主环境如
ZCode / Claude Code 的后台任务机制，完成自动通知）

参数说明
--------
  --dir <path>        工作区目录，可重复指定
  --prompt <text>     提示词，可重复指定，与 --dir 按出现顺序一一对应
                      只给 1 个时广播到所有目录
  --session <id>      续跑指定 session（可重复；按顺序与前几个任务一一配对，
                      数量不能超过任务数；不可与 --tasks 同用）
  --sessions [N]      列出最近 N 个 session（默认 15；传大数如 9999 查全部）
                      后退出，--json 时输出 JSON（数据来自官方 API，跨所有项目）
  --tasks <file>      任务文件（JSON），与 --dir/--prompt 二选一
  --max-parallel N    最大并行数，默认 {DEFAULT_MAX_PARALLEL}，上限 {MAX_PARALLEL_LIMIT}
  --model <m>         指定模型，格式 provider/model（默认用 opencode2 配置）
  --variant <v>       模型推理强度变体，拼为 provider/model#variant（需配合 --model）
  --agent <name>      指定 OpenCode 2 agent（如 build / plan，默认用配置）
  --timeout <sec>     单个任务超时秒数，默认 {DEFAULT_TIMEOUT}
  --json              汇总结果输出为 JSON（否则输出人类可读表格）
  --truncate <n>      人类可读输出中每条结果的最大字符数（默认不截断，
                      输出全文；给 Agent 消费时建议保持全文）

图片 / 文件输入
--------------
  读图或附带文件无需额外参数：把文件路径写进提示词即可
  （如 "读取图片 /path/to/img.png 并描述内容"），子 Agent 会自行读取。

行为说明
--------
- 自动携带 --auto（自动批准权限；OpenCode 2 中替代了 V1 的
  --dangerously-skip-permissions）；只读分析类任务请勿让 agent 修改文件
- 每个任务在 --dir 目录内以子进程方式运行 opencode2 run，
  结束后经官方 API (/api/session/<id>) 补全权威 tokens 与花费
- 单个任务失败（目录不存在 / 超时 / opencode2 报错）不影响其他任务
- 汇总字段: session ID / 动作统计（按工具名）/ 最终文本 / tokens / cost
- 调试: 设置环境变量 OC_RUN2_DEBUG=1 可把每个任务的原始 JSONL 事件流
  保存到系统临时目录，便于事后排查
"""


def parse_args(argv):
    p = argparse.ArgumentParser(add_help=False, prog=PROG)
    p.add_argument("--help", "-h", action="store_true", help="显示帮助")
    p.add_argument("--dir", action="append", default=[], metavar="<path>")
    p.add_argument("--prompt", action="append", default=[], metavar="<text>")
    p.add_argument("--session", action="append", default=[], metavar="<session_id>")
    p.add_argument("--sessions", nargs="?", type=int, const=15, metavar="N",
                   help="列出最近 N 个 session（默认 15）后退出")
    p.add_argument("--tasks", metavar="<file.json>")
    p.add_argument("--max-parallel", type=int, default=DEFAULT_MAX_PARALLEL)
    p.add_argument("--model", metavar="<provider/model>")
    p.add_argument("--variant", metavar="<variant>")
    p.add_argument("--agent", metavar="<name>")
    p.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT)
    p.add_argument("--json", action="store_true")
    p.add_argument("--truncate", type=int, default=None, metavar="<n>",
                   help="人类可读输出中每条结果的最大字符数（默认不截断）")
    return p.parse_args(argv)


def build_tasks(args):
    """把参数展开为任务列表: [{"dir", "prompt", "title"}]"""
    tasks = []
    if args.tasks:
        if args.dir or args.prompt:
            sys.exit("错误: --tasks 与 --dir/--prompt 互斥，请二选一。\n")
        try:
            with open(args.tasks, encoding="utf-8") as f:
                data = json.load(f)
        except FileNotFoundError:
            sys.exit(f"错误: 找不到任务文件: {args.tasks}\n")
        except json.JSONDecodeError as e:
            sys.exit(f"错误: 任务文件不是合法 JSON（{e}）\n")
        raw = data.get("tasks", data) if isinstance(data, dict) else data
        if not isinstance(raw, list):
            sys.exit("错误: 任务文件需是数组，或 {\"tasks\": [...]} 结构。\n")
        for i, t in enumerate(raw):
            if not isinstance(t, dict) or "dir" not in t or "prompt" not in t:
                sys.exit(f"错误: 任务文件第 {i + 1} 项缺少 dir 或 prompt 字段。\n")
            if not (isinstance(t["dir"], str) and isinstance(t["prompt"], str)):
                sys.exit(f"错误: 任务文件第 {i + 1} 项 dir/prompt 需为字符串。\n")
            tasks.append({
                "dir": t["dir"],
                "prompt": t["prompt"],
                "title": str(t.get("title") or f"任务{i + 1}"),
            })
    else:
        if not args.dir:
            sys.exit(HELP + "\n\n错误: 至少需要 --dir 或 --tasks 之一。\n")
        if not args.prompt:
            sys.exit("错误: 需要至少一个 --prompt 提示词。\n")
        n_dir, n_prompt = len(args.dir), len(args.prompt)
        if n_prompt == 1:
            prompts = args.prompt * n_dir  # 单提示词广播到所有目录
        elif n_prompt == n_dir:
            prompts = args.prompt          # 一一对应（主用法）
        else:
            sys.exit(
                f"错误: --dir 有 {n_dir} 个、--prompt 有 {n_prompt} 个，数量不匹配。\n"
                "需一一对应（两者数量相等），或只给 1 个提示词广播到所有目录。\n")
        for d, p in zip(args.dir, prompts):
            tasks.append({
                "dir": d,
                "prompt": p,
                "title": os.path.basename(d.rstrip("/")) or d,
            })
    if args.session:
        if args.tasks:
            sys.exit("错误: --session 与 --tasks 不能同时使用。\n")
        if len(args.session) > len(tasks):
            sys.exit(
                f"错误: --session 有 {len(args.session)} 个、任务只有 {len(tasks)} 个。\n"
                "--session 按顺序与前几个任务配对，数量不能超过任务数。\n")
        for t, sid in zip(tasks, args.session):
            if not sid.startswith("ses_"):
                sys.exit(f"错误: session ID 格式不正确（应以 ses_ 开头）: {sid}\n")
            t["session"] = sid
    return tasks


def parse_events(stdout):
    """解析 opencode2 run --format json 输出的 JSONL 事件流，忽略非 JSON 行"""
    events = []
    for line in stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return events


def summarize_stream(task, stdout, stderr, returncode):
    """从任务的事件流输出中提取汇总字段（V2 事件流）。

    V2 事件类型: step_start / tool_use / text / step_finish
    - tool_use: part.tool 为工具名
    - text:     part.text 为文本片段
    - step_finish: part.tokens = {input, output, reasoning, cache}
                   part.cost 为该步花费（美元）
    """
    events = parse_events(stdout or "")
    session_id = None
    actions = Counter()
    text_parts = []
    tokens_total = 0
    cost_total = 0.0

    for ev in events:
        if not isinstance(ev, dict):
            continue
        if ev.get("sessionID"):
            session_id = session_id or ev["sessionID"]
        etype = ev.get("type")
        part = ev.get("part")
        if not isinstance(part, dict):
            part = {}
        if etype == "tool_use":
            tool = part.get("tool") or "?"
            actions[tool] += 1
        elif etype == "text":
            if part.get("text"):
                text_parts.append(part["text"])
        elif etype == "step_finish":
            tk = part.get("tokens") or {}
            # V2 无 total 字段: input+output+reasoning 求和（cache 为缓存读写，不计）
            tokens_total += sum(
                tk.get(k, 0) or 0 for k in ("input", "output", "reasoning"))
            try:
                cost_total += part.get("cost") or 0.0
            except (TypeError, ValueError):
                pass

    final_text = (text_parts[-1] if text_parts else "").strip()
    if returncode == 0 and session_id:
        status = "ok"
    else:
        status = "failed"

    return {
        "title": task["title"],
        "dir": task["dir"],
        "status": status,
        "session_id": session_id,
        "actions": dict(actions),
        "total_actions": sum(actions.values()),
        "final_result": final_text,
        "tokens": tokens_total,
        "cost": round(cost_total, 6),
        "exit_code": returncode,
        "stderr_tail": (stderr or "").strip()[-500:],
    }


def _extract_data(payload):
    """兼容官方 API 两种返回结构: 裸对象 或 {"location":..., "data":...} 包装"""
    if isinstance(payload, dict) and "data" in payload:
        return payload["data"]
    return payload


def fetch_session_stats(session_id):
    """经官方 API 读取 session 的权威 tokens / cost / outcome。

    任何失败都返回 None（调用方降级用流式求和），绝不抛出。
    """
    try:
        p = subprocess.run(
            ["opencode2", "api", "get", f"/api/session/{session_id}"],
            capture_output=True, text=True, timeout=60)
        if p.returncode != 0:
            return None
        data = _extract_data(json.loads(p.stdout))
        if not isinstance(data, dict) or data.get("_tag"):  # _tag: api 对 404 也 exit 0
            return None
        out = {}
        tk = data.get("tokens") or {}
        total = sum(tk.get(k, 0) or 0 for k in ("input", "output", "reasoning"))
        if total:
            out["tokens"] = total
        if data.get("cost") is not None:
            out["cost"] = round(float(data["cost"]), 6)
        if data.get("outcome"):
            out["outcome"] = data["outcome"]
        return out or None
    except Exception:
        return None


def _task_error(task, status, message):
    """构造失败任务的汇总条目（统一字段结构）"""
    return {
        "title": task["title"], "dir": task["dir"], "status": status,
        "session_id": None, "actions": {}, "total_actions": 0,
        "final_result": message, "tokens": 0, "cost": 0.0,
        "exit_code": None, "stderr_tail": "",
    }


def kill_tree(proc):
    """向进程组发 SIGTERM，连带 opencode2 派生的孙进程"""
    try:
        os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
    except (ProcessLookupError, PermissionError):
        pass


def _debug_dump(task, stdout, stderr):
    """OC_RUN2_DEBUG=1 时把原始输出存到临时目录，便于事后排查"""
    if os.environ.get("OC_RUN2_DEBUG") != "1":
        return
    try:
        d = os.path.join(tempfile.gettempdir(), "oc-run2-debug")
        os.makedirs(d, exist_ok=True)
        safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", task["title"])[:60]
        stamp = time.strftime("%H%M%S")
        with open(os.path.join(d, f"{stamp}-{safe}.stdout.jsonl"), "w",
                  encoding="utf-8") as f:
            f.write(stdout or "")
        if stderr:
            with open(os.path.join(d, f"{stamp}-{safe}.stderr.txt"), "w",
                      encoding="utf-8") as f:
                f.write(stderr)
    except OSError:
        pass


def run_task(task, model, agent, timeout):
    debug = os.environ.get("OC_RUN2_DEBUG") == "1"
    if task.get("session"):
        # 续跑: OpenCode 2 原生支持 run --session（V1 的挂起 bug 已不存在）
        cmd = ["opencode2", "run", "--format", "json", "--auto",
               "--session", task["session"]]
    else:
        if not os.path.isdir(task["dir"]):
            return _task_error(task, "error", f"目录不存在: {task['dir']}")
        cmd = ["opencode2", "run", "--format", "json", "--auto",
               "--title", task["title"]]
    if agent:
        cmd += ["--agent", agent]
    if model:
        cmd += ["--model", model]
    cmd += ["--", task["prompt"]]  # 防止以 - 开头的 prompt 被当成 flag

    # 目录语义由 OpenCode 2 决定: 新任务按 cwd 解析 project/location（可能向上归并）;
    # 续跑跟随 session 所属 project，与 cwd 无关（实测确认），故不传 cwd
    cwd = task["dir"] if not task.get("session") else None

    try:
        # start_new_session: 独立进程组，超时后可按组清理孙进程
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, text=True,
                                errors="replace", start_new_session=True,
                                cwd=cwd)
        try:
            stdout, stderr = proc.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            # 官方推荐模式: kill 后重试 communicate()，不丢已产生的部分输出
            kill_tree(proc)
            stdout, stderr = "", ""
            try:
                stdout, stderr = proc.communicate(timeout=10)
            except Exception:
                pass
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                try:
                    os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
                except (ProcessLookupError, PermissionError):
                    pass
                try:
                    proc.wait(timeout=5)  # SIGKILL 后回收，避免僵尸进程
                except subprocess.TimeoutExpired:
                    pass
            if debug:
                _debug_dump(task, stdout, stderr)
            detail = (stderr or "").strip()[-200:]
            msg = f"超过 {timeout}s 未完成，已终止"
            if detail:
                msg += f"（stderr 末尾: {detail}）"
            entry = _task_error(task, "timeout", msg)
            # 抢救部分输出: 跑满超时的任务通常已建 session、已有真实花费
            partial = summarize_stream(task, stdout, "", 1)
            for k in ("session_id", "tokens", "cost"):
                if partial.get(k):
                    entry[k] = partial[k]
            if entry.get("session_id"):
                stats = fetch_session_stats(entry["session_id"])
                if stats:
                    entry.update(stats)
            return entry
    except FileNotFoundError:
        return _task_error(task, "error",
                           "找不到 opencode2 命令，请先安装 OpenCode 2 beta"
                           " (npm i -g @opencode-ai/cli@beta)")
    except Exception as e:
        # 兜底: 任何异常都不应中断整批任务
        return _task_error(task, "error", f"执行异常: {e}")

    if debug:
        _debug_dump(task, stdout, stderr)
    try:
        summary = summarize_stream(task, stdout, stderr, proc.returncode)
    except Exception as e:
        # beta 字段类型漂移等解析异常: 只废掉单个任务，不炸整批
        return _task_error(task, "error", f"解析输出失败: {e}")
    # 用官方 API 的权威 tokens/cost 修正流式统计（流里末步可能没有 step_finish）
    if summary["session_id"]:
        stats = fetch_session_stats(summary["session_id"])
        if stats:
            summary.update(stats)
    return summary


# ── session 历史（--sessions）──────────────────────────────────────

def format_ts(ms):
    """epoch 毫秒 → 本地时间 MM-DD HH:MM"""
    try:
        return time.strftime("%m-%d %H:%M", time.localtime(ms / 1000))
    except (TypeError, ValueError, OSError, OverflowError):
        return str(ms)


def list_sessions(n):
    """列出最近 n 个 session。

    数据源: 官方 API `opencode2 api get /api/session?limit=N`
    —— 跨所有项目，含 title / 目录 / model / tokens / cost。
    （OpenCode 2 无 `db` 子命令，V1 的 SQLite 直查方案不再适用）
    """
    n = max(0, min(n, 10000))
    p = subprocess.run(
        ["opencode2", "api", "get", f"/api/session?limit={n}"],
        capture_output=True, text=True, timeout=60)
    if p.returncode != 0:
        raise RuntimeError(p.stderr.strip()[-200:] or f"exit {p.returncode}")
    rows = _extract_data(json.loads(p.stdout))
    if not isinstance(rows, list):
        raise RuntimeError(f"API 返回异常: {str(rows)[:200]}")

    items = []
    for r in rows:
        if not isinstance(r, dict):
            continue  # 单行脏数据不毁掉整个列表
        model = r.get("model") or {}
        model_id = "/".join(
            x for x in (model.get("providerID"), model.get("id")) if x) or None
        loc = r.get("location") or {}
        items.append({
            "session_id": r.get("id"),
            "title": r.get("title") or "(无标题)",
            "worktree": loc.get("directory") or r.get("projectID") or "/",
            "updated": format_ts((r.get("time") or {}).get("updated")),
            "model": model_id,
            "tokens": sum(
                (r.get("tokens") or {}).get(k, 0) or 0
                for k in ("input", "output", "reasoning")),
            "cost": r.get("cost"),
        })
    # API 本身按 updated 倒序返回（实测确认）；本地按格式化串重排反而跨年错序
    return items[:n]


def print_sessions(items, as_json=False):
    if as_json:
        print(json.dumps(items, ensure_ascii=False, indent=2))
        return
    print(f"oc-run2 历史 session（最近 {len(items)} 条，跨所有项目）")
    for i, it in enumerate(items, 1):
        model = f" · {it['model']}" if it.get("model") else ""
        cost = it.get("cost")
        cost_s = f" · ${cost:.4f}" if isinstance(cost, (int, float)) else ""
        print(f"  [{i}] {it['session_id']}  {it['title']}{model}{cost_s}")
        print(f"       {it['updated']}  {it['worktree']}  tokens {it['tokens']:,}")
    print()
    print('续跑方法: oc-run2 --dir <目录> --session <session_id> --prompt "继续..."')


def truncate(text, n=200):
    text = " ".join(text.split())
    if n <= 1:  # 非法截断长度：直接返回原文
        return text
    return text if len(text) <= n else text[: n - 1] + "…"


def fmt_cost(c):
    if not isinstance(c, (int, float)):
        return "-"
    return f"${c:.4f}" if c > 0 else "$0"


def print_human(results, workers, truncate_n=None):
    n_ok = sum(1 for r in results if r["status"] == "ok")
    cost_all = sum(r.get("cost") or 0 for r in results)  # 含失败任务的真实花费
    print(f"oc-run2 汇总 · {len(results)} 个任务 · 并行度 {workers} · 成功 {n_ok}/{len(results)}"
          f" · 花费 {fmt_cost(cost_all)}")
    print("─" * 72)
    icons = {"ok": "✅", "failed": "❌", "timeout": "⏱", "error": "⚠️"}
    for i, r in enumerate(results, 1):
        icon = icons.get(r["status"], "·")
        print(f"{icon} [{i}] {r['title']}")
        print(f"    session: {r['session_id'] or '(无)'}")
        acts = " · ".join(f"{k}×{v}" for k, v in sorted(r["actions"].items())) or "(无工具调用)"
        print(f"    动作:   {r['total_actions']} 次 ({acts})")
        print(f"    tokens: {r['tokens']:,}   cost: {fmt_cost(r.get('cost'))}")
        if r["status"] == "ok":
            res = r["final_result"] if not truncate_n else truncate(r["final_result"], truncate_n)
            print(f"    结果:   {res if res else '(无文本输出)'}")
        else:
            detail = r["final_result"] or r["stderr_tail"] or "未知错误"
            print(f"    错误:   {truncate(detail, 160)}")
        print()


def ensure_opencode2():
    """确保 subprocess 能找到 opencode2。

    环境 PATH 精简时（非交互 shell / 脚本 / cron），`which opencode2`
    可能落空；按常见安装路径探测，命中后把所在目录注入 PATH。
    os.path.isfile 会自动过滤悬空软链（目标不存在返回 False）。
    """
    if shutil.which("opencode2"):
        return True
    for pat in (
        "~/.opencode/bin",
        "~/.local/bin",
        "~/.local/share/fnm/node-versions/*/installation/bin",
        "~/.workbuddy/binaries/node/versions/*/bin",
        "~/.bun/bin",
        "/opt/homebrew/bin",
        "/usr/local/bin",
    ):
        for d in glob.glob(os.path.expanduser(pat)):
            cand = os.path.join(d, "opencode2")
            if os.path.isfile(cand) and os.access(cand, os.X_OK):
                os.environ["PATH"] = d + os.pathsep + os.environ.get("PATH", "")
                return True
    return False


def main():
    args = parse_args(sys.argv[1:])
    if args.help:
        print(HELP)
        return 0

    if not ensure_opencode2():
        sys.exit("错误: 未找到 opencode2 命令，请先安装 OpenCode 2 beta"
                 " (npm i -g @opencode-ai/cli@beta)。"
                 "\n提示: OpenCode 1.x 用户请使用姊妹工具 oc-run。")

    if args.variant and not args.model:
        sys.exit("错误: --variant 需与 --model 配合使用（拼为 provider/model#variant）。\n")
    model = f"{args.model}#{args.variant}" if (args.model and args.variant) else args.model

    if args.sessions is not None:
        try:
            items = list_sessions(args.sessions)
        except Exception as e:
            sys.exit(f"错误: 读取 session 历史失败（{e}）。\n"
                     "提示: 可尝试 `opencode2 service status` 检查后台服务。")
        print_sessions(items, as_json=args.json)
        return 0

    tasks = build_tasks(args)
    if not tasks:
        sys.exit("错误: 没有可执行的任务。\n")
    if args.max_parallel < 1:
        sys.exit("错误: --max-parallel 至少为 1。\n")
    if args.max_parallel > MAX_PARALLEL_LIMIT:
        print(f"警告: --max-parallel 超过上限 {MAX_PARALLEL_LIMIT}，已按上限执行", file=sys.stderr)
    if args.timeout < 1:
        sys.exit("错误: --timeout 至少为 1 秒。\n")
    workers = min(args.max_parallel, MAX_PARALLEL_LIMIT, len(tasks))

    t0 = time.time()
    results = [None] * len(tasks)
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futures = {ex.submit(run_task, t, model, args.agent, args.timeout): i
                   for i, t in enumerate(tasks)}
        for fut in as_completed(futures):
            results[futures[fut]] = fut.result()
    elapsed = time.time() - t0

    if args.json:
        print(json.dumps({
            "summary": {
                "total": len(results),
                "parallel": workers,
                "ok": sum(1 for r in results if r["status"] == "ok"),
                "cost": round(sum(r.get("cost") or 0 for r in results), 6),
                "elapsed_sec": round(elapsed, 1),
                "opencode2_version": _opencode2_version(),
            },
            "tasks": results,
        }, ensure_ascii=False, indent=2))
    else:
        print_human(results, workers, args.truncate)
        print(f"总耗时: {elapsed:.1f}s")
    return 0


def _opencode2_version():
    try:
        p = subprocess.run(["opencode2", "--version"], capture_output=True,
                           text=True, timeout=10)
        return (p.stdout or p.stderr).strip().splitlines()[0][:40] if (
            p.stdout or p.stderr).strip() else None
    except Exception:
        return None


if __name__ == "__main__":
    sys.exit(main())
