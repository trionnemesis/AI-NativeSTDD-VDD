#!/usr/bin/env python3
"""Validate and render the opt-in Codex/Hermes adapter mapping."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
ADAPTER = ROOT / "integrations" / "codex" / "adapter.yaml"
FROZEN_PIPELINE = ["GATE:SPEC", "GATE:RED", "GATE:GREEN", "GATE:VDD", "GATE:DEPLOY"]
REQUIRED_LANES = {"L1-bugfix", "L2-feature", "L3-research-decision", "L4-incident-RCA"}


class AdapterValidationError(RuntimeError):
    """Raised when the adapter violates repository governance boundaries."""


def load_yaml(path: Path) -> Any:
    with path.open(encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AdapterValidationError(message)


def validate_adapter(adapter: dict[str, Any], root: Path = ROOT) -> dict[str, Any]:
    manifest = load_yaml(root / "governance" / "manifest.yaml")
    profiles = load_yaml(root / "governance" / "profiles" / "change.yaml")
    authority = manifest["authority"]
    require(adapter.get("schema_version") == "1.0.0", "unsupported adapter schema")
    require(adapter.get("adapter_id") == "ADAPTER:CODEX-HERMES", "adapter id mismatch")
    require(adapter.get("status") == "NON_AUTHORITATIVE_OPT_IN", "adapter must remain opt-in and non-authoritative")
    require(adapter["runtime"]["name"] == "Codex", "runtime must be Codex")
    require(adapter["runtime"]["independent_context_command"] == "codex exec", "Codex review command must use codex exec")
    adapter_authority = adapter["authority"]
    require(adapter_authority["manifest"] == "governance/manifest.yaml", "authority manifest path changed")
    require(adapter_authority["required_current"] == authority["current"], "adapter authority state is stale")
    require(adapter_authority["required_repository_state"] == authority["repository_state"], "adapter repository state is stale")
    require(manifest["canonical_pipeline"] == FROZEN_PIPELINE, "repository manifest changed the frozen five-gate pipeline")
    require(adapter["canonical_pipeline"] == FROZEN_PIPELINE, "adapter changed the frozen five-gate pipeline")
    require(set(adapter["lanes"]) == REQUIRED_LANES | {"L5-long-task-overlay"}, "adapter lane set is incomplete or unexpected")
    known_profiles = set(profiles["profiles"])
    for lane_name, lane in adapter["lanes"].items():
        require(isinstance(lane.get("delivery_gates"), list), f"{lane_name} delivery_gates must be a list")
        require(set(lane["delivery_gates"]).issubset(FROZEN_PIPELINE), f"{lane_name} references an unknown or non-canonical gate")
        if lane_name == "L5-long-task-overlay":
            require(lane.get("overlay_only") is True, "L5 must remain an overlay")
            require(not lane["delivery_gates"], "L5 cannot enter the delivery pipeline")
        else:
            profile = lane.get("change_profile")
            require(profile is None or profile in known_profiles, f"{lane_name} references unknown change profile {profile!r}")
    review = adapter["cross_cutting"]["independent_review"]
    require(review["command"] == "codex exec" and review["reviewers"] == 4, "independent review mapping is incomplete")
    return {
        "adapter_id": adapter["adapter_id"],
        "lanes": len(adapter["lanes"]),
        "delivery_lanes": len(REQUIRED_LANES),
        "pipeline_gates": len(adapter["canonical_pipeline"]),
        "authority": authority["current"],
    }


def render(adapter: dict[str, Any]) -> str:
    lines = [
        "# Codex Adapter Mapping",
        "",
        "> GENERATED FROM `integrations/codex/adapter.yaml`; this surface is non-authoritative.",
        "",
        "| Hermes lane | Change profile | Delivery gates |",
        "|---|---|---|",
    ]
    for name, lane in adapter["lanes"].items():
        profile = "overlay only" if lane.get("overlay_only") else lane.get("change_profile") or "decision/RCA artifact"
        gates = " → ".join(f"`{gate}`" for gate in lane["delivery_gates"]) or "none"
        lines.append(f"| `{name}` | `{profile}` | {gates} |")
    lines.extend(["", "Codex independent review uses `codex exec` in fresh contexts; L5 remains an overlay.", ""])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("validate", "render"))
    parser.add_argument("--json", action="store_true", help="emit validation summary as JSON")
    args = parser.parse_args()
    try:
        adapter = load_yaml(ADAPTER)
        summary = validate_adapter(adapter)
    except (OSError, KeyError, TypeError, AdapterValidationError) as error:
        parser.error(str(error))
    if args.command == "render":
        print(render(adapter), end="")
    elif args.json:
        print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    else:
        print(f"VALID: {summary['adapter_id']} lanes={summary['lanes']} pipeline_gates={summary['pipeline_gates']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
