#!/usr/bin/env bash
# preflight.sh — one-command local gate for YYC3-Hermes-Agent (fork of NousResearch/hermes-agent).
#
# Runs, in order (any failure is recorded and reported in the final PASS/FAIL table; total target < 3 min):
#   1. Version gates — mirrors CI exactly:
#        python 3.11.x  <- .github/workflows/tests.yml (`uv python install 3.11`, `uv sync --locked --python 3.11`)
#        uv >= 0.9.28   <- .github/workflows/lint.yml + docker.yml (astral-sh/setup-uv `version: "0.9.28"`)
#        rg  >= 15.1.0  <- .github/workflows/tests.yml (RG_VERSION=15.1.0 prebuilt binary)
#        node >= 22     <- .github/workflows/js-tests.yml pins 26 in CI; local floor is 22 (major only).
#                          Related precedent: .npmrc `min-release-age=14` assumes a modern npm/engine-strict.
#   2. Dependency consistency: `uv sync --locked --dry-run` (no venv mutation).
#   3. OSV supply-chain scan: `hermes security audit --fail-on high`
#        (exit != 0 iff any finding >= HIGH; LOW/MODERATE allowed — e.g. the known setuptools 83.0.0 LOW pin).
#        NOTE: ~/.hermes/hermes-agent/venv holds an editable install whose meta-path finder maps to the
#        pre-move repo path (/Users/yanyu/YYC-Cube/YYC3-Hermes-Agent, now gone). Exporting
#        PYTHONPATH=$REPO_ROOT lets the standard PathFinder resolve hermes_cli from this checkout.
#   4. Security-targeted tests (dashboard auth) via the canonical runner scripts/run_tests.sh
#        (~8s wall with per-file subprocess isolation). Skipped by --quick.
#   5. Website key-asset existence: pubilc/YYC3-HERMES-HUB-OFFLINE.html (repo root; "pubilc" is the
#        intentional on-disk dir name) and website/src/pages/skills/index.tsx.
#
# Usage:
#   scripts/preflight.sh           # full gate
#   scripts/preflight.sh --quick   # skip step 4 (security tests)
#   scripts/preflight.sh --help
#
# Exit code: 0 iff every executed step PASSes.

set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT" || exit 1

HERMES_VENV="${HERMES_VENV:-$HOME/.hermes/hermes-agent/venv}"

QUICK=0
case "${1:-}" in
  --quick) QUICK=1 ;;
  -h|--help)
    sed -n '2,40p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
    exit 0 ;;
  "") ;;
  *) echo "unknown option: $1 (try --help)" >&2; exit 2 ;;
esac

# ── colors ───────────────────────────────────────────────────────────────────
if [[ -t 1 && -z "${NO_COLOR:-}" ]]; then
  RED=$'\033[31m'; GREEN=$'\033[32m'; YELLOW=$'\033[33m'; BOLD=$'\033[1m'; DIM=$'\033[2m'; NC=$'\033[0m'
else
  RED=""; GREEN=""; YELLOW=""; BOLD=""; DIM=""; NC=""
fi
pass() { printf '  %sPASS%s  %s\n' "$GREEN" "$NC" "$1"; }
fail() { printf '  %sFAIL%s  %s\n' "$RED" "$NC" "$1"; }
note() { printf '       %s%s%s\n' "$DIM" "$1" "$NC"; }

# ── results ledger ───────────────────────────────────────────────────────────
STEPS_LABEL=(); STEPS_STATUS=(); STEPS_SECS=()
run_step() { # run_step <label> <cmd...>  (returns cmd status, records result)
  local label="$1"; shift
  printf '%s\n' "${BOLD}── $label${NC}"
  local t0=$SECONDS rc=0
  "$@" || rc=$?
  STEPS_LABEL+=("$label")
  STEPS_STATUS+=("$rc")
  STEPS_SECS+=("$((SECONDS - t0))s")
  return "$rc"
}

# ── step 1: version gates ────────────────────────────────────────────────────
ver_ge() { # ver_ge <got> <want> -> 0 iff got >= want (semver-ish, sort -V)
  [[ "$(printf '%s\n%s\n' "$2" "$1" | sort -V | head -n1)" == "$2" ]]
}
check_python() {
  local v; v="$(python3 -c 'import sys; print("%d.%d" % sys.version_info[:2])')" || return 1
  if [[ "$v" == "3.11" ]]; then pass "python3 $v (CI: 3.11, tests.yml)"; return 0
  else fail "python3 $v != 3.11.x (CI pins 3.11 in tests.yml)"; return 1; fi
}
check_uv() {
  local got="0.0"; got="$(uv --version 2>/dev/null | awk '{print $2}')"
  if ver_ge "$got" "0.9.28"; then pass "uv $got (CI floor 0.9.28, lint.yml/docker.yml)"; return 0
  else fail "uv $got < 0.9.28"; return 1; fi
}
check_rg() {
  local got="0.0"; got="$(rg --version 2>/dev/null | head -n1 | awk '{print $2}')"
  if ver_ge "$got" "15.1.0"; then pass "rg $got (CI floor 15.1.0, tests.yml)"; return 0
  else fail "rg $got < 15.1.0"; return 1; fi
}
check_node() {
  command -v node >/dev/null 2>&1 || { fail "node not found"; return 1; }
  local v maj; v="$(node -v)"; maj="${v#v}"; maj="${maj%%.*}"
  if [[ "$maj" =~ ^[0-9]+$ ]] && (( maj >= 22 )); then
    pass "node $v major=$maj >= 22 (CI js-tests.yml pins 26; local floor 22)"; return 0
  else fail "node $v major < 22"; return 1; fi
}
check_uv_sync() {
  echo "  running: uv sync --locked --dry-run ..."
  local out rc=0
  out="$(uv sync --locked --dry-run 2>&1)" || rc=$?
  if (( rc == 0 )); then
    pass "uv sync --locked --dry-run (lockfile consistent; venv untouched)"
    note "$(echo "$out" | grep -c '^ *+' 2>/dev/null || echo 0) package(s) would (re)install in a real sync"
    return 0
  else
    fail "uv sync --locked --dry-run exited $rc"
    note "$(echo "$out" | tail -n 5 | tr '\n' ' ')"
    return 1
  fi
}
check_osv() {
  local hermes_bin="$HERMES_VENV/bin/hermes"
  if [[ ! -x "$hermes_bin" ]]; then
    fail "hermes binary not found/executable: $hermes_bin (override with HERMES_VENV=...)"
    return 1
  fi
  # PYTHONPATH: the ~/.hermes venv's editable finder maps to the stale pre-move path; the
  # standard PathFinder (earlier in sys.meta_path) resolves hermes_cli from this checkout.
  local out rc=0
  out="$(PYTHONPATH="$REPO_ROOT" "$hermes_bin" security audit --fail-on high 2>&1)" || rc=$?
  echo "$out" | sed 's/^/  | /'
  if (( rc == 0 )); then
    pass "OSV scan: no HIGH/CRITICAL findings (LOW/MODERATE allowed, --fail-on high)"
    return 0
  else
    fail "OSV scan: findings >= HIGH present (exit $rc)"
    return 1
  fi
}
check_tests() {
  bash scripts/run_tests.sh \
    tests/hermes_cli/test_dashboard_auth_body_limit.py \
    tests/hermes_cli/test_dashboard_auth_audit.py \
    tests/hermes_cli/test_dashboard_auth_password_login.py \
    tests/hermes_cli/test_dashboard_auth_native_flow.py
}
check_assets() {
  local rc=0 f
  for f in "pubilc/YYC3-HERMES-HUB-OFFLINE.html" "website/src/pages/skills/index.tsx"; do
    if [[ -f "$f" ]]; then pass "asset present: $f"; else fail "asset MISSING: $f"; rc=1; fi
  done
  return "$rc"
}

# ── run ──────────────────────────────────────────────────────────────────────
T_START=$SECONDS
printf '%s\n' "${BOLD}Hermes preflight gate — repo: $REPO_ROOT${NC}"
[[ "$QUICK" == 1 ]] && printf '%s\n' "${YELLOW}(--quick: skipping security tests)${NC}"

FAILS=0
run_step "1. versions: python 3.11.x"  check_python || FAILS=$((FAILS+1))
run_step "1. versions: uv >= 0.9.28"   check_uv     || FAILS=$((FAILS+1))
run_step "1. versions: rg >= 15.1.0"   check_rg     || FAILS=$((FAILS+1))
run_step "1. versions: node >= 22"     check_node   || FAILS=$((FAILS+1))
run_step "2. deps: uv sync --locked --dry-run" check_uv_sync || FAILS=$((FAILS+1))
run_step "3. OSV: hermes security audit (--fail-on high)" check_osv || FAILS=$((FAILS+1))
if [[ "$QUICK" == 1 ]]; then
  STEPS_LABEL+=("4. security tests (dashboard auth)")
  STEPS_STATUS+=("SKIP"); STEPS_SECS+=("0s")
  printf '%s\n' "${YELLOW}── 4. security tests: SKIPPED (--quick)${NC}"
else
  run_step "4. security tests (dashboard auth x4)" check_tests || FAILS=$((FAILS+1))
fi
run_step "5. site key assets" check_assets || FAILS=$((FAILS+1))

# ── summary ──────────────────────────────────────────────────────────────────
printf '\n%s\n' "${BOLD}════ PASS/FAIL summary ════${NC}"
for i in "${!STEPS_LABEL[@]}"; do
  s="${STEPS_STATUS[$i]}"
  case "$s" in
    0)    col=$GREEN; txt="PASS" ;;
    SKIP) col=$YELLOW; txt="SKIP" ;;
    *)    col=$RED;   txt="FAIL" ;;
  esac
  printf '  %-55s %s%s%s  (%s)\n' "${STEPS_LABEL[$i]}" "$col" "$txt" "$NC" "${STEPS_SECS[$i]}"
done
TOTAL=$((SECONDS - T_START))
printf '\n'
if (( FAILS == 0 )); then
  printf '%sALL GATES PASSED%s — total %ss\n' "$GREEN$BOLD" "$NC" "$TOTAL"
  exit 0
else
  printf '%s%d GATE(S) FAILED%s — total %ss\n' "$RED$BOLD" "$FAILS" "$NC" "$TOTAL"
  exit 1
fi
