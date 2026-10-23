# YYC³ 团队 HTML 版本设计指导文档 · 兼标准生成提示词

> **版本**: v2.0（由 v1.0「项目展示站点生成提示词」升级而来）
> **蓝本**: `DGX-SPARK-HUB-OFFLINE.html`（双语增强版）+ `YYC3-PORTFOLIO-HUB-OFFLINE.html`（93 项目全景站实证）
> **定位**: **YYC³（YanYuCloudCube™）团队 HTML 版本设计的统一指导文档** —— 既是团队开发规范（人类查阅），也是标准生成提示词（AI 投喂），双轨共用
> **配套规范**: [YYC3-HTML-设计指导文档.md](YYC3-HTML-设计指导文档.md)（家族设计系统基线）
> **实证基线**: 2026-08 全景站交付 —— 93 项目 × 6 级分析、jsdom 真实解析验收、`<!--` 注释污染事故复盘
> **硬性约束**: 第二章核心规格（功能/模块/组件/交互/双语）**不可缩减**；第三章高级组件库为**可调取选装**，按项目需要选用，但一经选用同样纳入验收

---

## 使用说明（双轨用法）

### 轨道一 · 团队开发规范（人类查阅）

1. **新成员入门**：读第一章契约 → 第二章核心规格（M1–M8 / 16 交互 / i18n）→ 4.x 安全规范 → 附录 A 验收清单
2. **日常开发**：改数据不改代码（数据驱动铁律）；新界面文案走 `I18N` 双语词典；外源文本一律 `escHtml()`（见 4.1）
3. **组件选型**：需要高级能力（命令面板/图表/虚拟滚动等）时从**第三章组件库**按需调取，遵守每项标注的离线可用性与降级要求

### 轨道二 · 标准生成提示词（AI 投喂）

```
输出站点 = 【第二章提示词正文】 + 【第三章选装组件清单（可选）】 + 【附录 B 槽位表】 + 【项目数据】
```

1. 填附录 B 槽位表；若需高级能力，从第三章勾选组件一并投喂
2. AI 产出后**必须**跑附录 A 验收清单（含 A7 真实解析器渲染验收）
3. `cp {产品名}-HUB-OFFLINE.html index.html` → push main 自动部署

### 命名规范（家族统一）

| 产物 | 命名 |
| ------ | ------ |
| 数据源 / 离线版 | `{产品名}-HUB-OFFLINE.html`（可直接双击运行） |
| 部署入口 | `index.html`（由数据源逐字节复制，SHA 必须一致） |
| 仓库 | `YYC-Cube/{项目名}`，push main 自动部署 |

---

# 第一章 · 设计契约（开发/生成前必读）

1. **不可缩减**：第二章所列全部功能 / 模块 / 组件 / 键位 / 断点 / 验收项，缺一即为不合格交付
2. **单文件铁律**：CSS / HTML / JS / 数据 / 双语词典全部内联一个 `.html`，零 CDN、零构建、零框架、零网络请求（第三章选装组件同样必须满足此条或按标注降级）
3. **蓝本同构**：结构、类名、交互与蓝本保持一致；仅槽位参数与项目数据可变
4. **数据驱动**：HTML 只写骨架，内容由 `GUIDES` / `SKILLS` 数组渲染；改数据不改代码
5. **安全默认**：一切进入 `innerHTML` 的**外源文本必须 `escHtml()`**；数据生成侧同步清洗（见 4.1，源自真实事故）
6. **交付即验证**：附录 A 全项通过并在交付说明中报告结果

---

# 第二章 · 核心规格（提示词正文 · 不可缩减）

> ↓↓↓ 复制投喂 AI（或作为团队开发核心规范）↓↓↓

## 0. 角色与使命

你是 YYC³（YanYuCloudCube™）的前端工程师。请生成一个**单文件零依赖离线可用**的「操作中心」站点，技术栈为原生 HTML + CSS + JavaScript（ES6 模板字符串可用，禁止框架/CDN/npm）。以 DGX Spark 操作中心为蓝本：**暗色优先、数据驱动、交互闭环、单文件架构、移动适配、中英双语离线切换**。项目专属信息见槽位表。

## 1. 总体架构

1. 单文件结构（顺序固定）：`<!doctype html>` → `<head>`（charset / viewport / title / SVG data-URI favicon / `<style>` 全部 CSS）→ `<body>`（骨架容器）→ `<script>`（数据）→ `<script>`（逻辑：i18n → 主题 → 渲染 → 交互 → 路由 → init）
2. favicon：内联 SVG data URI，紫青渐变圆角方块 + 居中白色加粗 `{{LOGO_LETTER}}`
3. 三段式布局：固定侧边栏 280px（可折叠）+ 主区（sticky 毛玻璃顶栏 + max-width 1400px 内容区）
4. 双文件机制：产出即数据源；部署时 `cp` 生成 `index.html`，SHA 一致

## 2. 设计系统（CSS 变量，全部必备）

```css
:root {
  --bg:#0a0a0f; --bg2:#12121a; --bg3:#1a1a2e;
  --surface:rgba(255,255,255,.03); --surface-hover:rgba(255,255,255,.06);
  --border:rgba(255,255,255,.08); --border-hover:rgba(255,255,255,.15);
  --text:#f1f1f6; --text2:rgba(255,255,255,.65); --text3:rgba(255,255,255,.35);
  --accent-v:{{ACCENT_V}}; --accent-c:{{ACCENT_C}};
  --accent-e:#22c55e; --accent-r:#ef4444;
  --radius:14px; --radius-sm:8px; --shadow:0 4px 24px rgba(0,0,0,.3);
  --font:-apple-system,BlinkMacSystemFont,'Segoe UI','PingFang SC','Microsoft YaHei',sans-serif;
  --font-mono:'SF Mono','Fira Code','Cascadia Code','JetBrains Mono','Consolas',monospace;
}
.light { /* 浅色全套覆写 */ }
```

强制规则：禁止硬编码颜色；`::selection` 主色 30%；`scroll-behavior:smooth`；细滚动条（6px + `scrollbar-width:thin`）；`:focus-visible` 青色 2px 焦点环；**分类色两两区分**（见 2.1）。

### 2.1 分类色彩体系（v2 新增硬性要求）

- 每个分类注册 zh/en 双语标签 + 专属主题色（`getCategoryLabels()` / `getCategoryColors()`）
- **色值两两不重复且肉眼可辨**：避免同族近似色（青 vs 青绿、靛蓝 vs 紫是历史踩坑项）；推荐取色环等距的 8 色：紫 `#8b5cf6` · 粉 `#ec4899` · 青 `#06b6d4` · 金 `#eab308` · 橙 `#f97316` · 绿 `#22c55e` · 灰蓝 `#64748b` · 亮紫 `#a855f7`
- 筛选按钮注入 `style="--cat-color:{色}"`，active 态用 `var(--cat-color, var(--accent-v))` 高亮 —— 每个分类菜单有自己的色彩身份
- 侧边栏分组标题前置 8px 分类色圆点（`sb-cat-dot`）；卡片顶部色条（`gc-bar`）与注册表色一致
- **技能/速查面板必须有分类入口**：在分类注册表中注册 `skills` 类（如无此类数据可整块省略 M7），杜绝"面板已渲染但 UI 无入口"的缺陷

## 3. 页面模块与组件清单（M1–M8，逐组件落地）

### M1 侧边栏（fixed 280px，折叠动画 transform .3s）

| # | 组件 | 规格 |
|---|------|------|
| 1.1 | Logo 区 | 渐变字母图标 + 主/副标题（`data-i18n`），点击回仪表盘 |
| 1.2 | 搜索框 | SVG 放大镜 + 输入框（`data-i18n-ph`），`oninput=filterSidebar` |
| 1.3 | 总进度条 | 标签 + 百分比 + 填充条 + 计数四元素 |
| 1.4 | 导航 | 按 `cat` 分组：分组标题（**分类色点** + 双语名）→ 条目列表 |
| 1.5 | 导航条目 | 状态点（done/ext）+「序号. 标题」+ 尾标（难度星/外链箭头）；active 高亮 |
| 1.6 | 移动端遮罩 | 768px 以下显示，点击关闭抽屉 |
| 1.7 | 加载态 | spinner + 双语文案 |

### M2 顶栏（sticky + backdrop-filter blur 16px）

| # | 组件 | 规格 |
|---|------|------|
| 2.1 | 汉堡按钮 | toggle 侧边栏（sidebar.hidden + main.expanded 联动） |
| 2.2 | 标题组 | 随视图动态切换（仪表盘=站名 / 详情=条目标题+副标题双语互换） |
| 2.3 | 顶栏搜索 | `main.expanded` 时显示，与侧边栏双向同步 |
| 2.4 | 时钟 | 脉冲绿点 + HH:MM:SS，1s 刷新 |
| 2.5 | 分享按钮 | `navigator.share` → clipboard 降级 + ✓ 反馈 2s |
| 2.6 | 进度三键 | 导出/导入/重置（danger 红），双语 title |
| 2.7 | 语言切换 | 地球 SVG + 目标语言标签（EN↔中），`toggleLang()` |
| 2.8 | 主题切换 | 月/日图标互换，`toggleTheme()` |

### M3 仪表盘

| # | 组件 | 规格 |
|---|------|------|
| 3.1 | 页头 | 徽章（计数）+ 大标题 + 描述（`data-i18n`） |
| 3.2 | 统计卡 | 三张：全部 / 分类数 / 已完成 |
| 3.3 | 筛选栏 | 「🏠 全部」+ 全部分类按钮（**各携 --cat-color**）；active 分类色高亮 |
| 3.4 | 分类区 | 图标 / 双语名 / 计数 / 完成度 / 延伸线五元素 |
| 3.5 | 卡片网格 | `repeat(auto-fill, minmax(320px, 1fr))`；与筛选+搜索联动隐藏空区 |

### M4 条目卡片（核心卡）

顶部色条（分类色）→ 步骤进度角标 → 卡头（emoji 图标 +「序号. 标题」+ 难度/耗时 + 完成勾选圆）→ 两行截断描述 → 前置标签（前 3）→ **步骤预览**（前 3 步可点直达 + 「查看全部 N 步/级 →」开弹窗）→ 外链卡变体（整卡跳转 + 域名显示）。动效：`fadeUp` 入场 + 交错延迟 + hover 上浮 2px。

### M5 详情页

返回链接 → 英雄区（分类色图标 + 标题 + 描述 + 元信息：分类/难度/overview 键值胶囊）→ 进度条（done/total 步 pct%）→ 前置条件列表 → **可折叠步骤**（序号圆点击切完成、标题、耗时、▶；正文 = 说明 + 代码块 + 警告 + 提示）→ 危险步骤红色边框态 → 深链目标步骤平滑滚动居中。

### M6 步骤预览弹窗

遮罩点击关闭 → 标题（图标+条目名+后缀）→ ✕ → 步骤列表（完成态序号圆/标题/耗时/完成标），点击直达该步骤。

### M7 技能/速查面板（有此类数据时必备）

面板页头（计数徽章 + 双语标题 + 描述含 `<code>`）→ 技能分类（emoji/双语名/五星复杂度/计数，`--sk-color` 分类色）→ 技能卡（名称+星级+描述+**可点击整条复制**的命令行）→ 搜索联动过滤 + 空状态。

### M8 全局状态

首屏 loading；外链 `rel="noopener" target="_blank"`；**一切外源文本经 `escHtml()` 转义**（见 4.1）。

## 4. 安全与健壮性规范（v2 新增 · 源自真实事故，不可省略）

### 4.1 转义铁律 —— 外源文本零裸插

**事故背景**：全景站曾因两条 README 摘录含未闭合 `<!--`，裸拼 `innerHTML` 后浏览器把后续 74 张卡全部吞成注释，全站内容区空白。

| 规则 | 内容 |
|---|---|
| R1 渲染侧 | 凡进入 `innerHTML` 模板插值的**数据字段**（desc / title / titleEn / steps[].title / content / warning / tip / prereq 项等）一律 `escHtml()` 包裹；受控字面量（I18N 词典、生成的 overview 键值）豁免 |
| R2 数据侧 | 生成/录入数据时清洗：去除 `<!--`、`-->` 残段；标签清洗正则不得依赖 `>` 存在（`<[^>]+>` 匹配不到未闭合注释） |
| R3 代码块 | `code` 字段禁含单引号（内联 `onclick` 传参约束，家族既有规约）；命令示例设计时即规避或改用双引号 |
| R4 属性侧 | URL 类插值（href）必须 `escHtml()`；用户可控键值不拼进内联事件 |

### 4.2 存储与运行时健壮性

- localStorage 读写统一 `lsGet()/lsSet()` try-catch 封装，`file://` / 隐私模式静默降级
- 剪贴板 `navigator.clipboard` → `document.execCommand('copy')` 双链路降级
- `GUIDES` 未就绪时轮询兜底（≤50 次 × 200ms）
- 全局 `window.onerror` 时在页面顶部显示可关闭的错误条（开发态默认开启），生产可静默但保留 console

## 5. 交互功能清单（16 项，全部必须实现）

| # | 功能 | 实现要点 | 持久化 |
|---|------|----------|--------|
| 1 | 深/浅主题 | `classList.toggle('light')` + 图标互换 | `theme` |
| 2 | 中/英切换 | 全量重渲染 + 筛选 active 态恢复（见第 6 章） | `lang` |
| 3 | 双入口搜索 | 侧栏+顶栏双向同步；过滤导航/卡片/技能/空分组 | — |
| 4 | 分类筛选 | 筛选+搜索组合；skills 分类切换面板并隐藏卡片统计 | — |
| 5 | 条目完成 | 卡片勾选圆；联动侧栏点+总进度+统计 | `guide-done-{id}` |
| 6 | 步骤完成 | 序号圆切换；进度条局部无刷新更新 | `step-done-{id}-{n}` |
| 7 | 步骤折叠 | 点标题行开合 | `step-open-{id}-{n}` |
| 8 | 预览弹窗 | 查看全部 → Modal → 点击直达+滚动居中 | — |
| 9 | 代码复制 | clipboard + execCommand 降级；✅ 反馈 2s | — |
| 10 | 命令复制 | 技能卡整条点击复制 | — |
| 11 | 进度导出 | JSON（含 exportTime/嵌套 done·open）→ Blob 下载带日期文件名 | 文件 |
| 12 | 进度导入 | 隐藏 input → FileReader → 格式校验 → 写回 → 双语 alert | — |
| 13 | 进度重置 | 双语 confirm → 逐键 remove → 重渲染 | — |
| 14 | 页面分享 | share → clipboard 降级 + 图标反馈 | — |
| 15 | 实时时钟 | `setInterval` 1s | — |
| 16 | Hash 深链 | `#guide-{id}` / `#guide-{id}-step-{n}`；load+hashchange 双监听；正则解析；返回清 hash | URL |

## 6. 多语言 i18n 架构（离线双语，不可缩减）

1. 词典 `const I18N = { zh: {...}, en: {...} }`，每语言 **49+ 键** + 元信息 `_code/_label/docTitle`，键集严格一致，覆盖全部界面框架文案
2. 取词：`t(key)` 当前→zh 兜底→键名（缺词不白屏）；`tf(key, vars)` 填 `{placeholder}`；`guideTitle(g)` en 优先 `titleEn` 回退；`diffLabel(d)` 难度双语
3. 静态标记三类：`data-i18n`（文本）/ `data-i18n-ph`（placeholder）/ `data-i18n-title`（title）
4. `applyStaticI18n()`：同步 `<html lang>`、`<title>`、静态标记、语言按钮标签
5. `setLanguage(lang)`：持久化 → 静态刷新 → 重渲染侧栏/仪表盘/技能面板/当前详情 → **恢复筛选按钮 active 态**（含 skills 面板态）
6. 分类标签（含技能面板 `catNames`）按 `currentLang` 双分支
7. 存储走 `lsGet/lsSet` 安全封装

## 7. 数据结构规范

```js
const GUIDES = [
  { id:'{{prefix}}01', order:1, cat:'{{cat-key}}', title:'中文标题', titleEn:'English Title',
    diff:'easy'|'medium'|'hard', time:'30 min', icon:'🤖', color:'#22c55e',
    desc:'描述（两行截断）', prereq:['前置'], overview:[['标签','值']],
    steps:[{ n:1, title:'步骤', time:'5 min', content:'说明',
             code:[['bash','命令']], warning:'警告?', tip:'提示?', isDestructive:false }],
    type:'external', externalUrl:'https://…'   // 外链型二选一
  }
];
const SKILLS = [ { cat:'{{skill-cat}}', order:1, name:'名称', desc:'描述', cmd:'可复制命令' } ];
```

分类注册表：`getCategoryLabels()`（zh/en 分支）/ `getCategoryColors()`，键值一一对应且含 skills（如有 M7）。

## 8. 存储与路由规范

| localStorage 键 | 含义 |
|---|---|
| `guide-done-{id}` / `step-done-{id}-{n}` / `step-open-{id}-{n}` | 完成与展开状态 |
| `theme` / `lang` | 主题与语言 |

路由：`parseGuideHash()` 正则 `^([^-]+)-step-(\d+)$`；非 guide 前缀 → 回仪表盘。

## 9. 响应式与无障碍规范（全部必备）

1. **768px**：侧栏全宽抽屉+遮罩；单列卡片；顶栏瘦身（藏时钟/副标题、标题 ellipsis ≤42vw）
2. **480px**：藏分享按钮；间距收紧
3. **触屏**：`@media (hover:none) and (pointer:coarse)` 点击目标 ≥36px
4. **减少动效**：`prefers-reduced-motion` 关闭全部动画/过渡/平滑滚动
5. **键盘**：`:focus-visible` 焦点环；交互按钮 `aria-label` 双语
6. 语言/主题按钮在所有断点保留

## 10. 质量要求

注释分区（`/* ═══ 区块 ═══ */`）；JS 字符串单引号；插值转义（4.1）；`initTheme`/语言初始化脚本载入即执行防闪烁；`init()` 监听 DOMContentLoaded 或 readyState 直调。

## 11. 项目参数槽位表

| 槽位 | 说明 |
|---|---|
| `{{PROJECT_NAME}} / {{PROJECT_NAME_EN}}` | 项目名（标题/侧栏/`<title>`） |
| `{{LOGO_LETTER}}` | Logo 字母 |
| `{{ACCENT_V}} / {{ACCENT_C}}` | 品牌双色 |
| `{{CATEGORIES}}` | 分类注册表（key/emoji/双语名/色，**含色环等距要求**） |
| `{{SKILL_CATEGORIES}}` | 技能分类（key/emoji/双语名/星级/色） |
| `{{GUIDES}} / {{SKILLS}}` | 数据数组（**入库前过 4.1 R2 清洗**） |
| `{{DASH_DESC}} / {{SUBTITLE}}` | 仪表盘描述与副标题（双语） |
| `{{REPO}} / {{DOMAIN}}` | 仓库与自定义域名 |

> ↑↑↑ 核心规格结束 ↑↑↑

---

# 第三章 · HTML 高级组件功能库（可调取 · 选装）

> **调取原则**：本章组件为增强能力，按项目需要勾选；一经选用即纳入验收。所有组件必须**离线单文件可用**——`✅ 原生离线`（零依赖直接用）或 `🔄 需自实现`（附实现路径），**禁止引入 CDN/框架**。与第二章核心规格叠加而非替换。

## 3.A 现代 CSS 能力（2024–2026 浏览器基线）

| 能力 | 用途（YYC³ 场景） | 离线 | 用法要点与降级 |
|---|---|---|---|
| `:has()` 父选择器 | 卡片"含已完成步骤"整卡变色；`body:has(.light)` 联动 | ✅ | 直接用；旧浏览器忽略即无增强，不破坏布局 |
| Container Queries | 侧栏抽屉内组件按容器宽（非视口）自适应 | ✅ | `container-type: inline-size` + `@container (min-width:400px)`；与既有 768px 断点叠加 |
| `color-mix()` | 分类色 hover 态自动派生（`color-mix(in oklab, var(--cat-color) 80%, white)`） | ✅ | 不支持则回退固定透明度写法（先写 fallback 后写增强） |
| `oklch()` 色彩 | 分类色环程序化生成（等色相间隔），比 hex 更均匀 | ✅ | 同上双层写法 |
| CSS Subgrid | 卡片网格内多行元信息严格对齐 | ✅ | `grid-template-rows: subgrid`；不支持自动退化为普通 grid |
| Scroll-driven Animations | 滚动进度条、卡片入场由滚动驱动 | ✅ | `animation-timeline: view()`；reduced-motion 媒体查询下禁用 |
| View Transitions | 语言/主题切换、仪表盘↔详情整页过渡 | ✅ | `document.startViewTransition(() => 重渲染())`；不支持则同步切换（现状） |
| Popover API | 提示气泡、轻量上下文菜单 | ✅ | `popover` 属性 + `showPopover()`；降级 M6 自有 modal |
| `<details>/<summary>` | 原生折叠（FAQ/步骤零 JS 折叠降级方案） | ✅ | 与自有 step 折叠并存时注意样式统一 |
| `text-wrap: balance` | 中文标题/按钮文案换行均衡 | ✅ | 一行 CSS，无降级必要 |
| Anchor Positioning | 浮层锚定（如"查看全部"气泡锚到按钮） | ⚠️ 新特性 | 仅增强；降级 `position:fixed` 居中 |
| `field-sizing: content` | 搜索框随内容自适应宽 | ✅ | 一行增强 |

## 3.B 原生高级组件（免 JS/轻 JS）

| 组件 | YYC³ 用法 | 要点 |
|---|---|---|
| `<dialog>` | M6 弹窗升级：原生焦点圈闭 + Esc 关闭 + `::backdrop` | `showModal()`；替换自有 overlay 时保留点击遮罩关闭逻辑 |
| Popover（3.A） | 卡片快捷操作气泡 | 免 aria 手写 |
| `<template>` + slot | 卡片骨架模板复用，减少字符串拼接 | `content.cloneNode(true)` |
| `<progress>/<meter>` | 导出进度、磁盘/体积条 | 原生无障碍 |
| `<search>` | 双入口搜索语义容器 | 包裹既有搜索框即可 |
| Accessible `<table>` | 大数据排名表（替代卡片网格的密集视图） | `scope`/`caption` 必配 |

## 3.C Web Components（自定义元素，单文件内可用）

适用：同页大量重复结构（卡片、标签、命令行）需要强隔离样式时。

```js
class YYC3Card extends HTMLElement {
  connectedCallback() { /* render + escHtml */ }
}
customElements.define('yyc3-card', YYC3Card);
```

| 规约 | 内容 |
|---|---|
| 命名 | `yyc3-` 前缀，防冲突 |
| 样式隔离 | Shadow DOM 仅用于叶子组件（命令行、标签）；容器级组件**不用** Shadow 以保留主题变量穿透 |
| 主题 | 内部颜色一律 `var(--accent-v)` 等继承变量，不得硬编码 |
| i18n | 组件内渲染仍走 `t()/tf()` |
| 安全 | 传入属性经 `escHtml()`，同 4.1 |
| 取舍 | 蓝本字符串拼接已足够快（93 卡 <50ms）；仅在组件数 >500 或需跨页复用时启用 |

## 3.D 交互增强组件模式（纯 JS 实现，零依赖）

| 组件 | 场景 | 实现路径（离线） |
|---|---|---|
| **命令面板 ⌘K** | 93+ 条目快速跳转：Ctrl/⌘+K 唤起 → 模糊搜 title/titleEn/cat → 回车直达 | 自有 modal 变体 + keydown 监听 + 评分排序（前缀>包含>拼音首字母可后置）；复用 `searchQuery` 体系 |
| **虚拟滚动** | 条目 >500 时侧边栏/网格只渲染可视区 | 计算行高 × 容器高 → 绝对定位窗口渲染；93 条以内**不需要**（当前规模实测流畅） |
| **Toast 通知** | 复制/导入/重置反馈替代 alert | 单例容器 + 队列 + ARIA `role="status"` + 3s 自动消失；替代 importSuccess 的 alert |
| **骨架屏** | 大数据首屏 | CSS 渐变占位块 + 数据就绪后替换 loading spinner |
| **拖拽排序** | 用户自定义卡片顺序 | HTML5 DnD（dragstart/dragover/drop）+ `localStorage.order` 序列化 |
| **右键上下文菜单** | 卡片：完成/复制链接/查看全部 | `contextmenu` 事件 + 自有浮层（或 Popover API）；阻止默认仅限卡片区域 |
| **键盘快捷键系统** | J/K 上下条目、Enter 打开、Esc 返回/关弹窗、/ 聚焦搜索 | 全局 keydown 分发器 + 当页上下文判断；快捷键说明浮层（? 键唤起） |
| **富文本/Markdown 渲染** | steps.content 支持 `**粗体**`、行内 code | 自写 mini-parser（先 escHtml 再替换标记，顺序不可反）；**禁引外部 marked** |
| **撤销栈** | 误触"重置/取消完成"后 Ctrl+Z 恢复 | 操作前快照相关键值，≤20 步内存栈 |
| **批量操作** | Shift 多选卡片 → 批量完成/导出选中 | checkbox 模式切换 + 集合操作 |

## 3.E 可视化组件（SVG/Canvas，离线绘制）

| 组件 | YYC³ 场景 | 实现路径 |
|---|---|---|
| **环形进度** | 总进度/分类进度升级（替代线性条） | 内联 SVG `stroke-dasharray` 动画；中英百分比文案居中 |
| **Sparkline 迷你趋势** | 提交活跃度曲线（扫描数据含 last_commit/commit_count） | SVG polyline，数据点 ≤30 |
| **雷达图** | **五维评分可视化**（T/U/C/M/B 一屏对比）——全景站强推荐 | SVG 五边形网格 + 数据多边形填充分类色 20% 透明 |
| **分布条形图** | 分类条目数/等级分布 | 纯 CSS `flex` 宽度百分比即可，无需 SVG |
| **热力日历** | 提交热力图（GitHub 风格） | CSS grid 7 列 + 强度五档色（`color-mix` 派生） |
| Canvas 动效 | 品牌 portal 页背景粒子/3D | `requestAnimationFrame` + 帧率检测；reduced-motion 下静态首帧 |

## 3.F PWA 与离线增强

| 能力 | 说明 | 离线要求 |
|---|---|---|
| **单文件自缓存 SW** | Service Worker 缓存自身 URL → 真"断网可开" | SW 代码以 Blob/data 形式内联注册；`file://` 下自动跳过（SW 仅 http/https） |
| **manifest（data URI）** | 添加到主屏幕、独立窗口、主题色 | `<link rel="manifest" href="data:application/manifest+json,…">` |
| **IndexedDB 进度备份** | localStorage 之外二进制/大体量备份层 | 纯异步 API，导入导出的中间层 |
| **Web Share API** | 已在核心规格（功能 14） | — |

## 3.G 性能组件

| 技术 | 场景 | 用法 |
|---|---|---|
| `content-visibility: auto` | 长页面（93+ 卡片）滚动区渲染跳过 | `.cat-section { content-visibility:auto; contain-intrinsic-size: auto 600px; }` 防滚动条跳动 |
| `loading="lazy"` | 卡片内img/iframe（外链卡缩略） | 属性直加 |
| `requestIdleCallback` | 预渲染侧栏/预取 hash 目标 | 非紧急渲染延后；无该 API 用 setTimeout 降级 |
| 防抖/节流 | 搜索输入（80–150ms）、resize | 工具函数统一放脚本头部 |
| `DocumentFragment` | 一次 innerHTML 超大时的替代装配 | 当前直接 innerHTML 拼接实测 93 卡无压力；>500 卡改 Fragment + 分片 |

## 3.H 无障碍高级（ARIA）

| 能力 | 场景 | 要点 |
|---|---|---|
| `aria-live="polite"` | Toast/进度变化播报 | 通知容器常驻 |
| 焦点圈闭（focus trap） | 自有 Modal（未用 `<dialog>` 时） | Tab 循环限制在弹窗内；关闭后焦点归还触发元素 |
| `aria-expanded/collapsed` | 步骤折叠、侧栏抽屉 | 状态与视觉同步 |
| `role="tablist/tab"` | 筛选栏语义化 | 按钮组 + 方向键切换 |
| 色彩对比 | 分类色做**文字色**时须 ≥4.5:1（做装饰色条/背景时 ≥3:1） | 金 `#eab308` 等亮色慎做小号文字色，改深一档或仅作装饰 |

---

# 第四章 · 附录

## 附录 A · 验收清单（逐项打勾，缺一不通过）

### A1 结构与离线
- [ ] 单文件，`<script>/<link>/<img>/@import/url()` 零外部引用
- [ ] 两个内联脚本块 `node --check` 通过
- [ ] HTML 标签平衡（解析器校验）
- [ ] favicon 内联 SVG data URI 含 `{{LOGO_LETTER}}`
- [ ] `index.html` 与数据源 SHA 一致

### A2 组件完整性（对照 M1–M8 逐项）
- [ ] M1 七组件 / M2 八组件 / M3 五组件 / M4 卡片全要素 / M5 详情九要素 / M6 弹窗 / M7 技能面板（有数据时）/ M8 全局态
- [ ] 难度三级色 + 双语标签正确

### A3 功能与菜单（v2 强化）
- [ ] 16 项交互逐项通过
- [ ] localStorage 5 类键正确
- [ ] Hash 深链直达并滚动居中
- [ ] **每个分类菜单点击后显示且仅显示本类条目**（数量与数据一致、无混类、无空白）
- [ ] skills/速查分类有 UI 入口且点击正确切换面板

### A4 双语完整性
- [ ] 词典两语言键集一致、模板占位符同名同集
- [ ] 全部 `data-i18n*` 与 `t()/tf()` 引用有效
- [ ] 切换后：`<html lang>`/`<title>`/静态/侧栏/仪表盘/筛选栏/详情/技能面板/弹窗全部更新；筛选 active 态恢复；刷新语言保持

### A5 响应式与无障碍
- [ ] 768px / 480px / 触屏 36px / reduced-motion / 焦点环全部生效
- [ ] 分类色做文字色时对比度达标（3.H）

### A6 色彩体系（v2 新增）
- [ ] 分类色两两不重复且肉眼可辨（无青/青绿、靛/紫近似对）
- [ ] 筛选按钮 active 态显示各自分类色；侧栏色点、卡片色条与注册表一致

### A7 安全与真实渲染验收（v2 新增 · 源自事故）
- [ ] **escHtml 审计**：脚本内所有 innerHTML 数据插值逐处核对（grep `${g.desc`/`${s.content` 等裸插值为 0）
- [ ] **数据清洗**：数据块 `<!--`/`-->` 计数为 0；code 字段无单引号
- [ ] **真实解析器渲染**：以 jsdom（`runScripts:'dangerously'`）或等价真实引擎加载整页 —— 卡片数 === 数据条数、分类区数 === 分类数、控制台零错误、**真实点击遍历全部分类按钮**逐一断言（mock 级测试不发现 `<!--` 类解析截断，此级验收不可省略）
- [ ] 选装组件（如有）各自验收点通过

### A8 运行时冒烟（自动化参考）
Node + DOM 模拟：init → zh/en 切换 → 详情 → 技能面板 → 弹窗 → 持久化断言（蓝本参考 26/26；全景站实证 24/24 + 分类遍历）。

## 附录 B · 批量生产模板（90+ 项目）

### B1 单项目参数表

```yaml
PROJECT_NAME / PROJECT_NAME_EN / LOGO_LETTER: <项目标识>
ACCENT_V / ACCENT_C: <品牌双色>
SUBTITLE / SUBTITLE_EN / DASH_DESC: <双语文案>
CATEGORIES: <分类注册表（含等距色环）>
SKILL_CATEGORIES: <可选>
GUIDES / SKILLS: <数据（过 4.1 R2 清洗）>
REPO / DOMAIN: <部署信息>
ADVANCED_COMPONENTS: <可选：第三章勾选清单，如 [命令面板, 雷达图, Toast]>
```

### B2 流程

填槽（含选装勾选）→ 投喂/开发 → 附录 A 全项验收（**A7 必做**）→ `cp` 同步 → push main 自动部署 → 域名注册（CNAME → `YYC-Cube.github.io`，强制 HTTPS）

### B3 规模弹性

无 SKILLS 数据可省 M7 与 skills 分类按钮，其余不可缩减；条目 >500 时启用 3.D 虚拟滚动与 3.G content-visibility。

## 附录 C · 与家族规范的关系

- 色彩/字体/圆角/动效基线遵循 [YYC3-HTML-设计指导文档.md](YYC3-HTML-设计指导文档.md)；本文件在其上**固化**操作中心形态并新增：分类色彩体系（2.1）、安全规范（4.x）、高级组件库（第三章）
- 设计指导文档 8.1「多语言切换」已在本规格第 6 章落地；8.x 其余蓝图项（书签/快捷键/PWA/图表）对应本章 3.D/3.E/3.F 选装实现
- 设计指导文档 9.x MUST 项全部包含于第 2、9 章

## 版本记录

| 版本 | 日期 | 变更 |
|---|---|---|
| v1.0 | 2026-08-19 | 初版：生成提示词（M1–M8 / 16 交互 / i18n 49 键） |
| v2.0 | 2026-08-20 | 升级为团队 HTML 版本设计指导文档：双轨定位；新增分类色彩体系（2.1）、安全与健壮性规范（4.x，源自 `<!--` 污染事故复盘）、HTML 高级组件功能库（第三章 A–H 可调取）、验收清单强化（A3/A6/A7：菜单遍历、色彩区分、escHtml 审计、jsdom 真实渲染验收） |

---

*YanYuCloudCube™ — 言启千行代码，语枢万物智能*
*本文件为 YYC³ 团队 HTML 版本设计的统一指导文档与标准生成提示词；第二章核心规格不可缩减，第三章高级组件按需调取*
