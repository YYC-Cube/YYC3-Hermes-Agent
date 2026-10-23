---
file: README.md
description: YYC3 Hermes Agent 生产闭环会话索引与快速恢复指南
author: AI Tutor <Intelligent Application Implementation Expert>
version: v1.0.0
created: 2026-10-24
updated: 2026-10-24
status: active
tags: [index, handoff, production, security]
category: index
---

# YYC3 Hermes Agent · 生产闭环会话（2026-10-24）

## 一句话状态

P0-1/2/3（运行时、uv、brotli）与 P0-4（4 个 Dashboard 认证安全 backport）已完成；P1（ripgrep、技能索引拆分、doctor 建议）已完成；**P0-5 线上安全头仍待 Cloudflare 权限**。

## 文档导航

| 文件 | 内容 | 状态 |
| --- | --- | --- |
| [00-生产闭环终极审核与演进建议报告.md](./00-生产闭环终极审核与演进建议报告.md) | 初审 + 复核更正 + P0/P1 执行记录 + 对标 + 路线 | v1.2 |
| [01-任务规划与节点目标.md](./01-任务规划与节点目标.md) | 阶段目标、任务分解、验收标准、里程碑 | 已更新 |
| [02-执行日志与进度跟踪.md](./02-执行日志与进度跟踪.md) | 本次会话逐项操作日志、验证证据、失败归因 | 实时 |
| [03-总结文档与状态同步.md](./03-总结文档与状态同步.md) | 收尾总结、关键决策、下次会话恢复指南 | 已完成 |
| [04-P0-5线上安全头执行手册.md](./04-P0-5线上安全头执行手册.md) | Cloudflare 代理、Transform Rules、验收与回滚 | 待执行 |
| [logs/20261024-execution.jsonl](./logs/20261024-execution.jsonl) | 机器可读执行日志（一行一个事件） | 已完成 |

## 当前基线（2026-10-24 04:18 CST）

| 项 | 值 |
| --- | --- |
| 代码版本 | `0.21.3`，本地 git `bfe1ae96` |
| 上游 | `v0.22.5`（2026-10-23） |
| 运行时 venv | `~/.hermes/hermes-agent/venv`，**109 包 / 0 版本偏差 / 0 OSV** |
| uv | **0.13.5**（CI 口径 0.9.28 已验证可解析新锁） |
| ripgrep | **15.2.0**（CI 固定 15.1.0） |
| Python | 3.11.14 |
| 锁文件 | 259 包 / **0 OSV**（brotlicffi 已升 1.2.1.0） |
| 技能目录 | core **1.6 MB / 2,285 技能**；ClawHub 45 MB、skills.sh 9.5 MB 按需加载 |
| 测试基线 | `tests/tools` **10,022 通过 / 37 失败 / 143 跳过**；18 搜索类在隔离运行 **49/49 通过**（并发隔离） |
| 站点构建 | `npm run build` 成功；`skills-index.json` 已移出发布物 |
| 公开站点 | `h-agent.yyc3.vip` → `yyc-cube.github.io`，无 CDN；HSTS/XFO/XCTO 仍缺 |

## 快速恢复命令

```bash
cd /Users/yanyu/YYC-Cube/YYC3-Hermes-Agent

# 1) 运行时一致性
source ~/.hermes/hermes-agent/venv/bin/activate
uv sync --locked --active --extra all --extra dev
python - <<'PY'
import importlib.metadata as m
for p in ("cryptography","PyJWT","aiohttp","certifi","urllib3","requests","mcp"):
    print(p, m.version(p))
PY

# 2) 安全定向测试
scripts/run_tests.sh tests/hermes_cli/test_dashboard_auth_body_limit.py \
  tests/hermes_cli/test_dashboard_auth_audit.py \
  tests/hermes_cli/test_dashboard_auth_password_login.py \
  tests/hermes_cli/test_dashboard_auth_native_flow.py

# 3) 站点构建与技能分片
cd website && npm run build && ls -lh build/api | sort -k5 -h | tail -6

# 4) 线上安全头现状
curl -sS -I https://h-agent.yyc3.vip/ | grep -Ei \
  "strict-transport|content-security|x-frame|x-content-type|referrer-policy|permissions-policy"
```

## 下次优先 TOP 3

1. **P0-5**：在 Cloudflare 开启代理并应用 [00 报告附录 C](./00-生产闭环终极审核与演进建议报告.md) 的 Transform Rules；验收 `curl -I` 可见 5 类头。
2. **P1**：补 SBOM（CycloneDX）与发布来源证明；把 `ty` 变更文件设为阻塞。
3. **P2**：评估上游 0.22 结构重构（1.06M→698K 行），先做 0.21.7 安全补丁对齐。

## 绝对不要做

- 不要在 venv 里执行 `pip install -e '.[all]'`：该 venv 没有 pip，会落到 conda pip，污染 base 环境。统一用 `uv sync --locked`。
- 不要把 `website/static/api/skills-index.json` 放回发布目录；它已改为 `website/.cache/` 构建输入。
- 不要直接把上游 0.22 rebase 到本分支；先走 0.21.7 安全补丁，再评估分阶段合并。
