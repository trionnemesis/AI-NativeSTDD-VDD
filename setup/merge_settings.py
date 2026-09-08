#!/usr/bin/env python3
"""Merge missing hook registrations from the template into an existing settings.json.

複製 hook 檔案不等於註冊。既有安裝重跑 init.sh 時，settings.json 先前是直接跳過，
新增的 entrypoint 因此永遠不會被呼叫，CM-08 也必然 FAIL。

本工具只做加法：補上缺少的 matcher 與 hook command，不改動、不移除既有設定。
"""
import argparse
import json
import sys
from pathlib import Path


def hook_commands(entry):
    return [hook.get("command") for hook in entry.get("hooks", [])]


def merge_event(target_entries, template_entries):
    """Return the number of additions made to target_entries."""
    added = 0
    for template_entry in template_entries:
        matcher = template_entry.get("matcher")
        existing = next(
            (
                entry
                for entry in target_entries
                if entry.get("matcher") == matcher
            ),
            None,
        )
        if existing is None:
            target_entries.append(json.loads(json.dumps(template_entry)))
            added += 1
            continue
        present = set(hook_commands(existing))
        for hook in template_entry.get("hooks", []):
            if hook.get("command") not in present:
                existing.setdefault("hooks", []).append(json.loads(json.dumps(hook)))
                added += 1
    return added


def ensure_local(target_path: Path) -> None:
    """Refuse to write through a symlinked settings file.

    `.claude/settings.json`（或其父目錄）若是 symlink，write_text 會寫穿到 target
    以外的檔案，把別的專案或全域設定改掉。init.sh 已拒絕 symlink 化的控制目錄，
    這裡補上檔案本身。
    """
    project = target_path.parent.parent
    if target_path.is_symlink():
        raise ValueError(f"{target_path} is a symlink; refusing to write through it")
    try:
        target_path.resolve().relative_to(project.resolve())
    except (OSError, RuntimeError, ValueError) as exc:
        raise ValueError(f"{target_path} resolves outside {project}") from exc


def merge(target_path: Path, template_path: Path) -> int:
    ensure_local(target_path)
    target = json.loads(target_path.read_text(encoding="utf-8"))
    template = json.loads(template_path.read_text(encoding="utf-8"))
    target_hooks = target.setdefault("hooks", {})
    added = 0
    for event, template_entries in template.get("hooks", {}).items():
        added += merge_event(target_hooks.setdefault(event, []), template_entries)
    if added:
        target_path.write_text(
            json.dumps(target, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
    return added


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("target", type=Path)
    parser.add_argument("template", type=Path)
    arguments = parser.parse_args()
    try:
        added = merge(arguments.target, arguments.template)
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as exc:
        print(f"ERROR: cannot merge settings: {exc}", file=sys.stderr)
        return 1
    print(f"merged {added} missing hook registration(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
