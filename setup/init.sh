#!/usr/bin/env bash
# init.sh — STDD×VDD 環境一鍵初始化腳本
# 執行後，當前目錄會有完整的 STDD×VDD 治理層結構
# 使用方式：bash setup/init.sh [target-project-dir]
set -e

TARGET="${1:-.}"
SCRIPT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
mkdir -p "$TARGET"
TARGET_DIR="$(cd "$TARGET" && pwd)"

echo "=== STDD×VDD Init ==="
echo "Target: $TARGET_DIR"
echo "Template: $SCRIPT_DIR"
echo ""

# P1: 目錄結構
echo "[P1] 建立目錄結構..."
mkdir -p "$TARGET/specs/domain"
mkdir -p "$TARGET/specs/features"
mkdir -p "$TARGET/specs/contracts/api"
mkdir -p "$TARGET/specs/contracts/ui"
mkdir -p "$TARGET/specs/quality"
mkdir -p "$TARGET/specs/decisions"
mkdir -p "$TARGET/specs/traceability"
mkdir -p "$TARGET/.vdd/red"
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
  echo "  Copied 6 hook scripts"
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

# P4: Subagent
echo "[P4] 複製 red-verifier subagent..."
if [ "$TARGET_DIR" = "$SCRIPT_DIR" ]; then
  echo "  Template repo 內執行，red-verifier.md 已在正確位置"
elif [ ! -f "$TARGET/.claude/agents/red-verifier.md" ] && \
   [ -f "$SCRIPT_DIR/.claude/agents/red-verifier.md" ]; then
  cp "$SCRIPT_DIR/.claude/agents/red-verifier.md" "$TARGET/.claude/agents/"
  echo "  Copied red-verifier.md"
elif [ -f "$TARGET/.claude/agents/red-verifier.md" ]; then
  echo "  red-verifier.md 已存在，跳過"
fi
echo "[P4] 完成"

# P5: Python 依賴
echo "[P5] 安裝 Python 依賴..."
if command -v pip3 &>/dev/null; then
  pip3 install -q pytest pytest-cov ruff mutmut
  echo "  Installed: pytest, pytest-cov, ruff, mutmut"
else
  echo "  WARN: pip3 不可用，請手動安裝: pip install pytest pytest-cov ruff mutmut"
fi
echo "[P5] 完成"

# P0 提示（需管理員）
echo ""
echo "[P0] managed-settings.json（需管理員，手動執行）:"
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
  RESULT=$(echo '{"tool_name":"Edit","tool_input":{"file_path":"src/test.py"}}' | \
    python3 "$TARGET/.claude/hooks/pre_impl_gate.py" 2>&1; echo "EXIT:$?")
  if echo "$RESULT" | grep -q "EXIT:2"; then
    echo "  PASS: pre_impl_gate.py 正確 block src/ 寫入"
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
