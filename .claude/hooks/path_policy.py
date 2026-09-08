#!/usr/bin/env python3
"""Load and validate the project-local STDD×VDD path policy."""

from __future__ import annotations

import argparse
import copy
import fnmatch
import json
import os
import string
import sys
from pathlib import Path, PurePosixPath
from typing import Any

CONFIG_PATH = Path(".vdd/path-policy.json")
DEFAULT_POLICY: dict[str, Any] = {
    "implementation_roots": ["src"],
    "feature_spec_templates": [
        "specs/features/{module}.feature",
        "spec/features/{module}.feature",
    ],
    "protected_spec_roots": ["spec", "specs"],
    "red_evidence_template": ".vdd/red/{module}.json",
    "test_file_patterns": ["*test*", "*spec*"],
    "test_roots": ["tests"],
    "spec_change_paths": ["spec", "specs"],
}
PATH_TEMPLATE_FIELDS = {"module", "relative", "path"}

# write-side：這些 phase 允許寫實作。
IMPLEMENTATION_PHASES = ("RED_VERIFIED", "GREEN")

# read-side lane。只有 RED_VERIFIED 能斷定「現在在實作側」。
# GREEN 是 cycle 結束狀態，不是下一個任務的 lane：green_gate 寫入 GREEN 之後，
# 沒有任何 task boundary 會把它復位，把 GREEN 當實作側會讓後續每個任務的
# test author 讀不到既有測試、卻讀得到實作——正好是反過來的隔離。
READ_LANE_BY_PHASE = {"RED_VERIFIED": "implementation", "GREEN": "cycle_complete"}
DEFAULT_READ_LANE = "test_authoring"
FORBIDDEN_SIDE_BY_LANE = {
    "implementation": "test",
    "test_authoring": "implementation",
    "cycle_complete": None,
}


class PolicyError(ValueError):
    """Raised when the local path policy cannot be enforced safely."""


def project_root() -> Path:
    configured = os.environ.get("CLAUDE_PROJECT_DIR")
    if configured:
        try:
            root = Path(configured).expanduser().resolve()
        except (OSError, RuntimeError) as exc:
            raise PolicyError(f"cannot resolve CLAUDE_PROJECT_DIR: {configured}") from exc
        if not root.is_dir():
            raise PolicyError(f"CLAUDE_PROJECT_DIR is not a directory: {configured}")
        return root

    try:
        current = Path.cwd().resolve()
    except (OSError, RuntimeError) as exc:
        raise PolicyError("cannot resolve the current working directory") from exc
    for candidate in (current, *current.parents):
        markers = (
            candidate / CONFIG_PATH,
            candidate / ".claude" / "hooks" / "path_policy.py",
            candidate / ".git",
        )
        if any(marker.exists() or marker.is_symlink() for marker in markers):
            return candidate
    return current


def _template_fields(value: str) -> set[str]:
    try:
        return {
            field_name
            for _, field_name, _, _ in string.Formatter().parse(value)
            if field_name is not None
        }
    except ValueError as exc:
        raise PolicyError(f"invalid template {value!r}: {exc}") from exc


def _normalize_relative(value: str, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise PolicyError(f"{label} entries must be non-empty strings")
    normalized = value.strip()
    while normalized.startswith("./"):
        normalized = normalized[2:]
    normalized = normalized.rstrip("/")
    path = PurePosixPath(normalized)
    if (
        not normalized
        or normalized == "."
        or path.is_absolute()
        or ".." in path.parts
        or "\\" in normalized
    ):
        raise PolicyError(f"{label} must contain repository-relative POSIX paths: {value!r}")
    return path.as_posix()


def _validate_string_list(value: Any, label: str, *, paths: bool = False) -> list[str]:
    if not isinstance(value, list) or not value:
        raise PolicyError(f"{label} must be a non-empty list")
    result = []
    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise PolicyError(f"{label} entries must be non-empty strings")
        result.append(_normalize_relative(item, label) if paths else item.strip())
    return result


def _validate_path_template(value: Any, label: str) -> str:
    normalized = _normalize_relative(value, label)
    unknown = _template_fields(normalized) - PATH_TEMPLATE_FIELDS
    if unknown:
        raise PolicyError(f"{label} has unsupported placeholders: {', '.join(sorted(unknown))}")
    return normalized


def red_evidence_root(policy: dict[str, Any]) -> str:
    """Return the static directory reserved for machine-generated RED evidence."""
    template = policy["red_evidence_template"]
    static_prefix = template.split("{", 1)[0]
    if "/" not in static_prefix:
        raise PolicyError(
            "red_evidence_template must place evidence below a static directory"
        )
    if static_prefix.endswith("/"):
        root = static_prefix.rstrip("/")
    else:
        root = static_prefix.rsplit("/", 1)[0]
    return _normalize_relative(root, "red_evidence_template static root")


def load_policy(path: Path | None = None) -> dict[str, Any]:
    root = project_root()
    policy_path = path or CONFIG_PATH
    if not policy_path.is_absolute():
        policy_path = root / policy_path
    lexical_path = Path(os.path.abspath(policy_path))
    try:
        resolved_policy_path = policy_path.resolve()
        resolved_relative = resolved_policy_path.relative_to(root)
    except (OSError, RuntimeError, ValueError) as exc:
        raise PolicyError(f"policy path must be inside the repository: {policy_path}") from exc
    try:
        lexical_relative = lexical_path.relative_to(root)
    except ValueError:
        lexical_relative = None
    if lexical_relative is not None and lexical_relative != resolved_relative:
        raise PolicyError(f"policy path must not cross symlinks: {lexical_path}")

    policy = copy.deepcopy(DEFAULT_POLICY)
    if lexical_path.exists() or lexical_path.is_symlink():
        try:
            resolved_path = resolved_policy_path.relative_to(root)
        except (OSError, RuntimeError, ValueError) as exc:
            raise PolicyError(f"{lexical_path} must resolve inside the repository") from exc
        try:
            override = json.loads((root / resolved_path).read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise PolicyError(f"cannot read {lexical_path}: {exc}") from exc
        if not isinstance(override, dict):
            raise PolicyError(f"{lexical_path} must contain a JSON object")
        unknown = set(override) - set(DEFAULT_POLICY)
        if unknown:
            raise PolicyError(f"{lexical_path} has unknown keys: {', '.join(sorted(unknown))}")
        policy.update(override)

    policy["implementation_roots"] = _validate_string_list(
        policy["implementation_roots"], "implementation_roots", paths=True
    )
    policy["protected_spec_roots"] = _validate_string_list(
        policy["protected_spec_roots"], "protected_spec_roots", paths=True
    )
    policy["spec_change_paths"] = _validate_string_list(
        policy["spec_change_paths"], "spec_change_paths", paths=True
    )
    policy["feature_spec_templates"] = [
        _validate_path_template(item, "feature_spec_templates")
        for item in _validate_string_list(
            policy["feature_spec_templates"], "feature_spec_templates"
        )
    ]
    policy["red_evidence_template"] = _validate_path_template(
        policy["red_evidence_template"], "red_evidence_template"
    )
    red_evidence_root(policy)
    policy["test_file_patterns"] = _validate_string_list(
        policy["test_file_patterns"], "test_file_patterns"
    )
    policy["test_roots"] = _validate_string_list(
        policy["test_roots"], "test_roots", paths=True
    )
    return policy


COLOCATED_SCAN_LIMIT = 5000


def forbidden_roots(policy: dict[str, Any], forbidden: str) -> list[str]:
    """The configured roots belonging to the isolated side."""
    if forbidden == "test":
        return list(policy["test_roots"])
    return list(policy["implementation_roots"])


def isolated_side_exists(
    policy: dict[str, Any], forbidden: str, root: Path | None = None
) -> bool:
    """Whether the isolated side actually exists in this repository.

    When it does not, nothing can be reached and the guards stay inert — otherwise
    this governance repository, which has no src/, would block its own searches.
    """
    base = root or project_root()
    if any((base / candidate).is_dir() for candidate in forbidden_roots(policy, forbidden)):
        return True
    if forbidden != "test":
        return False
    # test_roots 不存在不代表沒有測試：co-located layout 的測試就住在 implementation
    # roots 底下。掃描設上限，掃不完時回報「存在」——寧可留著 guard，也不要靜默停用。
    scanned = 0
    for candidate in policy["implementation_roots"]:
        directory = base / candidate
        if not directory.is_dir():
            continue
        for path in directory.rglob("*"):
            scanned += 1
            if scanned > COLOCATED_SCAN_LIMIT:
                return True
            if path.is_file() and matches_test_path(str(path), policy):
                return True
    return False


def scope_reaches_forbidden(
    raw_path: str, policy: dict[str, Any], forbidden: str
) -> bool:
    """Whether a search scope contains (rather than sits inside) an isolated root.

    `path: "."` classifies as "other" yet traverses the whole repository, so a
    containment check is required on top of classify_path.
    """
    relative = repo_relative_path(raw_path)
    if relative is None:
        return False
    normalized = "" if relative in (".", "") else relative
    if not normalized:
        return True
    return any(
        root == normalized or root.startswith(f"{normalized}/")
        for root in forbidden_roots(policy, forbidden)
    )


def read_lane(phase: str | None) -> str:
    """Return the read-side lane implied by the governance phase."""
    return READ_LANE_BY_PHASE.get(phase, DEFAULT_READ_LANE)


def forbidden_side(phase: str | None) -> str | None:
    """Return which side must not be read in this phase, or None."""
    return FORBIDDEN_SIDE_BY_LANE[read_lane(phase)]


def classify_path(raw_path: str, policy: dict[str, Any]) -> str:
    """Classify a path as spec / test / implementation / other.

    Order is precedence. Only paths inside configured roots are classified;
    outside them the answer is always "other" because the setup protocol forbids
    guessing layout from framework heuristics — otherwise a document such as
    docs/02-canonical-spec.md would be treated as a test by the *spec* pattern.
    """
    if path_in_roots(raw_path, policy["protected_spec_roots"]):
        return "spec"
    if path_in_roots(raw_path, policy["test_roots"]):
        return "test"
    if path_in_roots(raw_path, policy["implementation_roots"]):
        # Co-located tests such as app/login.spec.ts still belong to the test side.
        return "test" if matches_test_path(raw_path, policy) else "implementation"
    return "other"


def read_phase(root: Path | None = None) -> str | None:
    """Return the governance phase, or None when the state file is absent."""
    phase_file = (root or project_root()) / ".vdd" / "phase"
    try:
        if not phase_file.exists():
            return None
        return phase_file.read_text(encoding="utf-8").strip()
    except (OSError, UnicodeError) as exc:
        raise PolicyError(f"cannot read the governance phase: {exc}") from exc


def repo_relative_path(raw_path: str, root: Path | None = None) -> str | None:
    """Return a real repository-relative path; reject repository symlink escapes."""
    if not isinstance(raw_path, str) or not raw_path:
        return None
    try:
        repository = (root or project_root()).resolve()
    except (OSError, RuntimeError) as exc:
        raise PolicyError("cannot resolve the repository root") from exc
    candidate = Path(raw_path)
    if not candidate.is_absolute():
        candidate = repository / candidate
    lexical_candidate = Path(os.path.abspath(candidate))
    try:
        resolved_candidate = candidate.resolve()
    except (OSError, RuntimeError) as exc:
        raise PolicyError(f"cannot resolve repository path: {raw_path}") from exc
    try:
        resolved_relative = resolved_candidate.relative_to(repository)
    except ValueError:
        try:
            lexical_candidate.relative_to(repository)
        except ValueError:
            return None
        raise PolicyError(f"repository path escapes through a symlink: {raw_path}")
    try:
        lexical_relative = lexical_candidate.relative_to(repository)
    except ValueError:
        # Accept host-level aliases such as /var -> /private/var when the resolved
        # path is still inside the resolved repository root.
        return resolved_relative.as_posix()
    if lexical_relative != resolved_relative:
        raise PolicyError(f"repository path crosses a symlink: {raw_path}")
    return resolved_relative.as_posix()


def repository_path(raw_path: str) -> Path | None:
    relative = repo_relative_path(raw_path)
    return None if relative is None else (project_root() / relative).resolve()


def path_in_roots(raw_path: str, roots: list[str]) -> bool:
    relative = repo_relative_path(raw_path)
    if relative is None:
        return False
    return any(relative == root or relative.startswith(f"{root}/") for root in roots)


def implementation_context(raw_path: str, policy: dict[str, Any]) -> dict[str, str] | None:
    relative_path = repo_relative_path(raw_path)
    if relative_path is None:
        return None
    for root in sorted(policy["implementation_roots"], key=len, reverse=True):
        prefix = f"{root}/"
        if not relative_path.startswith(prefix):
            continue
        below_root = relative_path[len(prefix):]
        without_suffix = PurePosixPath(below_root).with_suffix("").as_posix()
        full_without_suffix = PurePosixPath(relative_path).with_suffix("").as_posix()
        return {
            "module": PurePosixPath(relative_path).stem,
            "relative": without_suffix,
            "path": full_without_suffix,
        }
    return None


def render_path_template(template: str, context: dict[str, str]) -> Path:
    try:
        rendered = template.format_map(context)
    except (KeyError, ValueError) as exc:
        raise PolicyError(f"cannot render path template {template!r}: {exc}") from exc
    normalized = _normalize_relative(rendered, "rendered path")
    root = project_root()
    candidate = root / normalized
    try:
        resolved_relative = candidate.resolve().relative_to(root)
    except (OSError, RuntimeError, ValueError) as exc:
        raise PolicyError(f"rendered path escapes through a symlink: {normalized}") from exc
    if PurePosixPath(normalized) != PurePosixPath(resolved_relative.as_posix()):
        raise PolicyError(f"rendered path crosses a symlink: {normalized}")
    try:
        return candidate.resolve()
    except (OSError, RuntimeError) as exc:
        raise PolicyError(f"cannot resolve rendered path: {normalized}") from exc


def feature_spec_paths(policy: dict[str, Any], context: dict[str, str]) -> list[Path]:
    return [render_path_template(item, context) for item in policy["feature_spec_templates"]]


def red_evidence_path(policy: dict[str, Any], context: dict[str, str]) -> Path:
    return render_path_template(policy["red_evidence_template"], context)


def matches_test_path(raw_path: str, policy: dict[str, Any]) -> bool:
    relative = repo_relative_path(raw_path)
    if relative is None:
        return False
    return any(
        fnmatch.fnmatchcase(
            relative.casefold() if pattern == "*spec*" else relative,
            pattern.casefold() if pattern == "*spec*" else pattern,
        )
        for pattern in policy["test_file_patterns"]
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--policy", type=Path, help="policy path inside the project")
    arguments = parser.parse_args()
    try:
        load_policy(arguments.policy)
    except PolicyError as exc:
        print(f"INVALID: {exc}", file=sys.stderr)
        return 2
    print("path policy: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
