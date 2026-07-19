#!/usr/bin/env python3
"""Reconcile the repository governance shadow with the frozen Notion Archive baseline.

Phase 2 is deliberately non-authoritative: a successful comparison proves that the
repository projection matches the reviewed machine-semantic scope captured from the
Notion Archive. It does not perform authority cutover or prove runtime enforcement.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[1]
GOVERNANCE = ROOT / "governance"
BASELINE = GOVERNANCE / "reconciliation" / "notion-archive-baseline.yaml"
REPORT = ROOT / "generated" / "semantic-reconciliation-report.md"


class SemanticReconciliationError(RuntimeError):
    pass


def load_yaml(path: Path) -> Any:
    with path.open(encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SemanticReconciliationError(message)


def assertion_names(assertions: Any) -> list[str]:
    if isinstance(assertions, list):
        values: list[str] = []
        for item in assertions:
            require(isinstance(item, dict) and bool(item.get("check")), "list assertion is missing check")
            values.append(str(item["check"]))
        return values
    if isinstance(assertions, dict):
        return list(assertions)
    raise SemanticReconciliationError("assertions must be a list or mapping")


def extract_repo_semantics(root: Path = ROOT) -> dict[str, Any]:
    governance = root / "governance"
    manifest = load_yaml(governance / "manifest.yaml")
    glossary = load_yaml(governance / "glossary.yaml")
    namespaces = load_yaml(governance / "registries" / "namespaces.yaml")
    system_profiles = load_yaml(governance / "profiles" / "system.yaml")
    change_profiles = load_yaml(governance / "profiles" / "change.yaml")
    applicability = load_yaml(governance / "profiles" / "applicability.yaml")

    gates: dict[str, dict[str, Any]] = {}
    for path in sorted((governance / "gates").glob("*.yaml")):
        gate = load_yaml(path)
        gate_id = gate["gate_id"]
        gates[gate_id] = {
            "scope": gate["scope"],
            "stage": gate["stage"],
            "assertions": assertion_names(gate["assertions"]),
        }

    glossary_projection = {
        entry["stable_id"]: entry["canonical_term"]
        for entry in glossary.values()
    }
    system_projection = {
        name: list(profile.get("concerns", []))
        for name, profile in system_profiles["profiles"].items()
    }

    change_projection: dict[str, dict[str, Any]] = {}
    semantic_fields = (
        "behavior",
        "red_evidence",
        "requirements",
        "tier_rule",
        "low_risk_forbidden_when_touching",
        "default_tier",
        "activation",
    )
    for name, profile in change_profiles["profiles"].items():
        change_projection[name] = {
            field: copy.deepcopy(profile[field])
            for field in semantic_fields
            if field in profile
        }

    non_pipeline = manifest["non_pipeline_gates"]
    return {
        "canonical_pipeline": list(manifest["canonical_pipeline"]),
        "gate_scopes": {
            "canonical_pipeline": list(manifest["canonical_pipeline"]),
            "upstream": list(non_pipeline.get("upstream", [])),
            "auxiliary": list(non_pipeline.get("auxiliary", [])),
        },
        "intentionally_undefined_ids": list(manifest.get("intentionally_undefined_ids", [])),
        "glossary": glossary_projection,
        "namespaces": list(namespaces["namespaces"]),
        "gates": gates,
        "system_profiles": system_projection,
        "change_profiles": change_projection,
        "mandatory_always_on_controls": list(applicability["mandatory_always_on_controls"]),
        "invariants": {
            **copy.deepcopy(manifest["invariants"]),
            "profile_conflict_rule": applicability["resolution"]["conflict_rule"],
        },
    }


def canonicalize(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: canonicalize(value[key]) for key in sorted(value)}
    if isinstance(value, list):
        normalized = [canonicalize(item) for item in value]
        return sorted(normalized, key=lambda item: json.dumps(item, ensure_ascii=False, sort_keys=True))
    return value


def semantic_digest(value: Any) -> str:
    normalized = json.dumps(
        canonicalize(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def compare_values(expected: Any, actual: Any, path: str = "$") -> list[str]:
    diffs: list[str] = []
    if isinstance(expected, dict):
        if not isinstance(actual, dict):
            return [f"{path}: expected mapping, got {type(actual).__name__}"]
        for key in sorted(set(expected) | set(actual)):
            child_path = f"{path}.{key}"
            if key not in expected:
                diffs.append(f"{child_path}: repository-only value {actual[key]!r}")
            elif key not in actual:
                diffs.append(f"{child_path}: missing from repository projection")
            else:
                diffs.extend(compare_values(expected[key], actual[key], child_path))
        return diffs
    if isinstance(expected, list):
        if not isinstance(actual, list):
            return [f"{path}: expected list, got {type(actual).__name__}"]
        if canonicalize(expected) != canonicalize(actual):
            diffs.append(f"{path}: expected {expected!r}, got {actual!r}")
        return diffs
    if expected != actual:
        diffs.append(f"{path}: expected {expected!r}, got {actual!r}")
    return diffs


def compare_contracts(expected: dict[str, Any], actual: dict[str, Any]) -> list[str]:
    diffs: list[str] = []
    if expected["canonical_pipeline"] != actual["canonical_pipeline"]:
        diffs.append(
            f"$.canonical_pipeline: expected {expected['canonical_pipeline']!r}, "
            f"got {actual['canonical_pipeline']!r}"
        )

    expected_rest = copy.deepcopy(expected)
    actual_rest = copy.deepcopy(actual)
    expected_rest.pop("canonical_pipeline", None)
    actual_rest.pop("canonical_pipeline", None)
    diffs.extend(compare_values(expected_rest, actual_rest))
    return diffs


def reconcile(root: Path = ROOT) -> dict[str, Any]:
    baseline = load_yaml(root / "governance" / "reconciliation" / "notion-archive-baseline.yaml")
    expected = baseline["semantic_contract"]
    actual = extract_repo_semantics(root)
    diffs = compare_contracts(expected, actual)

    return {
        "reconciliation_id": baseline["reconciliation_id"],
        "status": "SEMANTIC_MATCH" if not diffs else "SEMANTIC_DRIFT",
        "expected_digest": semantic_digest(expected),
        "actual_digest": semantic_digest(actual),
        "differences": diffs,
        "counts": {
            "glossary_entries": len(actual["glossary"]),
            "namespaces": len(actual["namespaces"]),
            "gates": len(actual["gates"]),
            "system_profiles": len(actual["system_profiles"]),
            "change_profiles": len(actual["change_profiles"]),
            "mandatory_controls": len(actual["mandatory_always_on_controls"]),
        },
        "source": baseline["source"],
    }


def validate_reconciliation(root: Path = ROOT) -> dict[str, Any]:
    result = reconcile(root)
    manifest = load_yaml(root / "governance" / "manifest.yaml")
    authority = manifest["authority"]

    require(authority["current"] == "NOTION_CANONICAL", "Phase 2 must retain Notion authority")
    require(
        authority["repository_state"] == "SHADOW_NON_AUTHORITATIVE",
        "Phase 2 repository must remain non-authoritative",
    )
    require(authority["cutover_decision"] == "pending", "Phase 2 cannot imply cutover")
    require(not result["differences"], "semantic drift: " + "; ".join(result["differences"]))
    require(
        result["expected_digest"] == result["actual_digest"],
        "semantic digests differ despite an empty diff",
    )
    require(
        manifest["cutover_preconditions"]["notion_to_repo_semantic_hash_match"] is True,
        "manifest must record the reviewed Phase 2 semantic match",
    )
    phase2 = manifest.get("semantic_reconciliation", {})
    require(phase2.get("status") == "PASSED_PHASE2", "manifest semantic_reconciliation status is not PASSED_PHASE2")
    require(phase2.get("baseline") == "governance/reconciliation/notion-archive-baseline.yaml", "baseline path mismatch")
    require(phase2.get("report") == "generated/semantic-reconciliation-report.md", "report path mismatch")
    require(phase2.get("authority_unchanged") is True, "Phase 2 must record authority_unchanged=true")
    return result


def render_markdown(root: Path = ROOT) -> str:
    result = reconcile(root)
    status = result["status"]
    source = result["source"]
    counts = result["counts"]
    differences = result["differences"]

    lines = [
        "# Phase 2 Semantic Reconciliation Report",
        "",
        "> **GENERATED FILE — DO NOT EDIT.**",
        "> This report compares the reviewed Notion Archive machine-semantic baseline with the repository governance projection.",
        "> A pass does **not** perform authority cutover and does **not** prove target-runtime enforcement.",
        "",
        f"- Reconciliation: `{result['reconciliation_id']}`",
        f"- Status: **{status}**",
        f"- Notion root: {source['notion_root']}",
        f"- Human handbook: {source['human_handbook']}",
        f"- Archive: {source['archive']}",
        f"- Pre-refactor snapshot: {source['pre_refactor_snapshot']}",
        f"- Baseline digest: `{result['expected_digest']}`",
        f"- Repository digest: `{result['actual_digest']}`",
        "",
        "## Compared semantic surface",
        "",
        "| Surface | Count |",
        "|---|---:|",
        f"| Glossary entries | {counts['glossary_entries']} |",
        f"| Namespaces | {counts['namespaces']} |",
        f"| Gate contracts | {counts['gates']} |",
        f"| System profiles | {counts['system_profiles']} |",
        f"| Change profiles | {counts['change_profiles']} |",
        f"| Mandatory always-on controls | {counts['mandatory_controls']} |",
        "",
        "The comparison covers the fixed five-gate pipeline, upstream/auxiliary Gate boundaries, intentionally undefined IDs,",
        "Stable ID canonical terms, namespaces, Gate scope/stage/assertion keys, System/Change Profiles, applicability controls,",
        "and frozen authority/pipeline invariants. Human narrative wording, examples, diagrams, dated assessments, and ledger prose",
        "are intentionally excluded from the machine semantic digest.",
        "",
        "## Classification result",
        "",
    ]
    if differences:
        lines.append("Semantic drift was detected:")
        lines.append("")
        for difference in differences:
            lines.append(f"- `{difference}`")
    else:
        lines.extend([
            "- `equivalent_formatting`: normalized machine semantics match.",
            "- `notion_only_human_explanation`: excluded from the machine digest by policy.",
            "- `repository_omission`: none.",
            "- `repository_drift`: none.",
            "- `intentional_supersession`: none recorded in Phase 2.",
        ])

    lines.extend([
        "",
        "## Authority boundary",
        "",
        "- Current authority remains `NOTION_CANONICAL`.",
        "- Repository state remains `SHADOW_NON_AUTHORITATIVE`.",
        "- Cutover decision remains `pending`.",
        "- Phase 3 rollback dry-run and observation-window work is still required.",
        "- Explicit Methodology Warden approval is still required before Phase 4 authority cutover.",
        "",
    ])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("validate")
    render_parser = subparsers.add_parser("render")
    render_parser.add_argument("--check", action="store_true")

    args = parser.parse_args()
    try:
        if args.command == "validate":
            result = validate_reconciliation(ROOT)
            print(json.dumps(result, ensure_ascii=False, sort_keys=True))
            return 0

        content = render_markdown(ROOT)
        if args.check:
            require(REPORT.exists(), f"{REPORT.relative_to(ROOT)} is missing")
            require(REPORT.read_text(encoding="utf-8") == content, "semantic reconciliation report is stale")
        else:
            REPORT.parent.mkdir(parents=True, exist_ok=True)
            REPORT.write_text(content, encoding="utf-8")
        print(f"semantic reconciliation report: {reconcile(ROOT)['status']}")
        return 0
    except SemanticReconciliationError as error:
        print(f"semantic reconciliation failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
