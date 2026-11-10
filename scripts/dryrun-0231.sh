#!/usr/bin/env bash
# dryrun-0231.sh — whole-tree switch dry run vs upstream-v0.23.1 (07 报告 §7.2-3 的无历史等价实现)
#
# fork 是 squash 导入（ceb2a4a11f 无上游 parent），无法 merge-base，rebase 干跑不可行；
# 本脚本用「锚点树三方对比 + blob 级 git merge-file 逐文件实测」获得同一决策数字：
#   base    = v0.21.4+canary.20260925T065930Z（07 报告选定的代理基线锚点）
#   ours    = main（import 之后的全部定制）
#   theirs  = upstream-v0.23.1（浅取 tag，树完整）
# 交集 = 我方变更集 ∩ 上游变更集；对交集逐文件做真实三方合并 → 自动可解 vs 真冲突。
# 输出: docs/hermes-agent-实施专家-20261024/logs/dryrun-0231/{ours,upstream,intersect,clean,conflicts,special}.txt
set -uo pipefail
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO"
ANCHOR="v0.21.4+canary.20260925T065930Z"
IMPORT="ceb2a4a11f"
UP="upstream-v0.23.1"
OUT="docs/hermes-agent-实施专家-20261024/logs/dryrun-0231"
mkdir -p "$OUT"

git diff --no-renames --name-only "$IMPORT" main | sort -u > "$OUT/ours.txt"
git diff --no-renames --name-only "$ANCHOR" "$UP" | sort -u > "$OUT/upstream.txt"
comm -12 "$OUT/ours.txt" "$OUT/upstream.txt" > "$OUT/intersect.txt"

echo "ours_files=$(wc -l < "$OUT/ours.txt" | tr -d ' ')"
echo "upstream_files=$(wc -l < "$OUT/upstream.txt" | tr -d ' ')"
echo "intersect=$(wc -l < "$OUT/intersect.txt" | tr -d ' ')"

: > "$OUT/clean.txt"; : > "$OUT/conflicts.txt"; : > "$OUT/special.txt"
while IFS= read -r f; do
  if ! git cat-file -e "$ANCHOR:$f" 2>/dev/null; then echo "added-both-sides $f" >> "$OUT/special.txt"; continue; fi
  if ! git cat-file -e "main:$f" 2>/dev/null;    then echo "deleted-by-ours $f" >> "$OUT/special.txt"; continue; fi
  if ! git cat-file -e "$UP:$f" 2>/dev/null;     then echo "deleted-upstream $f" >> "$OUT/special.txt"; continue; fi
  git show "$ANCHOR:$f" > /tmp/_d_base 2>/dev/null
  git show "main:$f"    > /tmp/_d_ours 2>/dev/null
  git show "$UP:$f"     > /tmp/_d_theirs 2>/dev/null
  cp /tmp/_d_ours /tmp/_d_merged
  if git merge-file -L base -L ours -L theirs /tmp/_d_merged /tmp/_d_base /tmp/_d_theirs >/dev/null 2>&1; then
    echo "$f" >> "$OUT/clean.txt"
  else
    echo "$f" >> "$OUT/conflicts.txt"
  fi
done < "$OUT/intersect.txt"

echo "clean=$(wc -l < "$OUT/clean.txt" | tr -d ' ')"
echo "conflicts=$(wc -l < "$OUT/conflicts.txt" | tr -d ' ')"
echo "special=$(wc -l < "$OUT/special.txt" | tr -d ' ')"
echo "--- conflict breakdown by dir (top 20) ---"
sed 's|^.*/||;t;/\//H;$!d' /dev/null 2>/dev/null # noop
awk -F/ '{if (NF>2) print $1"/"$2; else if (NF>1) print $1; else print "(root)"}' "$OUT/conflicts.txt" | sort | uniq -c | sort -rn | head -20
echo "--- special breakdown ---"
awk '{print $1}' "$OUT/special.txt" | sort | uniq -c