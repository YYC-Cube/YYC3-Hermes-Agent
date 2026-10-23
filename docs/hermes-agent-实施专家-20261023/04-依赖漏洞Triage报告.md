---
file: 04-依赖漏洞Triage报告.md
description: YYC3 Hermes Agent 依赖漏洞分级、影响面与修复批次
author: YYC³ Team <admin@0379.email>
version: v1.0.0
created: 2026-10-23
updated: 2026-10-23
status: active
tags: [security, dependencies, triage]
category: report
---

<p align="center">
  <img src="../../website/static/img/yyc3-family.png" alt="YYC³ Family" />
</p>

> ***YanYuCloudCube***
> *言启象限 | 语枢未来*
> ***Words Initiate Quadrants, Language Serves as Core for Future***
> *万象归元于云枢 | 深栈智启新纪元*
> ***All things converge in cloud pivot; Deep stacks ignite a new era of intelligence***

# 依赖漏洞 Triage 报告

## 一、结论摘要

1. **328 条告警不等于 328 个独立漏洞**：按 package + manifest + advisory 去重后，critical 集中在 **10 个包**。
2. **npm 侧：源码仓锁文件过期，但运行时锁文件已修复**。运行时已使用 `dompurify 3.4.17`、`simple-git 4.0.2`、`vite 8.2.4`、`undici 7.30.0` 等修复版本；新仓库提交的是 0.21.3 旧锁文件。
3. **Python 侧：真实运行环境仍然脆弱**。`venv` 中 `certifi 2026.5.20`、`PyJWT 2.13.0`、`Pillow 12.2.0`、`anyio 4.12.1`、`aiohttp 3.14.1`、`urllib3 2.7.0` 均低于修复版本。
4. **额外发现：运行环境与锁文件漂移**。`pyproject.toml` 要求 `cryptography==50.0.0`，实际 venv 为 `46.0.7`；`Pillow` 锁为 12.3.0，实际为 12.2.0。
5. 建议顺序：**同步 npm 锁 → 修 Python runtime → 处理 Electron / simple-git 大版本 → 清理 dev-only**。

## 二、数据来源与方法

| 项 | 说明 |
| --- | --- |
| 数据源 | GitHub Dependabot Alerts（`state=open`） |
| 采集时间 | 2026-10-23 |
| 告警数 | 328 条 |
| 生态 | npm 203，pip 125 |
| 作用域 | runtime 226，development 102 |
| 说明 | `npm audit` 因 registry / 代理返回错误，本次以 Dependabot 为准 |

### 严重度分布

| 严重度 | 数量 |
| --- | ---: |
| critical | 23 |
| high | 142 |
| medium | 125 |
| low | 38 |

### 受影响清单（Top）

| 条数 | Manifest |
| ---: | --- |
| 97 | `package-lock.json` |
| 85 | `uv.lock` |
| 43 | `website/package-lock.json` |
| 40 | `pyproject.toml` |
| 29 | `apps/desktop/package.json` |
| 12 | `plugins/platforms/photon/sidecar/package-lock.json` |
| 7 | `web/package.json` |
| 7 | `apps/bootstrap-installer/package.json` |
| 4 | `ui-tui/package.json` |
| 3 | `scripts/whatsapp-bridge/package-lock.json` |

## 三、Critical 清单（10 个包）

| 包 | 生态 | 源码仓 | 运行时 | 修复版本 | 作用域 | 处理建议 |
| --- | --- | --- | --- | --- | --- | --- |
| Pillow | pip | 12.3.0 | 12.2.0 | 13.0.0 | runtime | 升 13，回归视觉/图片工具 |
| PyJWT | pip | 2.13.0 | 2.13.0 | 2.14.0 | runtime | 直接升，回归认证 |
| certifi | pip | 2026.5.20 | 2026.5.20 | 2026.10.19 | runtime | 直接升，回归 TLS |
| anyio | pip | 4.12.1 | 4.12.1 | 4.14.2 | runtime | 锁文件升级，回归异步调用 |
| dompurify | npm | 3.4.13 | 3.4.17 | 3.4.17 | runtime | 同步运行时锁 |
| shell-quote | npm | 1.9.0 | 1.12.0 | 1.11.0 | runtime/dev | 同步运行时锁 |
| proxy-addr | npm | 2.0.7（website） | 2.0.8 | 2.0.8 | runtime | 同步 website 锁 |
| tinypool | npm | 1.1.1（website） | 2.2.0 | 2.1.2 | development | 随 vitest 升级 |
| simple-git | npm | 3.36.0 | 4.0.2 | 4.0.1 | runtime（Desktop） | 大版本，回归 Git Review |
| @simple-git/argv-parser | npm | 1.1.1 | 2.0.1 | 2.0.1 | runtime（Desktop） | 随 simple-git 4 升级 |

## 四、High 热点

| 包 | 条数 | 源码仓 | 运行时 | 修复版本 | 影响面 |
| --- | ---: | --- | --- | --- | --- |
| Pillow | 46 | 12.3.0 | 12.2.0 | 13.0.0 | 图片解析、视觉工具 |
| @xmldom/xmldom | 14 | 0.8.13 | 0.8.15 | 0.9.12 | Docusaurus 构建链 |
| electron | 10 | 40.10.2 | 40.10.2 | 41.10.6 | Desktop 主进程 |
| fast-uri | 10 | 3.1.5 | 3.1.8 | 3.1.8 | 构建链 / URL 解析 |
| undici | 5 | 7.29.0 | 7.30.0 | 7.29.1 | HTTP 客户端 |
| vite | 4 | 8.2.0 | 8.2.4 | 8.2.4 | 开发服务器 / 构建 |
| PyJWT | 6 | 2.13.0 | 2.13.0 | 2.14.0 | 认证 |
| simple-git | 4 | 3.36.0 | 4.0.2 | 4.0.0 | Desktop Git 操作 |
| axios | 4 | 1.18.1 | 1.20.0 | 1.20.0 | 构建 / 脚本 |
| browserslist | 3 | — | — | 4.28.7 | 构建链 |
| aiohttp | 3 | 3.14.3 | 3.14.1 | 3.14.4 | 消息网关 |
| urllib3 | 2 | 2.7.0 | 2.7.0 | 2.8.0 | HTTP / TLS |
| tornado | 2 | 6.5.8 | 未安装 | 6.5.9 | 可选 extras |
| httpx2 | 2 | 2.7.0 | 未安装 | 2.12.0 | MCP / dev |
| joi | 1 | 18.2.3 | 18.2.9 | 17.13.8 / 18.2.9 | 构建链 |

## 五、额外发现：运行时漂移

| 包 | `pyproject.toml` 要求 | `uv.lock` | 实际 venv | 风险 |
| --- | --- | --- | --- | --- |
| cryptography | `==50.0.0` | 50.0.0 | **46.0.7** | 加密、WeCom、TLS |
| Pillow | `==12.3.0` | 12.3.0 | **12.2.0** | 图片解析 |
| aiohttp | `==3.14.3` | 3.14.3 | **3.14.1** | 消息渠道 |
| certifi | `==2026.5.20` | 2026.5.20 | 2026.5.20 | 证书校验 |
| PyJWT | `==2.13.0` | 2.13.0 | 2.13.0 | 认证 |
| anyio | 未直接 pin | 4.12.1 | 4.12.1 | 异步运行时 |

结论：**当前 venv 不是由最新锁文件构建的**。修复依赖前必须先确认 venv 来源，否则改了锁文件也不会影响真实运行。

## 六、修复批次

### Batch A（P0，低风险）：同步 npm 锁

- 目标：关闭 dompurify / shell-quote / proxy-addr / fast-uri / undici / axios / joi / @xmldom / vite / tinypool 告警
- 方式：以运行时锁为基线，按包定向更新；不要手改 `package-lock.json`
- 验证：`npm ci`（root、website、desktop）、`npm run typecheck && npm test && npm run build`
- 风险：低；仅锁文件与补丁版本

### Batch B（P0，中风险）：Python runtime

- 变更：`certifi==2026.10.19`、`PyJWT[crypto]==2.14.0`、`Pillow==13.0.0`、`aiohttp==3.14.4`、`urllib3>=2.8.0,<3`、`httpx2==2.12.0`，并让 `anyio>=4.14.2`
- 步骤：改 `pyproject.toml` → `uv lock` → 重建 venv / `hermes pm repair`
- 验证：`hermes doctor`、认证回归、视觉工具回归、网关消息回归、`scripts/run_tests.sh`
- 风险：Pillow 13 有 API 变更；cryptography 46→50 可能影响加密渠道

### Batch C（P1，大版本）：Desktop 运行时

- `electron@41.10.6`（40 → 41）
- `simple-git@4.0.2` + `@simple-git/argv-parser@2.0.1`
- `tinypool@2.2.0`（随 vitest）
- 验证：Desktop `typecheck`、`test`、`build`、启动、Git Review、终端、原生模块
- 风险：Electron ABI、native modules（node-pty / get-windows）、simple-git 4 API

### Batch D（P2）：dev-only

- @xmldom/xmldom、joi、launch-editor、browserslist 等
- 仅在 A/B/C 完成后处理；不阻塞 runtime 安全

## 七、执行约束

1. 禁止 `npm audit fix --force` 或整体大版本升级。
2. Python 依赖保持精确 pin；改 `pyproject.toml` 后必须 `uv lock`。
3. 每批单独提交，提交前跑 T12 回滚演练中的验证步骤。
4. Electron / simple-git 升级必须做 Desktop 启动与 Git Review 实测。
5. 推送后重新查看 Dependabot，确认 critical 归零。
6. 不修改 `pm/downloader.py` 的本地 400 回退补丁（T13 单独处理）。

## 八、验收标准

| 指标 | 目标 |
| --- | --- |
| critical 告警 | 0 |
| high（runtime） | 0 |
| high（development） | 有明确排期 |
| `hermes doctor` | 通过 |
| 本地 one-shot | 返回 `OK` |
| Desktop build | 通过 |
| 回滚路径 | T12 手册可用 |

## 九、下一步

1. **Batch A**：同步 npm 锁，预计关闭大部分 npm critical/high。
2. **Batch B**：更新 Python 依赖并重建 venv，关闭全部 pip critical。
3. **Batch C**：Electron 41 与 simple-git 4 专项回归。
4. **Batch D**：dev-only 清理。

## 十、执行记录（Batch A）

2026-10-23 已完成 Batch A：

- 直接依赖：`dompurify 3.4.17`、`vite 8.2.4`、`ui-tui undici 6.28.1`
- 根 overrides：`shell-quote 1.12.0`、`fast-uri 3.1.8`、`axios 1.20.0`、`joi 18.2.9`、`@xmldom/xmldom 0.8.15 / 0.9.12`、`ip-address 10.7.4`、`js-yaml 4.3.2`、`undici 7.30.0 / 6.28.1`、`brace-expansion 5.0.11`、`dompurify 3.4.17`
- website overrides：`shell-quote 1.12.0`、`proxy-addr 2.0.8`、`fast-uri 3.1.8`、`joi 17.13.8`、`dompurify 3.4.17`、`nanoid 3.3.18`、`js-yaml 4.3.2`
- photon sidecar：`undici 7.30.0`
- 锁文件：根锁重新生成，website / photon 定点更新
- 验证：`npm ci` ×3、`npm ls`、Desktop typecheck + vitest + build、website build、ui-tui typecheck、web build、photon syntax check

未执行：`tinypool 2`（并入 Batch C）、`simple-git 4` / `Electron 41`（Batch C）、Python runtime（Batch B）、dev-only（Batch D）。

## 十一、执行记录（Batch B）

2026-10-23 已完成 Batch B：

- **运行时已修复**：活动环境为 Python 3.14.7 pm 环境，实际版本 `certifi 2026.10.19`、`PyJWT 2.15.1`、`Pillow 13.0.0`、`anyio 4.14.2`、`aiohttp 3.14.5`、`urllib3 2.8.0`、`httpx2 2.12.0`、`cryptography 50.0.1`；旧 3.11 `venv/` 不参与启动。
- **源码 pyproject**：`certifi 2026.10.19`、`PyJWT 2.15.1`、`Pillow 13.0.0`、`aiohttp 3.14.5`、`urllib3 >=2.8.0,<3`、`httpx2 2.12.0`、`cryptography 50.0.1`。
- **锁文件**：使用运行时 uv 0.12.3 重新 `uv lock`，结果 `aiohttp 3.14.5`、`anyio 4.14.2`、`certifi 2026.10.19`、`cryptography 50.0.2`、`httpx2 2.12.0`、`pillow 13.0.0`、`pyjwt 2.15.1`、`tornado 6.5.10`、`urllib3 2.8.0`。
- **验证**：`uv lock --check` 通过；`hermes doctor` 正常；本地 one-shot 返回 `OK`。
- **未重建 venv**：活动 pm 环境已满足，重建无收益；遗留 3.11 venv 见 R13。
- **推送后告警**：328 → 211（npm 关闭 117 条）；Python 清单的 `updated_at` 尚未变化，等待 GitHub 重新扫描。

## 十二、执行记录（Batch C）

2026-10-23 已完成 Batch C：

- **Electron**：`40.10.2 → 41.10.6`；`electron --version` 返回 `v41.10.6`；Desktop build 与 `node-pty` 加载通过。
- **simple-git**：`3.36.0 → 4.0.2`；新增 `@simple-git/argv-parser 2.0.1`；回移运行时已适配的 `git-review-ops.ts` 与 `no-console-git.ts`；`git-review-ops.test.ts` 9 passed。
- **tinypool**：website `1.1.1 → 2.2.0`；website build 通过。
- **验证**：Desktop typecheck/build、lint 0 errors；全量 vitest 10708 passed，4 个既有/环境失败（voice-prefs 断言、managed-ssh exit 127、pool-spawn 5s 超时）。
- **告警**：211 → **94**（5 critical / 36 high）；剩余 5 条 critical 为 simple-git / argv-parser / tinypool 旧告警，等待 npm 清单重扫。

## 十三、执行记录（Batch D）

2026-10-23 已完成 Batch D（dev-only 与边缘运行时）：

| 包 | 范围 | 变更 | 方式 |
| --- | --- | --- | --- |
| follow-redirects | 根 / website | 1.16.0 → 1.16.1 | override + npm 解析 |
| browserslist | 根 / website | 4.28.6 → 4.28.7 | override + npm 解析 |
| baseline-browser-mapping | 根 / website | 2.10.43 → 2.11.28 | browserslist 连带 |
| electron-to-chromium | website | 1.5.392 → 1.5.451 | browserslist 连带 |
| source-map-js | 根 / website | 1.2.1 → 1.2.2 | override + npm 解析 |
| brace-expansion | 根 / website | 5.0.9（website）/ 5.0.11（根）→ 5.0.12 | override + npm 解析 |
| launch-editor | website | 2.14.1 → 2.14.2 | override + npm 解析 |
| compression | website | 1.8.1 → 1.8.2 | override + npm 解析 |
| svgo | website | 3.3.4 → 3.3.5 | override + npm 解析 |
| @grpc/grpc-js | photon sidecar | 1.14.4 → 1.14.5 | override + npm 解析 |
| sharp | whatsapp-bridge | 0.35.4 → 0.35.5 | override + npm 解析（24 个 `@img/*` 平台包同步；libvips 1.3.3 → 1.3.4） |
| fsspec | Python 锁 | 2026.2.0 → 2026.9.0 | `uv lock --upgrade-package fsspec` |

- **锁文件**：四套 npm 锁（根 / website / photon / whatsapp-bridge）均由 npm 解析更新，无手工 patch；`uv.lock` 仅 fsspec 一条变更。
- **验证**：四个 npm 工程 `npm ci --dry-run` 通过；website、photon、whatsapp-bridge 实际 `npm ci` 通过并安装到目标版本；根 `npm ci` 干净安装通过，Electron 41.10.6 二进制完好。
- **构建**：website `typecheck` 0 errors、`build:fast` 成功；Desktop `typecheck` 通过；photon `index.mjs` 与 whatsapp `bridge.js` `node --check` 通过。
- **顺带修复**：website 类型门禁在 TS 6 下已失效（`baseUrl` 弃用、`JSX` 命名空间缺失、JSON 模块未启用）。已在 `website/tsconfig.json` 补 `baseUrl` / `ignoreDeprecations` / `resolveJsonModule`，并在两个组件补 `import type { JSX } from 'react'`。
- **无修复版本（接受风险，均 dev-only 或构建期）**：`http-cache-semantics 4.2.0`、`@electron-internal/extract-zip 1.0.5`、`braces 3.0.3`。不作为运行时依赖，等待上游发布修复或随大版本自然消解。
- **告警**：代码侧已无 Batch D 目标；最终计数以 GitHub Dependabot 重扫为准（npm 清单重扫存在延迟）。

## 十四、执行记录（Batch E）

2026-10-23 已完成 Batch E（medium/low 收尾）：

| 包 | 范围 | 变更 | 方式 |
| --- | --- | --- | --- |
| sanitize-html | 根 runtime | 2.17.6 → 2.18.0 | override + npm 解析 |
| colord | 根 / website | 2.9.3 → 2.9.4 | override + npm 解析 |
| postcss | 根 | 8.5.23 → 8.5.31 | override（满足 sanitize-html 2.18 的 `^8.5.27`） |
| qs | website | 6.15.3 → 6.16.0 | override + npm 解析 |
| postcss-selector-parser | website | 6.1.4 / 7.1.4 → 7.1.6 | override + npm 解析（嵌套条目合并） |
| music-metadata | whatsapp-bridge | 11.15.0 → 11.16.0 | override + npm 解析 |
| vitest | 根 / web / desktop / ui-tui / tests-js | 4.1.10 → 4.1.12 | devDependency 统一 |
| @vitest/mocker | 根 | 4.1.10 → 4.1.12 | override |
| h2 | Python 锁 | 4.3.0 → 4.4.1 | `uv lock --upgrade-package` |
| hpack | Python 锁 | 4.1.0 → 4.2.0 | `uv lock --upgrade-package` |
| multidict | Python 锁 | 6.7.1 → 6.9.1 | `uv lock --upgrade-package multidict==6.9.1`（不取 7.0 大版本） |

- **npm 冷却门禁**：上述包多为近 14 天发布，已在 `.npmrc` 按既有惯例加入 `min-release-age-exclude`（sanitize-html、qs、postcss-selector-parser、music-metadata、vitest、`@vitest/*`），并注明满两周后移除。
- **锁文件**：根 / website / whatsapp-bridge 三套 npm 锁更新；`uv.lock` 仅 h2 / hpack / multidict 三条。
- **验证**：根、website、whatsapp-bridge `npm ci` 通过；根 `npm ls` 全部 deduped、无 invalid；Desktop 与 web `typecheck` 通过；ui-tui `typecheck` 通过；website `typecheck` + `build:fast` 通过；whatsapp `node --check` 通过；`uv lock --check` 通过。
- **测试**：web vitest 49 文件 / 346 tests 全通过；Desktop UI 908 文件 / 8349 tests，2 条既有 voice-prefs 断言失败；Desktop platform 208 文件 / 2383 tests，2 条既有失败（managed-ssh exit 127、pool-spawn 5s 超时）。与 Batch C 基线一致，无新增失败。
- **运行时**：pm 环境未安装 h2 / hpack / multidict（可选依赖未启用），不存在运行时暴露。
- **暂缓项（风险或 pin 约束）**：
  - `katex 0.16.47 → 0.18.2`：4 条 low；所有依赖方声明 `^0.16`，跨两个 minor 强推有渲染回归风险，保留观察。
  - `oauthlib 3.3.1 → 4.0.0`：medium；主版本升级影响 google-auth-oauthlib 授权链，需专项回归后再动。
  - `mcp 2.0.0 → 2.2.0`：medium；`pyproject.toml` 明确 pin 2.0.0（MCP revision 2026-07-28 兼容性），不随告警盲升。
  - `opentelemetry-api 1.39.1 → 1.45.1`：medium；与 `opentelemetry-sdk==1.39.1` 版本绑定，单独升级会破坏 OTLP extra。
  - `electron 42.11.x`：medium ×10 / low ×6；Batch C 刚完成 40 → 41，暂不做第二次大版本跳跃。

### Batch E 后残留

| 包 | 告警 | 处置 |
| --- | --- | --- |
| katex | low ×4 | 观察（上游 semver 未跟上） |
| oauthlib / mcp / opentelemetry-api | medium ×4 | 需专项回归或等待上游约束放宽 |
| electron | medium ×10 / low ×6 | 暂缓至 Electron 42 专项 |
| http-cache-semantics / extract-zip / braces | high / high / high | 无修复版本，接受风险 |

> Batch A/B/C/D/E 均已完成；Dependabot 重扫 94 → **71**（0 critical / 20 high / 40 medium / 11 low）。代码侧可修项已清零，剩余为暂缓项与无修复版本。
