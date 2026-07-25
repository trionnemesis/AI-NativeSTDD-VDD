#!/usr/bin/env bash
# init.sh — STDD×VDD 環境一鍵初始化腳本
# 執行後，當前目錄會有完整的 STDD×VDD 治理層結構
# 使用方式：bash setup/init.sh [target-project-dir] [path-policy-json]
set -e

TARGET="${1:-.}"
POLICY_SOURCE="${2:-}"
SCRIPT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
mkdir -p "$TARGET"
TARGET_DIR="$(cd "$TARGET" && pwd -P)"

echo "=== STDD×VDD Init ==="
echo "Target: $TARGET_DIR"
echo "Template: $SCRIPT_DIR"
echo ""

# P1: Path policy + 目錄結構
echo "[P1] 建立 path policy 與治理目錄..."
if [ -L "$TARGET/.vdd" ] || [ -L "$TARGET/.claude" ] || \
   [ -L "$TARGET/.claude/hooks" ]; then
  echo "  ERROR: target control directories 不得為 symlink" >&2
  exit 1
fi
mkdir -p "$TARGET/.vdd"

POLICY_DEST="$TARGET_DIR/.vdd/path-policy.json"
POLICY_TEMP="$TARGET_DIR/.vdd/.path-policy.$$.tmp"
POLICY_CANDIDATE="$POLICY_DEST"
POLICY_MESSAGE="Existing .vdd/path-policy.json preserved"

if [ -L "$POLICY_DEST" ]; then
  echo "  ERROR: $POLICY_DEST 不得為 symlink" >&2
  exit 1
fi

if [ -n "$POLICY_SOURCE" ]; then
  if [ ! -f "$POLICY_SOURCE" ]; then
    echo "  ERROR: path policy 不存在: $POLICY_SOURCE" >&2
    exit 1
  fi
  POLICY_SOURCE_DIR="$(cd "$(dirname "$POLICY_SOURCE")" && pwd -P)"
  POLICY_SOURCE_PATH="$POLICY_SOURCE_DIR/$(basename "$POLICY_SOURCE")"
  if [ "$POLICY_SOURCE_PATH" = "$POLICY_DEST" ]; then
    POLICY_MESSAGE="Existing path policy validated in place"
  else
    cp "$POLICY_SOURCE_PATH" "$POLICY_TEMP"
    POLICY_CANDIDATE="$POLICY_TEMP"
    POLICY_MESSAGE="Copied custom path policy"
  fi
elif [ -f "$POLICY_DEST" ]; then
  POLICY_MESSAGE="Existing .vdd/path-policy.json preserved"
else
  cp "$SCRIPT_DIR/setup/templates/path-policy.json" "$POLICY_TEMP"
  POLICY_CANDIDATE="$POLICY_TEMP"
  POLICY_MESSAGE="Installed compatibility path policy"
fi

if ! python3 -m json.tool "$POLICY_CANDIDATE" >/dev/null; then
  rm -f "$POLICY_TEMP"
  echo "  ERROR: .vdd/path-policy.json 不是有效 JSON" >&2
  exit 1
fi
if ! (cd "$TARGET_DIR" && CLAUDE_PROJECT_DIR="$TARGET_DIR" \
  python3 "$SCRIPT_DIR/.claude/hooks/path_policy.py" \
  --policy "$POLICY_CANDIDATE" >/dev/null); then
  rm -f "$POLICY_TEMP"
  echo "  ERROR: .vdd/path-policy.json schema 驗證失敗" >&2
  exit 1
fi
if [ "$POLICY_CANDIDATE" = "$POLICY_TEMP" ]; then
  mv -f "$POLICY_TEMP" "$POLICY_DEST"
fi
echo "  $POLICY_MESSAGE"

if cmp -s "$POLICY_DEST" "$SCRIPT_DIR/setup/templates/path-policy.json"; then
  COMPATIBILITY_POLICY=1
  mkdir -p "$TARGET/specs/domain"
  mkdir -p "$TARGET/specs/features"
  mkdir -p "$TARGET/specs/contracts/api"
  mkdir -p "$TARGET/specs/contracts/ui"
  mkdir -p "$TARGET/specs/quality"
  mkdir -p "$TARGET/specs/decisions"
  mkdir -p "$TARGET/specs/traceability"
  mkdir -p "$TARGET/.vdd/red"
  echo "  Compatibility layout created"
else
  COMPATIBILITY_POLICY=0
  echo "  Custom layout preserved; implementation/spec/test directories are not synthesized"
fi

mkdir -p "$TARGET/.claude/hooks"
mkdir -p "$TARGET/.claude/agents"
mkdir -p "$TARGET/changes"

# 初始化 phase 狀態
if [ ! -f "$TARGET/.vdd/phase" ]; then
  echo "INIT" > "$TARGET/.vdd/phase"
  echo "  Created .vdd/phase = INIT"
fi

# 初始化 admit queue
if [ ! -f "$TARGET/.vdd/admit-queue" ]; then
  touch "$TARGET/.vdd/admit-queue"
fi

echo "[P1] 完成"

# P1b: Agent 入口文件
echo "[P1b] 複製 agent 入口文件..."
if [ "$TARGET_DIR" = "$SCRIPT_DIR" ]; then
  echo "  Template repo 內執行，文件已在正確位置"
else
  if [ ! -f "$TARGET/AGENTS.md" ] && [ -f "$SCRIPT_DIR/AGENTS.md" ]; then
    cp "$SCRIPT_DIR/AGENTS.md" "$TARGET/AGENTS.md"
    echo "  Copied AGENTS.md"
  elif [ -f "$TARGET/AGENTS.md" ]; then
    cp "$SCRIPT_DIR/AGENTS.md" "$TARGET/AGENTS.stdd-vdd.md"
    echo "  AGENTS.md 已存在，Copied AGENTS.stdd-vdd.md for merge"
  fi

  if [ ! -f "$TARGET/CLAUDE.md" ] && [ -f "$SCRIPT_DIR/CLAUDE.md" ]; then
    cp "$SCRIPT_DIR/CLAUDE.md" "$TARGET/CLAUDE.md"
    echo "  Copied CLAUDE.md"
  elif [ -f "$TARGET/CLAUDE.md" ]; then
    cp "$SCRIPT_DIR/CLAUDE.md" "$TARGET/CLAUDE.stdd-vdd.md"
    echo "  CLAUDE.md 已存在，Copied CLAUDE.stdd-vdd.md for merge"
  fi

  if [ -d "$SCRIPT_DIR/docs" ]; then
    mkdir -p "$TARGET/docs"
    cp "$SCRIPT_DIR/docs/"*.md "$TARGET/docs/"
    echo "  Copied docs/*.md"
  fi

  if [ -d "$SCRIPT_DIR/governance" ]; then
    mkdir -p "$TARGET/governance" "$TARGET/generated" "$TARGET/scripts"
    cp -R "$SCRIPT_DIR/governance/." "$TARGET/governance/"
    cp "$SCRIPT_DIR/generated/notion-canonical-view.md" "$TARGET/generated/"
    cp "$SCRIPT_DIR/scripts/governance.py" "$TARGET/scripts/"
    cp "$SCRIPT_DIR/requirements-governance.txt" "$TARGET/"
    echo "  Copied governance shadow, generated view, validation script, and requirements"
  fi

  mkdir -p "$TARGET/setup/templates"
  cp "$SCRIPT_DIR/setup/AGENT_SETUP_PROTOCOL.md" "$TARGET/setup/"
  cp "$SCRIPT_DIR/setup/templates/"*.json "$TARGET/setup/templates/"
  echo "  Copied setup/AGENT_SETUP_PROTOCOL.md and templates"
fi
echo "[P1b] 完成"

# P2: Hook Scripts
echo "[P2] 複製 hook scripts..."
if [ "$TARGET_DIR" = "$SCRIPT_DIR" ]; then
  echo "  Template repo 內執行，hooks 已在正確位置"
elif [ -d "$SCRIPT_DIR/.claude/hooks" ]; then
  cp "$SCRIPT_DIR/.claude/hooks/"*.py "$TARGET/.claude/hooks/"
  chmod +x "$TARGET/.claude/hooks/"*.py
  echo "  Copied 6 hook entrypoints + path_policy.py"
else
  echo "  WARN: $SCRIPT_DIR/.claude/hooks 不存在，跳過"
fi
echo "[P2] 完成"

# P3: Hook 設定
echo "[P3] 複製 settings.json..."
if [ "$TARGET_DIR" = "$SCRIPT_DIR" ]; then
  echo "  Template repo 內執行，settings.json 已在正確位置"
elif [ ! -f "$TARGET/.claude/settings.json" ] && [ -f "$SCRIPT_DIR/.claude/settings.json" ]; then
  cp "$SCRIPT_DIR/.claude/settings.json" "$TARGET/.claude/settings.json"
  echo "  Copied settings.json"
elif [ -f "$TARGET/.claude/settings.json" ]; then
  echo "  settings.json 已存在，跳過"
fi
echo "[P3] 完成"

# P4: RED verifier subagent
echo "[P4] 複製 red-verifier subagent..."
if [ "$TARGET_DIR" = "$SCRIPT_DIR" ]; then
  echo "  Template repo 內執行，red-verifier.md 已在正確位置"
elif [ ! -f "$TARGET/.claude/agents/red-verifier.md" ] && \
   [ -f "$SCRIPT_DIR/.claude/agents/red-verifier.md" ]; then
  cp "$SCRIPT_DIR/.claude/agents/red-verifier.md" "$TARGET/.claude/agents/"
  echo "  Copied red-verifier.md"
elif [ -f "$TARGET/.claude/agents/red-verifier.md" ]; then
  echo "  red-verifier.md 已存在，跳過"
else
  echo "  ERROR: red-verifier.md missing" >&2
  exit 1
fi
echo "[P4] 完成"

# P5: Python 依賴
echo "[P5] 準備 verification command 依賴..."
if python3 -m pip --version >/dev/null 2>&1; then
  python3 -m pip install -q 'pytest>=8.3,<10.0' pytest-cov 'ruff>=0.12,<1.0' mutmut
  echo "  Installed verification tools: pytest pytest-cov ruff mutmut"
else
  echo "  WARN: python3 的 pip 不可用，請以同一 interpreter 手動安裝 verification tools"
fi
echo "[P5] 完成"

# P0 提示（需管理員）
echo ""
echo "[P0] managed-settings.json（需管理員）:"
MANAGED_PATH="/Library/Application Support/ClaudeCode/managed-settings.json"
if [ -f "$MANAGED_PATH" ]; then
  echo "  PASS: $MANAGED_PATH 已存在"
else
  echo "  MISSING: 請執行以下命令（需 sudo）："
  echo "  sudo mkdir -p \"/Library/Application Support/ClaudeCode\""
  echo "  sudo cp \"$SCRIPT_DIR/setup/templates/managed-settings.json\" \\"
  echo "    \"/Library/Application Support/ClaudeCode/managed-settings.json\""
fi

# P6 smoke test
echo ""
echo "[P6] Smoke test..."
if [ -f "$TARGET/.claude/hooks/pre_impl_gate.py" ]; then
  SMOKE_ROOT=$(python3 -c \
    'import json,sys; data=json.load(open(sys.argv[1])); print(data.get("implementation_roots", ["src"])[0])' \
    "$TARGET/.vdd/path-policy.json")
  SMOKE_PAYLOAD=$(python3 -c \
    'import json,sys; print(json.dumps({"tool_name":"Edit","tool_input":{"file_path":sys.argv[1] + "/test.py"}}))' \
    "$SMOKE_ROOT")
  RESULT=$(cd "$TARGET" && printf '%s\n' "$SMOKE_PAYLOAD" | \
    CLAUDE_PROJECT_DIR="$TARGET_DIR" \
    python3 .claude/hooks/pre_impl_gate.py 2>&1; echo "EXIT:$?")
  if echo "$RESULT" | grep -q "EXIT:2" && echo "$RESULT" | grep -q "BLOCKED \[GATE:SPEC\]"; then
    echo "  PASS: pre_impl_gate.py 正確 block $SMOKE_ROOT/ 寫入"
  else
    echo "  WARN: Smoke test 未如預期，請手動確認"
  fi
fi
echo "[P6] 完成"

echo ""
echo "=== 初始化完成 ==="
echo ""
echo "下一步："
echo "  1. 在 Claude Code 中輸入："
echo "     '閱讀 setup/AGENT_SETUP_PROTOCOL.md 並執行 Confirm Mode'"
echo "  2. 若 P0 失敗，先安裝 managed-settings.json（需 sudo）"
echo ""
echo "目前 .vdd/phase = $(cat $TARGET/.vdd/phase)"
