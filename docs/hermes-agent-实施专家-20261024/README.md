---
file: README.md
description: YYC3 Hermes Agent 生产闭环会话索引与快速恢复指南
author: AI Tutor <Intelligent Application Implementation Expert>
version: v1.1.0
created: 2026-10-24
updated: 2026-11-11
status: active
tags: [index, handoff, production, security]
category: index
---

# YYC3 Hermes Agent · 生产闭环会话（2026-10-24 ~ 11-11）

## 一句话状态

**🌹 生产闭环终点已达成（2026-10-29，6/6 判据，复审 91.3）· 维护态运转中**：线上 5/5 安全头 + DCDN + 分片目录、测试全量归零、`yyc3-maintenance.sh`（launchd 周一 09:07 已实装验证 7/7）一键维护。**当前唯一事实源 = [09-状态压缩与生产就绪终评.md](./09-状态压缩与生产就绪终评.md)**；上游策略 = 0.21.3 基线 + 定点 backport（[08 干跑](./08-上游0231整树切换干跑报告.md)实测确认，下一评估点 v0.24.0）。

## 文档导航

| 文件 | 内容 | 状态 |
| --- | --- | --- |
| **[09-状态压缩与生产就绪终评.md](./09-状态压缩与生产就绪终评.md)** | **压缩事实源：状态 + 不足项 G1-G8 + 生产分析 + 封装流程** | **当前入口** |
| [08-上游0231整树切换干跑报告.md](./08-上游0231整树切换干跑报告.md) | 0.23.1 干跑实测（84∩/61 冲突/人工≈13-23）+ 决策维持 (a) + G8 | v1.0 |
| [00-生产闭环终极审核与演进建议报告.md](./00-生产闭环终极审核与演进建议报告.md) | 初审 + 复核 + P0/P1 执行 + 对标 + 路线（含 v1.6.1 终点记录） | v1.6.1 |
| [01-任务规划与节点目标.md](./01-任务规划与节点目标.md) | 阶段目标、任务分解、验收标准、里程碑 | 已更新 |
| [02-执行日志与进度跟踪.md](./02-执行日志与进度跟踪.md) | 逐项操作日志、验证证据、失败归因 | 实时 |
| [03-总结文档与状态同步.md](./03-总结文档与状态同步.md) | 收尾总结、关键决策、恢复指南 | 已完成 |
| [04-P0-5线上安全头执行手册.md](./04-P0-5线上安全头执行手册.md) | 方案 B（DCDN）执行手册 + TXT 验证记录 | ✅ 已闭环 |
| [05-下一阶段衔接与演进规划.md](./05-下一阶段衔接与演进规划.md) | M4→M8 规划 + 终点判据计分板（6/6） | 已闭环 |
| [06-同类对标与M6闭环演进报告.md](./06-同类对标与M6闭环演进报告.md) | M6 闭环全网对标（10-29 数据）+ 行业信号 | v1.0 |
| [07-上游022结构重构评估.md](./07-上游022结构重构评估.md) | 0.22 冲突面实测 + 合并决策（缓议 + 0.23.0 触发干跑） | v1.0 |
| [logs/](./logs/) | 机器可读执行日志 + `maintenance-*.md` 维护归档 + `dryrun-0231/` 干跑原始清单 | 持续 |

## 当前基线（2026-11-11 巡检）

| 项 | 值 |
| --- | --- |
| 代码版本 | `0.21.3` 基线 + 定点 backport（上游策略见 08：维持 (a)，下一评估点 **v0.24.0**） |
| 上游 | `v0.23.1`（2026-11-10；滚装节奏 ~5 天/版，main 领先 2.5k commits/5 天） |
| 线上站点 | `h-agent.yyc3.vip` → DCDN → Pages；**5/5 安全头**；LE 证书余 77 天（≤35 天自动续期+重传，launchd 周巡检） |
| 维护入口 | `bash scripts/yyc3-maintenance.sh`；launchd `com.yyc3.hermes-maintenance`（周一 09:07，kickstart 实测 **7/7 PASS**） |
| 测试门禁 | preflight 8 关 ALL PASS（11s）；OSV critical-high = **0**（oauthlib 4.0.1 / pyasn1 0.6.5 已于 11-09 修复） |
| 运行时 venv | `~/.hermes/hermes-agent/venv`（canonical；仓库 .venv 不保留） |
| Python / uv / rg | 3.11.14 / 0.13.5 / 15.2.0 |
| 自动化变更 | **分支 + PR（禁直推 main）**；PR #22 已 rebase-merge（5 commits） |

## 快速恢复命令

```bash
cd /Users/yanyu/YYC-Cube/personal/YYC3-Hermes-Agent

# 1) 一键维护（门禁 + 证书巡检 + 线上验收 + 周报 + 归档）
bash scripts/yyc3-maintenance.sh            # --quick 可选

# 2) 安全定向测试（canonical runner）
scripts/run_tests.sh tests/hermes_cli/test_dashboard_auth_body_limit.py \
  tests/hermes_cli/test_dashboard_auth_audit.py

# 3) 线上安全头现状
curl -sS -I https://h-agent.yyc3.vip/ | grep -Ei \
  "strict-transport|x-frame|x-content-type|referrer-policy|permissions-policy"

# 4) launchd 手动触发 / 状态
launchctl kickstart -k gui/$(id -u)/com.yyc3.hermes-maintenance
tail -20 ~/Library/Logs/yyc3-maintenance.log
```

## 下次优先 TOP 3

1. **backport 候选评估**（08 §4-3，方案 (a) 渠道）：上游 0.23.0 安全区 4 项——secret 掩码扩展 / 审批门强化 / 网络边界 / shell-hook consent，逐项走分支+PR。
2. **v0.24.0 重新干跑**：`scripts/dryrun-0231.sh` 改两个变量即可复用（0.24.0 承诺完整 curated notes = 下一稳定锚）。
3. **维护态巡检**：launchd 周报驱动；证书 ≤35 天自动续期；G2 cron 兜底已就位。

## 绝对不要做

- 不要在 venv 里执行 `pip install -e '.[all]'`：该 venv 没有 pip，会落到 conda pip 污染 base。统一 `uv sync --extra all --locked`。
- 不要直推 main；自动化变更一律分支 + PR（AGENTS.md 新规）。
- 不要整树 merge/rebase 上游：08 报告实测维持方案 (a)；切换（若未来执行）必须先临时应用 `.gitattributes merge=ours` 政策并在合并后移除（常驻会毒化日常 PR 的 lockfile 合并）。
- 不要把仓库 `.venv` 留在树外提交范围：canonical 环境是 `~/.hermes/hermes-agent/venv`。
