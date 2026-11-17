#!/bin/bash
# 이 스킬 전용 파이썬 환경(.venv)으로 인자를 그대로 실행한다.
#
#   scripts/run.sh scripts/generate.py "<prompt>" --model nano-banana-2 --out .
#
# 왜 있나: 맥의 기본 python3 는 Homebrew 업그레이드 때마다 버전이 바뀌고(3.14 → 3.15),
# 패키지는 버전별로 따로 설치돼 있어서 기본 python3 로 부르면 어느 날 갑자기
# ModuleNotFoundError 가 난다(2026-11-17 실제 발생). 스킬이 자기 환경을 들고 다니면
# 기본 파이썬이 무엇이든 상관없다.
#
# .venv 가 없거나, 깨졌거나(만든 파이썬이 지워짐), requirements.txt 가 바뀌었으면
# 스스로 다시 만든다. 1분 안팎 걸리고 진행 상황은 stderr 로만 알린다(stdout 은 스크립트 결과 전용).
set -euo pipefail

SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV="$SKILL_DIR/.venv"
PY="$VENV/bin/python"
REQ="$SKILL_DIR/requirements.txt"
STAMP="$VENV/.ready"
CHECK_IMPORT="import google.genai"

say() { echo "[run.sh] $*" >&2; }

ready() { [ -x "$PY" ] && [ "$STAMP" -nt "$REQ" ] && "$PY" -c "" 2>/dev/null; }

# 후보: 기본 python3 먼저, 그다음 설치된 python3.N 을 높은 버전부터.
candidates() {
  command -v python3 2>/dev/null || true
  { echo "$PATH" | tr ':' '\n'; echo /opt/homebrew/bin; echo /usr/local/bin; } |
    while IFS= read -r d; do
      [ -n "$d" ] && ls "$d"/python3.[0-9]* 2>/dev/null || true
    done |
    grep -E '/python3\.[0-9]+$' |
    awk -F'python3.' '!seen[$0]++ { print $NF " " $0 }' | sort -rn | cut -d' ' -f2-
}

build() {
  local base
  while IFS= read -r base <&3; do
    [ -x "$base" ] || continue
    "$base" -c 'import sys; sys.exit(sys.version_info < (3, 10))' 2>/dev/null || continue
    say "전용 환경을 만듭니다: $("$base" --version 2>&1) ($base)"
    rm -rf "$VENV"
    if "$base" -m venv "$VENV" >&2 &&
       "$PY" -m pip install --quiet --disable-pip-version-check -r "$REQ" >&2 &&
       "$PY" -c "$CHECK_IMPORT" >&2; then
      touch "$STAMP"
      say "준비 완료."
      return 0
    fi
    say "이 파이썬으로는 실패했습니다. 다음 후보로 넘어갑니다."
  done 3< <(candidates)
  rm -rf "$VENV"
  say "전용 환경을 만들지 못했습니다. Python 3.10 이상과 인터넷 연결이 필요합니다."
  return 1
}

ready || build
exec "$PY" "$@"
