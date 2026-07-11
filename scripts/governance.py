#!/usr/bin/env python3
"""Validate and render the MCR:2026:004 repository shadow.

The script deliberately does not change authority. The manifest must remain in
NOTION_CANONICAL / SHADOW_NON_AUTHORITATIVE state until a later explicit
cutover decision.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any, Iterable

import yaml
from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[1]
GOVERNANCE = ROOT / "governance"
GENERATED_VIEW = ROOT / "generated" / "notion-canonical-view.md"
FROZEN_PIPELINE = [
    "GATE:SPEC",
    "GATE:RED",
    "GATE:GREEN",
    "GATE:VDD",
    "GATE:DEPLOY",
]
ID_REFERENCE = re.compile(r"\b(?:TERM|GATE):[A-Z0-9][A-Z0-9_-]*\b")


class GovernanceValidationError(RuntimeError):
    pass


def load_yaml(path: Path) -> Any:
    with path.open(encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def load_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise GovernanceValidationError(message)


def validate_schema(instance: Any, schema_path: Path, label: str) -> None:
    schema = load_json(schema_path)
    Draft202012Validator.check_schema(schema)
    errors = sorted(
        Draft202012Validator(schema).iter_errors(instance),
        key=lambda item: tuple(str(part) for part in item.path),
    )
    if errors:
        rendered = "; ".join(
            f"{'.'.join(str(part) for part in error.path) or '<root>'}: {error.message}"
            for error in errors
        )
        raise GovernanceValidationError(f"{label} failed {schema_path.name}: {rendered}")


def iter_strings(value: Any) -> Iterable[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for key, child in value.items():
            yield from iter_strings(key)
            yield from iter_strings(child)
    elif isinstance(value, list):
        for child in value:
            yield from iter_strings(child)


def validate_pipeline_contract(manifest: dict[str, Any], registry: dict[str, Any]) -> None:
    pipeline = manifest.get("canonical_pipeline")
    require(pipeline == FROZEN_PIPELINE, f"canonical pipeline changed: {pipeline!r}")
    registry_pipeline = [entry["id"] for entry in registry.get("gates", [])]
    require(registry_pipeline == FROZEN_PIPELINE, f"gate registry order changed: {registry_pipeline!r}")
    non_pipeline = manifest.get("non_pipeline_gates", {})
    excluded = set(non_pipeline.get("upstream", [])) | set(non_pipeline.get("auxiliary", []))
    require(not excluded.intersection(pipeline), "upstream or auxiliary gate entered the five-gate pipeline")
    require("GATE:ADMIT" in excluded, "GATE:ADMIT must remain upstream")
    require("GATE:REGRESSION" in excluded, "GATE:REGRESSION must remain auxiliary")


def canonical_paths(root: Path = ROOT) -> list[Path]:
    governance = root / "governance"
    paths = [governance / "glossary.yaml"]
    paths.extend(sorted((governance / "registries").glob("*.yaml")))
    paths.extend(sorted((governance / "gates").glob("*.yaml")))
    paths.extend(sorted((governance / "profiles").glob("*.yaml")))
    return paths


def bundle_digest(root: Path = ROOT) -> str:
    digest = hashlib.sha256()
    for path in canonical_paths(root):
        relative = path.relative_to(root).as_posix()
        normalized = json.dumps(load_yaml(path), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(normalized.encode("utf-8"))
        digest.update(b"\0")
    return digest.hexdigest()


def validate_repo(root: Path = ROOT) -> dict[str, Any]:
    governance = root / "governance"
    manifest = load_yaml(governance / "manifest.yaml")
    glossary = load_yaml(governance / "glossary.yaml")
    namespaces = load_yaml(governance / "registries" / "namespaces.yaml")
    registry = load_yaml(governance / "registries" / "gates.yaml")

    schema_dir = governance / "schemas"
    validate_schema(manifest, schema_dir / "manifest.schema.json", "manifest")
    validate_schema(glossary, schema_dir / "glossary.schema.json", "glossary")
    validate_schema(namespaces, schema_dir / "namespace-registry.schema.json", "namespace registry")

    authority = manifest.get("authority", {})
    require(authority.get("current") == "NOTION_CANONICAL", "shadow phase must retain Notion authority")
    require(authority.get("repository_state") == "SHADOW_NON_AUTHORITATIVE", "repository must remain non-authoritative")
    require(authority.get("cutover_decision") == "pending", "cutover cannot be implied by repository files")
    validate_pipeline_contract(manifest, registry)

    require(isinstance(glossary, dict) and glossary, "glossary must be a non-empty mapping")
    stable_ids: list[str] = []
    for key, term in glossary.items():
        require(isinstance(term, dict), f"glossary entry {key} must be a mapping")
        for field in ("stable_id", "canonical_term", "operational_meaning"):
            require(bool(term.get(field)), f"glossary entry {key} is missing {field}")
        stable_ids.append(term["stable_id"])
    require(len(stable_ids) == len(set(stable_ids)), "glossary Stable IDs must be unique")

    namespace_names = set(namespaces.get("namespaces", {}))
    for stable_id in stable_ids:
        require(stable_id.split(":", 1)[0] in namespace_names, f"unregistered namespace for {stable_id}")

    gate_files: dict[str, dict[str, Any]] = {}
    for path in sorted((governance / "gates").glob("*.yaml")):
        gate = load_yaml(path)
        validate_schema(gate, schema_dir / "gate.schema.json", path.name)
        for field in ("gate_id", "scope", "stage", "assertions"):
            require(field in gate, f"{path.name} is missing {field}")
        gate_id = gate["gate_id"]
        require(gate_id not in gate_files, f"duplicate gate contract {gate_id}")
        gate_files[gate_id] = gate

    registered_gate_ids = {
        entry["id"]
        for section in ("gates", "upstream_gates", "auxiliary_gates")
        for entry in registry.get(section, [])
    }
    require(set(gate_files) == registered_gate_ids, "gate files and Gate Registry differ")
    for gate_id in FROZEN_PIPELINE:
        require(gate_files[gate_id]["scope"] == "canonical_pipeline", f"{gate_id} has incorrect scope")
    require(gate_files["GATE:ADMIT"]["scope"] == "upstream", "GATE:ADMIT must remain upstream")
    require(gate_files["GATE:REGRESSION"]["scope"] == "auxiliary", "GATE:REGRESSION must remain auxiliary")

    system_profiles = load_yaml(governance / "profiles" / "system.yaml")
    change_profiles = load_yaml(governance / "profiles" / "change.yaml")
    applicability = load_yaml(governance / "profiles" / "applicability.yaml")
    validate_schema(system_profiles, schema_dir / "profile.schema.json", "system profiles")
    validate_schema(change_profiles, schema_dir / "profile.schema.json", "change profiles")
    require(system_profiles.get("stable_id") == "TERM:SYSTEM-PROFILE", "system profile Stable ID mismatch")
    require(change_profiles.get("stable_id") == "TERM:CHANGE-PROFILE", "change profile Stable ID mismatch")
    require(
        set(change_profiles.get("profiles", {}))
        == {"FEATURE", "DEFECT", "REFACTOR", "DEPENDENCY", "DOC_CONFIG", "MIGRATION", "EMERGENCY"},
        "change profile set differs from Notion page 24",
    )
    require(bool(applicability.get("mandatory_always_on_controls")), "mandatory controls cannot be empty")

    intentionally_undefined = set(manifest.get("intentionally_undefined_ids", []))
    require(
        not intentionally_undefined.intersection(registered_gate_ids),
        "an intentionally undefined ID was registered",
    )
    known_ids = set(stable_ids) | registered_gate_ids | intentionally_undefined
    unresolved: set[str] = set()
    for path in canonical_paths(root):
        for text in iter_strings(load_yaml(path)):
            for reference in ID_REFERENCE.findall(text):
                if reference not in known_ids:
                    unresolved.add(reference)
    require(not unresolved, f"unresolved TERM/GATE references: {sorted(unresolved)}")

    schema_files = sorted((governance / "schemas").glob("*.schema.json"))
    require(bool(schema_files), "schema files are missing")
    for path in schema_files:
        schema = load_json(path)
        require(schema.get("$schema") == "https://json-schema.org/draft/2020-12/schema", f"invalid schema declaration in {path.name}")

    return {
        "terms": len(glossary),
        "gates": len(gate_files),
        "pipeline_gates": len(FROZEN_PIPELINE),
        "system_profiles": len(system_profiles["profiles"]),
        "change_profiles": len(change_profiles["profiles"]),
        "bundle_sha256": bundle_digest(root),
    }


def md_cell(value: Any) -> str:
    if isinstance(value, list):
        value = ", ".join(str(item) for item in value)
    return " ".join(str(value).split()).replace("|", "\\|")


def render_markdown(root: Path = ROOT) -> str:
    governance = root / "governance"
    manifest = load_yaml(governance / "manifest.yaml")
    glossary = load_yaml(governance / "glossary.yaml")
    registry = load_yaml(governance / "registries" / "gates.yaml")
    system_profiles = load_yaml(governance / "profiles" / "system.yaml")
    change_profiles = load_yaml(governance / "profiles" / "change.yaml")
    digest = bundle_digest(root)

    lines = [
        "# Generated Canonical View — STDD × VDD",
        "",
        "> **GENERATED FILE — DO NOT EDIT.** Source: `governance/**/*.yaml`.",
        f"> Authority: **{manifest['authority']['current']}**; repository state: **{manifest['authority']['repository_state']}**.",
        f"> Source snapshot: {manifest['snapshot_date']} · MCR: `{manifest['mcr_id']}` · bundle SHA-256: `{digest}`.",
        "",
        "## Five-gate canonical pipeline",
        "",
        " → ".join(f"`{gate}`" for gate in manifest["canonical_pipeline"]),
        "",
        "`GATE:ADMIT` is upstream. `GATE:REGRESSION` is auxiliary. Neither is a sixth pipeline gate.",
        "",
        "| Gate | Stage | Contract |",
        "|---|---|---|",
    ]
    for gate in registry["gates"]:
        lines.append(f"| `{gate['id']}` | {md_cell(gate['stage'])} | {md_cell(gate['spec'])} |")

    lines.extend(["", "## Canonical glossary", "", "| Stable ID | Canonical term | Operational meaning |", "|---|---|---|"])
    for term in glossary.values():
        lines.append(
            f"| `{term['stable_id']}` | {md_cell(term['canonical_term'])} | {md_cell(term['operational_meaning'])} |"
        )

    lines.extend(["", "## System profiles", "", "| Profile | Concerns |", "|---|---|"])
    for name, profile in system_profiles["profiles"].items():
        lines.append(f"| `{name}` | {md_cell(profile['concerns'])} |")

    lines.extend(["", "## Change profiles", "", "| Profile | Red evidence | Requirements |", "|---|---|---|"])
    for name, profile in change_profiles["profiles"].items():
        lines.append(
            f"| `{name}` | {md_cell(profile['red_evidence'])} | {md_cell(profile['requirements'])} |"
        )

    lines.extend(
        [
            "",
            "## Authority boundary",
            "",
            "This generated view is non-authoritative during shadow mode. Conflicts must fail loudly and be resolved against the Notion source until explicit cutover approval.",
            "",
        ]
    )
    return "\n".join(lines)


def command_validate() -> int:
    try:
        summary = validate_repo(ROOT)
    except (GovernanceValidationError, OSError, ValueError, yaml.YAMLError) as exc:
        print(f"governance validation failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def command_render(check: bool) -> int:
    rendered = render_markdown(ROOT)
    if check:
        if not GENERATED_VIEW.exists():
            print(f"generated view is missing: {GENERATED_VIEW}", file=sys.stderr)
            return 1
        if GENERATED_VIEW.read_text(encoding="utf-8") != rendered:
            print("generated view is stale; regenerate from governance YAML", file=sys.stderr)
            return 1
        print("generated view is current")
        return 0
    print(rendered, end="")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("validate")
    render_parser = subparsers.add_parser("render")
    render_parser.add_argument("--check", action="store_true")
    subparsers.add_parser("digest")
    args = parser.parse_args()
    if args.command == "validate":
        return command_validate()
    if args.command == "render":
        return command_render(args.check)
    print(bundle_digest(ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
