#!/usr/bin/env bash
# upstream_weekly.sh — weekly upstream report for NousResearch/hermes-agent (via the `upstream` remote).
#
# What it does:
#   1. `git fetch upstream --tags --depth=50` (shallow, cheap).
#   2. Counts new commits on upstream/main not in HEAD (`git rev-list --count HEAD..upstream/main`).
#      NOTE: with --depth=50 the count is a lower bound capped by the shallow boundary.
#   3. Lists upstream releases published in the window and the latest release/tag (`gh api`).
#   4. Rough security screen: GitHub commit search for "security" since the window start,
#      plus a grep of the latest release notes for security/cve/ghsa.
#   5. One-line verdict on whether an upgrade evaluation is warranted.
#
# Graceful degradation: if `gh` is missing / unauthenticated / the network fails, GitHub-API
# sections are marked DEGRADED and the report falls back to local git data (fetch permitting).
#
# Usage:
#   scripts/upstream_weekly.sh                 # 7-day window, stdout
#   scripts/upstream_weekly.sh --days 14       # custom window
#   scripts/upstream_weekly.sh --out FILE.md   # also write the report to FILE (markdown)
#   scripts/upstream_weekly.sh --help
#
# Exit code: 0 normally (degradation is reported in-body); 2 only on usage errors.

set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/.."
cd "$REPO_ROOT" || exit 1

UPSTREAM_REPO="NousResearch/hermes-agent"
DAYS=7
OUT=""

usage() {
  sed -n '2,32p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --days) DAYS="${2:?--days needs a number}"; shift 2 ;;
    --out)  OUT="${2:?--out needs a file path}"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "unknown option: $1 (try --help)" >&2; exit 2 ;;
  esac
done
[[ "$DAYS" =~ ^[0-9]+$ ]] || { echo "--days must be a number" >&2; exit 2; }

WIN_SECS=$(( DAYS * 86400 ))
NOW_EPOCH="$(date +%s)"
CUTOFF_EPOCH=$(( NOW_EPOCH - WIN_SECS ))
# BSD date (macOS) vs GNU date
if CUTOFF_ISO="$(date -u -r "$CUTOFF_EPOCH" +%Y-%m-%d 2>/dev/null)"; then :;
else CUTOFF_ISO="$(date -u -d "@$CUTOFF_EPOCH" +%Y-%m-%d 2>/dev/null)" || CUTOFF_ISO="unknown"; fi

# ── output plumbing: buffer everything, then stdout (+ optional --out) ───────
BUF="$(mktemp "${TMPDIR:-/tmp}/upstream_weekly.XXXXXX")"
trap 'rm -f "$BUF"' EXIT
emit() { printf '%s\n' "$1" >> "$BUF"; }

WARNINGS=0
warn() { emit "⚠️  $1"; WARNINGS=$((WARNINGS+1)); }

# Degradation is decided ONCE here, in the parent shell: command substitutions run in
# subshells and cannot propagate variable changes back, so per-call cascades don't work.
GH_OK=1
GH_FAIL_REASON=""
if ! command -v gh >/dev/null 2>&1; then
  GH_OK=0; GH_FAIL_REASON="gh 未安装"
elif ! gh auth status >/dev/null 2>&1; then
  GH_OK=0; GH_FAIL_REASON="gh 未认证"
fi
gh_api() { # gh_api <gh api args...> -> prints result on stdout; warns inline on failure
  [[ "$GH_OK" == 1 ]] || return 1
  local out rc=0
  out="$(gh api "$@" 2>&1)" || rc=$?
  if (( rc != 0 )); then
    warn "gh api '$*' 失败: $(printf '%s' "$out" | tail -n1)"
    return 1
  fi
  printf '%s\n' "$out"
}

# ── header ───────────────────────────────────────────────────────────────────
emit "# Hermes 上游周报 — $UPSTREAM_REPO"
emit ""
emit "- 生成时间: $(date '+%Y-%m-%d %H:%M %Z')"
emit "- 统计窗口: 最近 ${DAYS} 天 ($CUTOFF_ISO .. 今天)"
emit ""

# ── 1. fetch ─────────────────────────────────────────────────────────────────
emit "## 1. 上游抓取"
if git fetch upstream --tags --depth=50 >/dev/null 2>&1; then
  emit "- \`git fetch upstream --tags --depth=50\` ✅ 成功（浅量）"
else
  warn "git fetch upstream 失败（网络/远端不可达）——以下 git 数据基于本地已有的上游引用，可能过时"
fi
emit ""

# ── 2. new commits on upstream/main ─────────────────────────────────────────
emit "## 2. 上游 main 新提交（不在本 fork HEAD 中）"
if git rev-parse --verify upstream/main >/dev/null 2>&1; then
  CNT="$(git rev-list --count HEAD..upstream/main 2>/dev/null || echo '?')"
  if [[ "$CNT" == "?" ]]; then
    warn "rev-list 统计失败（浅历史边界）"
  else
    emit "- 新提交数: **$CNT**（受 --depth=50 浅抓取限制，此为下限）"
  fi
  if (( ${CNT:-0} > 0 )) 2>/dev/null; then
    emit ""
    emit '```'
    git log --oneline --no-decorate HEAD..upstream/main 2>/dev/null | head -10 | while IFS= read -r l; do emit "  $l"; done
    (( $(git rev-list --count HEAD..upstream/main 2>/dev/null || echo 0) > 10 )) && emit "  ... (truncated)"
    emit '```'
  fi
else
  warn "本地没有 upstream/main 引用——无法统计新提交"
fi
emit ""

# ── 3. releases & tags ──────────────────────────────────────────────────────
emit "## 3. 上游 Release / Tag"
RELEASES=""
if [[ "$GH_OK" == 1 ]] && RELEASES="$(gh_api "repos/$UPSTREAM_REPO/releases" --paginate -q '.[] | select(.published_at != null and .draft != true) | select((.published_at | fromdateiso8601) > (now - '"$WIN_SECS"')) | .tag_name + "  " + .published_at[0:10]')"; then
  emit "- 窗口内发布的 release:"
  printf '%s\n' "$RELEASES" | while IFS= read -r l; do emit "  - $l"; done
else
  if [[ "$GH_OK" == 1 ]]; then emit "- 窗口内（${DAYS} 天）没有新 release"; else emit "- 窗口内 release 查询不可用（${GH_FAIL_REASON}）"; fi
fi
if [[ "$GH_OK" == 1 ]] && LATEST_REL="$(gh_api "repos/$UPSTREAM_REPO/releases/latest" -q '.tag_name + "  " + (.published_at // "?")[0:10]')"; then
  emit "- 最新 release: **$LATEST_REL**"
fi
if [[ "$GH_OK" == 1 ]] && PUSHED="$(gh_api "repos/$UPSTREAM_REPO" -q .pushed_at)"; then
  emit "- 上游最近 push: $PUSHED"
fi
LATEST_TAG="$(git for-each-ref refs/tags --sort=-creatordate --format='%(refname:short) %(creatordate:short)' 2>/dev/null | head -3)"
if [[ -n "$LATEST_TAG" ]]; then
  emit "- 本地最新 tags（浅抓取）:"
  printf '%s\n' "$LATEST_TAG" | while IFS= read -r l; do emit "  - $l"; done
fi
[[ "$GH_OK" == 0 ]] && warn "GitHub API 整体不可用（${GH_FAIL_REASON}）——本节不完整"
emit ""

# ── 4. security-related screen ──────────────────────────────────────────────
emit "## 4. 安全相关粗筛"
SEC_HITS=0
if [[ "$GH_OK" == 1 ]] && SEC_JSON="$(gh_api "search/commits?q=repo:$UPSTREAM_REPO+security+committer-date:>${CUTOFF_ISO}" -q '.total_count')"; then
  SEC_HITS="${SEC_JSON:-0}"
  emit "- commit search（\"security\", committer-date > ${CUTOFF_ISO}）命中: **${SEC_HITS}**"
  if (( SEC_HITS > 0 )) 2>/dev/null; then
    gh_api "search/commits?q=repo:$UPSTREAM_REPO+security+committer-date:>${CUTOFF_ISO}" \
      -q '.items[] | "  - " + .sha[0:8] + " " + (.commit.message | split("\n")[0])' \
      | while IFS= read -r l; do emit "$l"; done
  fi
else
  if [[ "$GH_OK" == 1 ]]; then emit "- commit search: 无结果"; else emit "- commit search: 不可用（${GH_FAIL_REASON}）"; fi
fi
if [[ "$GH_OK" == 1 ]]; then
  REL_BODY="$(gh api "repos/$UPSTREAM_REPO/releases/latest" -q '.body // ""' 2>/dev/null || true)"
  SEC_LINES="$(printf '%s\n' "$REL_BODY" | grep -iE 'security|cve|ghsa' | head -5 || true)"
  if [[ -n "$SEC_LINES" ]]; then
    emit "- 最新 release notes 中的安全相关行:"
    printf '%s\n' "$SEC_LINES" | while IFS= read -r l; do emit "  - ${l:0:160}"; done
  else
    emit "- 最新 release notes: 未发现 security/cve/ghsa 关键词"
  fi
fi
emit ""

# ── 5. verdict ──────────────────────────────────────────────────────────────
NEED=0; WHY=()
if (( ${CNT:-0} > 0 )) 2>/dev/null; then NEED=1; WHY+=("上游 main 有 $CNT 个新提交"); fi
if [[ -n "$RELEASES" ]]; then NEED=1; WHY+=("窗口内有新 release"); fi
if (( SEC_HITS > 0 )) 2>/dev/null; then NEED=1; WHY+=("命中 $SEC_HITS 条含 security 的提交"); fi
if [[ -n "${PUSHED:-}" ]]; then
  PUSHED_EPOCH="$(date -u -j -f '%Y-%m-%dT%H:%M:%SZ' "${PUSHED}" +%s 2>/dev/null || date -u -d "${PUSHED}" +%s 2>/dev/null || echo 0)"
  if (( PUSHED_EPOCH >= CUTOFF_EPOCH && PUSHED_EPOCH > 0 )) 2>/dev/null; then NEED=1; WHY+=("上游最近 push 在窗口内 ($PUSHED)"); fi
fi
emit "## 5. 结论"
if (( NEED == 1 )); then
  JOINED=""; SEP=""
  for w in "${WHY[@]}"; do JOINED+="${SEP}${w}"; SEP="；"; done
  emit "➡️  **建议评估升级**：${JOINED}。"
else
  emit "✅ **暂无需升级评估**：窗口内未见新提交/release/安全提交。"
fi
if (( WARNINGS > 0 )); then emit ""; emit "（报告含 $WARNINGS 条降级/警告，数据完整性受限）"; fi

# ── flush ───────────────────────────────────────────────────────────────────
if [[ -n "$OUT" ]]; then
  mkdir -p "$(dirname "$OUT")" 2>/dev/null
  cp "$BUF" "$OUT" && emit_note="saved to $OUT" || emit_note="FAILED to save $OUT"
fi
cat "$BUF"
[[ -n "${emit_note:-}" ]] && echo "[upstream_weekly] $emit_note" >&2
exit 0
