#!/usr/bin/env python3
"""Render isolated, skills-only z-harness packages from canonical skill sources.

The renderer is hermetic with respect to its declared inputs: repository files, render config,
and adapter config. It does not read Git state, environment variables, clocks, networks, runtime
homes, or installed harness configuration.

Usage:
  render-packages.py --output <new-directory>
  render-packages.py --verify <rendered-directory>
  render-packages.py --selftest

An output path must not already exist. Publication and installation are separate operations.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import sys
import tempfile
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


VERSION = "0.2.0"
ROOT = Path(__file__).resolve().parent.parent
DEFAULT_RENDER_CONFIG = ROOT / "release" / "render.json"
DEFAULT_ADAPTER_CONFIG = ROOT / "adapters" / "targets.json"
ARTIFACT_MANIFEST = "z-harness-artifact.json"
RENDER_INDEX = "render-index.json"
ARTIFACT_SCHEMA = (
    "https://github.com/ChrisHuie/z-harness/blob/main/"
    "contracts/artifact-manifest.schema.json"
)
RENDER_INDEX_SCHEMA = (
    "https://github.com/ChrisHuie/z-harness/blob/main/contracts/render-index.schema.json"
)
AGENT_PLUGIN_SCHEMA = "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json"
SEMVER = re.compile(
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?"
    r"(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?$"
)
SKILL_NAME = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
PACKAGE_NAME = re.compile(r"^[a-z0-9]+(?:[.-][a-z0-9]+)*$")
KIMI_PLUGIN_NAME = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")
EXPECTED_MANIFEST_PATHS = {
    "agent-plugins": "plugin.json",
    "codex": ".codex-plugin/plugin.json",
    "claude": ".claude-plugin/plugin.json",
    "kimi": "kimi.plugin.json",
    "hermes": None,
}
COMPETING_MANIFESTS = {
    "plugin.json",
    ".codex-plugin/plugin.json",
    ".claude-plugin/plugin.json",
    "kimi.plugin.json",
    ".kimi-plugin/plugin.json",
    "plugin.yaml",
}
TARGET_LEVELS = {
    "portable-core",
    "adapter-functional",
    "host-integrated",
    "governed-parity",
}
AUTHORITIES = {"instruction-only", "host-enforced", "external-boundary"}
VALIDATION_STATUSES = {"fixture-only", "candidate", "promoted"}


class RenderError(Exception):
    """A deterministic input, rendering, or verification failure."""


def read_json_object(path: Path, label: str) -> Dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise RenderError(f"cannot read {label} {path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise RenderError(f"{label} is not valid JSON: {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise RenderError(f"{label} must contain a JSON object: {path}")
    return value


def require_exact_keys(value: Dict[str, Any], expected: Iterable[str], label: str) -> None:
    actual = set(value)
    wanted = set(expected)
    missing = sorted(wanted - actual)
    unknown = sorted(actual - wanted)
    if missing or unknown:
        raise RenderError(f"{label} keys: missing={missing} unknown={unknown}")


def require_nonempty_string(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise RenderError(f"{label} must be a non-empty string")
    return value


def require_string_list(value: Any, label: str, *, nonempty: bool = False) -> List[str]:
    if not isinstance(value, list) or not all(
        isinstance(item, str) and item for item in value
    ):
        raise RenderError(f"{label} must be an array of non-empty strings")
    if nonempty and not value:
        raise RenderError(f"{label} must not be empty")
    if len(value) != len(set(value)):
        raise RenderError(f"{label} must not contain duplicates")
    return list(value)


def load_inputs(
    render_path: Path = DEFAULT_RENDER_CONFIG,
    adapter_path: Path = DEFAULT_ADAPTER_CONFIG,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    render_config = read_json_object(render_path, "render config")
    adapter_config = read_json_object(adapter_path, "adapter config")

    require_exact_keys(
        render_config,
        {
            "schemaVersion",
            "package",
            "sourceSkillsPath",
            "selectedSkills",
            "runtimeExcludeDirectories",
            "targets",
        },
        "render config",
    )
    if render_config["schemaVersion"] != 1:
        raise RenderError("render config schemaVersion must be 1")
    package = render_config["package"]
    if not isinstance(package, dict):
        raise RenderError("render config package must be an object")
    require_exact_keys(
        package,
        {
            "name",
            "coreVersion",
            "description",
            "author",
            "homepage",
            "repository",
            "keywords",
            "licenses",
            "interface",
        },
        "render config package",
    )
    package_name = require_nonempty_string(package["name"], "package.name")
    if PACKAGE_NAME.fullmatch(package_name) is None:
        raise RenderError("package.name is not a portable package identifier")
    core_version = require_nonempty_string(package["coreVersion"], "package.coreVersion")
    if SEMVER.fullmatch(core_version) is None:
        raise RenderError("package.coreVersion must be strict semantic versioning")
    require_nonempty_string(package["description"], "package.description")
    require_nonempty_string(package["homepage"], "package.homepage")
    require_nonempty_string(package["repository"], "package.repository")
    require_string_list(package["keywords"], "package.keywords")
    require_string_list(package["licenses"], "package.licenses")
    author = package["author"]
    if not isinstance(author, dict):
        raise RenderError("package.author must be an object")
    require_exact_keys(author, {"name", "url"}, "package.author")
    require_nonempty_string(author["name"], "package.author.name")
    require_nonempty_string(author["url"], "package.author.url")
    interface = package["interface"]
    if not isinstance(interface, dict):
        raise RenderError("package.interface must be an object")
    require_exact_keys(
        interface,
        {
            "displayName",
            "shortDescription",
            "longDescription",
            "developerName",
            "category",
            "capabilities",
            "websiteURL",
            "brandColor",
            "defaultPrompt",
        },
        "package.interface",
    )
    for key in (
        "displayName",
        "shortDescription",
        "longDescription",
        "developerName",
        "category",
        "websiteURL",
        "brandColor",
    ):
        require_nonempty_string(interface[key], f"package.interface.{key}")
    require_string_list(interface["capabilities"], "package.interface.capabilities", nonempty=True)
    prompts = require_string_list(
        interface["defaultPrompt"], "package.interface.defaultPrompt", nonempty=True
    )
    if len(prompts) > 3 or any(len(prompt) > 128 for prompt in prompts):
        raise RenderError("package.interface.defaultPrompt must contain 1-3 strings <=128 chars")

    source_path = require_nonempty_string(
        render_config["sourceSkillsPath"], "sourceSkillsPath"
    )
    source_parts = Path(source_path).parts
    if Path(source_path).is_absolute() or ".." in source_parts:
        raise RenderError("sourceSkillsPath must remain inside the repository")
    skills = require_string_list(
        render_config["selectedSkills"], "selectedSkills", nonempty=True
    )
    for skill in skills:
        if SKILL_NAME.fullmatch(skill) is None:
            raise RenderError(f"selected skill is not kebab-case: {skill!r}")
    excludes = require_string_list(
        render_config["runtimeExcludeDirectories"], "runtimeExcludeDirectories"
    )
    for excluded in excludes:
        if Path(excluded).name != excluded or excluded in (".", ".."):
            raise RenderError(
                "runtimeExcludeDirectories entries must be immediate directory names"
            )
    targets = require_string_list(render_config["targets"], "targets", nonempty=True)

    require_exact_keys(adapter_config, {"schemaVersion", "targets"}, "adapter config")
    if adapter_config["schemaVersion"] != 1:
        raise RenderError("adapter config schemaVersion must be 1")
    adapters = adapter_config["targets"]
    if not isinstance(adapters, dict) or not adapters:
        raise RenderError("adapter config targets must be a non-empty object")
    for target in targets:
        if target not in EXPECTED_MANIFEST_PATHS:
            raise RenderError(f"renderer has no implementation for target {target!r}")
        adapter = adapters.get(target)
        if not isinstance(adapter, dict):
            raise RenderError(f"adapter config has no object for target {target!r}")
        require_exact_keys(
            adapter,
            {
                "adapterRevision",
                "packageVersion",
                "format",
                "manifestPath",
                "targetLevel",
                "authority",
                "validationStatus",
                "testedHosts",
            },
            f"adapter {target}",
        )
        revision = adapter["adapterRevision"]
        if not isinstance(revision, int) or isinstance(revision, bool) or revision < 1:
            raise RenderError(f"adapter {target} revision must be a positive integer")
        package_version = require_nonempty_string(
            adapter["packageVersion"], f"adapter {target} packageVersion"
        )
        if SEMVER.fullmatch(package_version) is None:
            raise RenderError(f"adapter {target} packageVersion must be strict semantic versioning")
        require_nonempty_string(adapter["format"], f"adapter {target} format")
        if adapter["manifestPath"] != EXPECTED_MANIFEST_PATHS[target]:
            raise RenderError(f"adapter {target} manifestPath is not the implemented path")
        if adapter["targetLevel"] not in TARGET_LEVELS:
            raise RenderError(f"adapter {target} has an unknown targetLevel")
        if adapter["authority"] not in AUTHORITIES:
            raise RenderError(f"adapter {target} has an unknown authority")
        if adapter["validationStatus"] not in VALIDATION_STATUSES:
            raise RenderError(f"adapter {target} has an unknown validationStatus")
        require_string_list(adapter["testedHosts"], f"adapter {target} testedHosts")
        if adapter["validationStatus"] == "fixture-only" and adapter["testedHosts"]:
            raise RenderError(f"fixture-only adapter {target} must not claim tested hosts")

    return render_config, adapter_config


def decode_scalar(raw: str, label: str) -> str:
    value = raw.strip()
    if not value:
        raise RenderError(f"{label} must be a single-line scalar")
    if value.startswith('"'):
        try:
            decoded = json.loads(value)
        except json.JSONDecodeError as exc:
            raise RenderError(f"{label} has invalid quoted text") from exc
        return require_nonempty_string(decoded, label)
    if value.startswith("'"):
        if not value.endswith("'") or len(value) < 2:
            raise RenderError(f"{label} has invalid quoted text")
        return require_nonempty_string(value[1:-1].replace("''", "'"), label)
    return value


def parse_skill_frontmatter(path: Path, expected_name: str) -> Dict[str, str]:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise RenderError(f"cannot read skill manifest {path}: {exc}") from exc
    lines = text.splitlines()
    if not lines or lines[0] != "---":
        raise RenderError(f"skill {expected_name} has no opening YAML frontmatter delimiter")
    try:
        end = lines.index("---", 1)
    except ValueError as exc:
        raise RenderError(f"skill {expected_name} has no closing frontmatter delimiter") from exc
    values: Dict[str, str] = {}
    for line in lines[1:end]:
        if not line or line[0].isspace() or ":" not in line:
            continue
        key, raw = line.split(":", 1)
        if key in ("name", "description"):
            values[key] = decode_scalar(raw, f"skill {expected_name} {key}")
    if set(values) != {"name", "description"}:
        raise RenderError(f"skill {expected_name} requires top-level name and description")
    if values["name"] != expected_name:
        raise RenderError(
            f"skill directory/name mismatch: directory={expected_name!r} "
            f"frontmatter={values['name']!r}"
        )
    if SKILL_NAME.fullmatch(values["name"]) is None:
        raise RenderError(f"skill name is not portable kebab-case: {values['name']!r}")
    if not 1 <= len(values["description"]) <= 1024:
        raise RenderError(f"skill {expected_name} description must be 1-1024 characters")
    return values


def normalized_mode(path: Path) -> str:
    mode = stat.S_IMODE(path.stat().st_mode)
    return "0755" if mode & 0o111 else "0644"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical_json_digest(value: Any) -> str:
    data = json.dumps(
        value, ensure_ascii=False, separators=(",", ":"), sort_keys=True
    ).encode("utf-8")
    return sha256_bytes(data)


def file_record(path: Path, relative: str) -> Dict[str, str]:
    return {
        "path": relative,
        "mode": normalized_mode(path),
        "sha256": sha256_bytes(path.read_bytes()),
    }


def tree_digest(records: Sequence[Dict[str, str]]) -> str:
    digest = hashlib.sha256()
    for record in sorted(records, key=lambda item: item["path"]):
        for key in ("path", "mode", "sha256"):
            digest.update(record[key].encode("utf-8"))
            digest.update(b"\0")
    return digest.hexdigest()


def scan_skill(
    skill_dir: Path,
    skill_name: str,
    excluded_directories: Sequence[str],
) -> Tuple[List[Dict[str, str]], List[Dict[str, str]], List[str]]:
    if not skill_dir.is_dir():
        raise RenderError(f"selected skill directory is absent: {skill_dir}")
    if skill_dir.is_symlink():
        raise RenderError(f"selected skill directory must not be a symlink: {skill_dir}")
    parse_skill_frontmatter(skill_dir / "SKILL.md", skill_name)
    all_records: List[Dict[str, str]] = []
    included: List[Dict[str, str]] = []
    excluded: List[str] = []
    for path in sorted(skill_dir.rglob("*"), key=lambda item: item.as_posix()):
        if path.is_symlink():
            raise RenderError(f"skill source contains a symlink: {path}")
        if path.is_dir():
            continue
        if not path.is_file():
            raise RenderError(f"skill source contains a non-regular file: {path}")
        relative = path.relative_to(skill_dir).as_posix()
        record = file_record(path, relative)
        all_records.append(record)
        if Path(relative).parts[0] in excluded_directories:
            excluded.append(relative)
        else:
            included.append(record)
    if not all_records:
        raise RenderError(f"selected skill has zero files: {skill_name}")
    if not included or "SKILL.md" not in {record["path"] for record in included}:
        raise RenderError(f"selected skill has no included SKILL.md: {skill_name}")
    return all_records, included, excluded


def resolve_source_skills_root(
    repo_root: Path,
    render_config: Dict[str, Any],
) -> Path:
    repo_root = repo_root.resolve()
    candidate = repo_root
    for part in Path(render_config["sourceSkillsPath"]).parts:
        candidate = candidate / part
        if candidate.is_symlink():
            raise RenderError(f"sourceSkillsPath must not traverse a symlink: {candidate}")
    resolved = candidate.resolve()
    if resolved != repo_root and repo_root not in resolved.parents:
        raise RenderError(f"sourceSkillsPath resolves outside the repository: {resolved}")
    if not resolved.is_dir():
        raise RenderError(f"sourceSkillsPath is not a directory: {resolved}")
    return resolved


def write_bytes(path: Path, data: bytes, mode: str = "0644") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    path.chmod(int(mode, 8))
    os.utime(path, (0, 0))


def write_json(path: Path, value: Dict[str, Any]) -> None:
    data = (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")
    write_bytes(path, data)


def copy_skill_payload(
    source_dir: Path,
    target_dir: Path,
    included: Sequence[Dict[str, str]],
) -> None:
    for record in sorted(included, key=lambda item: item["path"]):
        source = source_dir / record["path"]
        destination = target_dir / record["path"]
        write_bytes(destination, source.read_bytes(), record["mode"])


def target_manifest(
    target: str,
    package: Dict[str, Any],
    package_version: str,
) -> Optional[Dict[str, Any]]:
    common = {
        "name": package["name"],
        "version": package_version,
        "description": package["description"],
        "author": dict(package["author"]),
        "homepage": package["homepage"],
        "repository": package["repository"],
        "keywords": list(package["keywords"]),
    }
    if len(package["licenses"]) == 1:
        common["license"] = package["licenses"][0]
    if target == "agent-plugins":
        return {"$schema": AGENT_PLUGIN_SCHEMA, **common}
    if target == "codex":
        return {**common, "skills": "./skills/", "interface": package["interface"]}
    if target == "claude":
        return {**common, "skills": "./skills/"}
    if target == "kimi":
        interface = package["interface"]
        return {
            "name": package["name"],
            "version": package_version,
            "description": package["description"],
            "skills": "./skills/",
            "interface": {
                "displayName": interface["displayName"],
                "shortDescription": interface["shortDescription"],
                "longDescription": interface["longDescription"],
                "developerName": interface["developerName"],
                "websiteURL": interface["websiteURL"],
            },
        }
    if target == "hermes":
        return None
    raise RenderError(f"no manifest builder for target {target!r}")


def payload_records(artifact_root: Path) -> List[Dict[str, str]]:
    records: List[Dict[str, str]] = []
    for path in sorted(artifact_root.rglob("*"), key=lambda item: item.as_posix()):
        if path.is_symlink():
            raise RenderError(f"rendered artifact contains a symlink: {path}")
        if path.is_dir():
            continue
        if not path.is_file():
            raise RenderError(f"rendered artifact contains a non-regular file: {path}")
        relative = path.relative_to(artifact_root).as_posix()
        if relative == ARTIFACT_MANIFEST:
            continue
        records.append(file_record(path, relative))
    if not records:
        raise RenderError(f"artifact has zero payload files: {artifact_root}")
    return records


def complete_artifact_records(artifact_root: Path) -> List[Dict[str, str]]:
    records: List[Dict[str, str]] = []
    for path in sorted(artifact_root.rglob("*"), key=lambda item: item.as_posix()):
        if path.is_symlink():
            raise RenderError(f"rendered artifact contains a symlink: {path}")
        if path.is_dir():
            continue
        if not path.is_file():
            raise RenderError(f"rendered artifact contains a non-regular file: {path}")
        records.append(file_record(path, path.relative_to(artifact_root).as_posix()))
    if not records:
        raise RenderError(f"artifact has zero files: {artifact_root}")
    return records


def assert_isolated_manifest(artifact_root: Path, target: str) -> None:
    intended = EXPECTED_MANIFEST_PATHS[target]
    present = sorted(
        relative for relative in COMPETING_MANIFESTS
        if (artifact_root / relative).is_file()
    )
    expected = [] if intended is None else [intended]
    if present != expected:
        raise RenderError(
            f"target {target} manifest isolation failed: intended={intended!r} present={present}"
        )


def is_sha256(value: Any) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def verify_target_manifest(
    artifact_root: Path,
    target: str,
    artifact_manifest: Dict[str, Any],
) -> None:
    manifest_relative = EXPECTED_MANIFEST_PATHS[target]
    if manifest_relative is None:
        if target != "hermes":
            raise RenderError(f"target {target} unexpectedly has no native manifest")
        return
    manifest_path = artifact_root / manifest_relative
    manifest = read_json_object(manifest_path, f"{target} package manifest")
    if target == "kimi":
        require_exact_keys(
            manifest,
            {"name", "version", "description", "skills", "interface"},
            "kimi package manifest",
        )
        if manifest["name"] != artifact_manifest["packageName"]:
            raise RenderError("kimi package name does not match artifact identity")
        if KIMI_PLUGIN_NAME.fullmatch(manifest["name"]) is None:
            raise RenderError("kimi package name is not a valid plugin id")
        if manifest["version"] != artifact_manifest["packageVersion"]:
            raise RenderError("kimi package version does not match artifact identity")
        require_nonempty_string(manifest["description"], "kimi manifest description")
        if manifest["skills"] != "./skills/":
            raise RenderError("kimi manifest skills path must be ./skills/")
        interface = manifest["interface"]
        if not isinstance(interface, dict):
            raise RenderError("kimi manifest interface must be an object")
        require_exact_keys(
            interface,
            {
                "displayName",
                "shortDescription",
                "longDescription",
                "developerName",
                "websiteURL",
            },
            "kimi manifest interface",
        )
        for key, value in interface.items():
            require_nonempty_string(value, f"kimi manifest interface.{key}")
        return
    common = {
        "name", "version", "description", "author", "homepage", "repository", "keywords"
    }
    optional = {"license"}
    target_keys = {
        "agent-plugins": {"$schema"},
        "codex": {"skills", "interface"},
        "claude": {"skills"},
    }[target]
    unknown = sorted(set(manifest) - common - optional - target_keys)
    missing = sorted((common | target_keys) - set(manifest))
    if missing or unknown:
        raise RenderError(
            f"{target} package manifest keys: missing={missing} unknown={unknown}"
        )
    if manifest["name"] != artifact_manifest["packageName"]:
        raise RenderError(f"{target} package name does not match artifact identity")
    if manifest["version"] != artifact_manifest["packageVersion"]:
        raise RenderError(f"{target} package version does not match artifact identity")
    require_nonempty_string(manifest["description"], f"{target} manifest description")
    author = manifest["author"]
    if not isinstance(author, dict) or not author:
        raise RenderError(f"{target} manifest author must be a non-empty object")
    require_nonempty_string(author.get("name"), f"{target} manifest author.name")
    require_nonempty_string(manifest["homepage"], f"{target} manifest homepage")
    require_nonempty_string(manifest["repository"], f"{target} manifest repository")
    require_string_list(manifest["keywords"], f"{target} manifest keywords")
    licenses = artifact_manifest["licenses"]
    if len(licenses) == 1 and manifest.get("license") != licenses[0]:
        raise RenderError(f"{target} manifest license does not match artifact licenses")
    if len(licenses) != 1 and "license" in manifest:
        raise RenderError(f"{target} manifest must omit ambiguous license metadata")
    if target == "agent-plugins":
        if manifest["$schema"] != AGENT_PLUGIN_SCHEMA:
            raise RenderError("portable manifest does not target Agent Plugins 1.0.0")
    else:
        if manifest["skills"] != "./skills/":
            raise RenderError(f"{target} manifest skills path must be ./skills/")
    if target == "codex" and not isinstance(manifest["interface"], dict):
        raise RenderError("codex manifest interface must be an object")


def render_target(
    repo_root: Path,
    target_root: Path,
    target: str,
    render_config: Dict[str, Any],
    adapter_config: Dict[str, Any],
) -> Dict[str, Any]:
    package = render_config["package"]
    adapter = adapter_config["targets"][target]
    source_skills = resolve_source_skills_root(repo_root, render_config)
    excluded_directories = render_config["runtimeExcludeDirectories"]
    skill_manifests: List[Dict[str, Any]] = []
    aggregate_input: List[Dict[str, str]] = []
    aggregate_included: List[Dict[str, str]] = []

    target_root.mkdir(parents=True, exist_ok=False)
    for skill_name in sorted(render_config["selectedSkills"]):
        source_dir = source_skills / skill_name
        all_records, included, excluded = scan_skill(
            source_dir, skill_name, excluded_directories
        )
        copy_skill_payload(source_dir, target_root / "skills" / skill_name, included)
        skill_manifests.append({
            "id": skill_name,
            "inputTreeSha256": tree_digest(all_records),
            "includedTreeSha256": tree_digest(included),
            "includedFiles": len(included),
            "excludedPaths": sorted(excluded),
        })
        for record in all_records:
            aggregate_input.append({**record, "path": f"{skill_name}/{record['path']}"})
        for record in included:
            aggregate_included.append({**record, "path": f"{skill_name}/{record['path']}"})

    manifest_relative = adapter["manifestPath"]
    manifest = target_manifest(target, package, adapter["packageVersion"])
    if manifest_relative is None:
        if manifest is not None:
            raise RenderError(f"target {target} produced an undeclared native manifest")
    else:
        if manifest is None:
            raise RenderError(f"target {target} did not produce its declared native manifest")
        write_json(target_root / manifest_relative, manifest)
    assert_isolated_manifest(target_root, target)
    payload = payload_records(target_root)
    artifact_manifest = {
        "$schema": ARTIFACT_SCHEMA,
        "schemaVersion": 1,
        "artifactId": f"{package['name']}/{target}",
        "packageName": package["name"],
        "coreVersion": package["coreVersion"],
        "packageVersion": adapter["packageVersion"],
        "licenses": package["licenses"],
        "target": target,
        "format": adapter["format"],
        "adapterRevision": adapter["adapterRevision"],
        "build": {
            "renderer": "z-harness/render-packages",
            "rendererVersion": VERSION,
            "rendererSha256": sha256_bytes(Path(__file__).resolve().read_bytes()),
            "renderConfigSha256": canonical_json_digest(render_config),
            "adapterConfigSha256": canonical_json_digest(adapter),
        },
        "source": {
            "kind": "canonical-tree",
            "inputTreeSha256": tree_digest(aggregate_input),
            "includedTreeSha256": tree_digest(aggregate_included),
            "upstreamLocks": [],
            "skills": skill_manifests,
        },
        "payload": {
            "sha256": tree_digest(payload),
            "files": payload,
        },
        "claims": {
            "targetLevel": adapter["targetLevel"],
            "earnedLevel": "unverified",
            "authority": adapter["authority"],
            "validationStatus": adapter["validationStatus"],
            "testedHosts": adapter["testedHosts"],
        },
    }
    write_json(target_root / ARTIFACT_MANIFEST, artifact_manifest)
    verify_artifact(target_root, target)
    return artifact_manifest


def render_all(
    repo_root: Path,
    output_root: Path,
    render_config: Dict[str, Any],
    adapter_config: Dict[str, Any],
) -> Dict[str, Dict[str, Any]]:
    repo_root = repo_root.resolve()
    output_root = output_root.resolve()
    if output_root.exists():
        raise RenderError(f"output path already exists: {output_root}")
    source_skills = resolve_source_skills_root(repo_root, render_config)
    for skill_name in render_config["selectedSkills"]:
        source_dir = (source_skills / skill_name).resolve()
        if output_root == source_dir or source_dir in output_root.parents:
            raise RenderError(
                f"output path must not overlap selected skill source {skill_name!r}: "
                f"{output_root}"
            )
    output_root.parent.mkdir(parents=True, exist_ok=True)
    temp_root = Path(tempfile.mkdtemp(prefix=f".{output_root.name}.", dir=output_root.parent))
    results: Dict[str, Dict[str, Any]] = {}
    try:
        for target in sorted(render_config["targets"]):
            results[target] = render_target(
                repo_root,
                temp_root / target,
                target,
                render_config,
                adapter_config,
            )
        render_index = {
            "$schema": RENDER_INDEX_SCHEMA,
            "schemaVersion": 1,
            "coreVersion": render_config["package"]["coreVersion"],
            "targets": {
                target: {
                    "artifactId": results[target]["artifactId"],
                    "packageVersion": results[target]["packageVersion"],
                    "adapterRevision": results[target]["adapterRevision"],
                    "artifactSha256": tree_digest(
                        complete_artifact_records(temp_root / target)
                    ),
                    "payloadSha256": results[target]["payload"]["sha256"],
                }
                for target in sorted(results)
            },
        }
        write_json(temp_root / RENDER_INDEX, render_index)
        temp_root.rename(output_root)
    except Exception:
        shutil.rmtree(temp_root, ignore_errors=True)
        raise
    return results


def verify_artifact(artifact_root: Path, expected_target: str) -> Dict[str, Any]:
    artifact_root = artifact_root.resolve()
    manifest_path = artifact_root / ARTIFACT_MANIFEST
    manifest = read_json_object(manifest_path, "artifact manifest")
    require_exact_keys(
        manifest,
        {
            "$schema",
            "schemaVersion",
            "artifactId",
            "packageName",
            "coreVersion",
            "packageVersion",
            "licenses",
            "target",
            "format",
            "adapterRevision",
            "build",
            "source",
            "payload",
            "claims",
        },
        "artifact manifest",
    )
    if manifest["$schema"] != ARTIFACT_SCHEMA or manifest["schemaVersion"] != 1:
        raise RenderError("artifact manifest schema identity is invalid")
    if manifest["target"] != expected_target:
        raise RenderError(
            f"artifact target mismatch: expected={expected_target!r} actual={manifest['target']!r}"
        )
    if expected_target not in EXPECTED_MANIFEST_PATHS:
        raise RenderError(f"unknown artifact target: {expected_target!r}")
    package_name = require_nonempty_string(manifest["packageName"], "artifact packageName")
    if PACKAGE_NAME.fullmatch(package_name) is None:
        raise RenderError("artifact packageName is not portable")
    if manifest["artifactId"] != f"{package_name}/{expected_target}":
        raise RenderError("artifactId does not match packageName and target")
    for version_field in ("coreVersion", "packageVersion"):
        version = require_nonempty_string(manifest[version_field], f"artifact {version_field}")
        if SEMVER.fullmatch(version) is None:
            raise RenderError(f"artifact {version_field} must be strict semantic versioning")
    require_string_list(manifest["licenses"], "artifact licenses")
    revision = manifest["adapterRevision"]
    if not isinstance(revision, int) or isinstance(revision, bool) or revision < 1:
        raise RenderError("artifact adapterRevision must be a positive integer")
    require_nonempty_string(manifest["format"], "artifact format")
    build = manifest.get("build")
    if not isinstance(build, dict):
        raise RenderError("artifact build must be an object")
    require_exact_keys(
        build,
        {
            "renderer",
            "rendererVersion",
            "rendererSha256",
            "renderConfigSha256",
            "adapterConfigSha256",
        },
        "artifact build",
    )
    if build["renderer"] != "z-harness/render-packages":
        raise RenderError("artifact build renderer identity is invalid")
    renderer_version = require_nonempty_string(
        build["rendererVersion"], "artifact build rendererVersion"
    )
    if SEMVER.fullmatch(renderer_version) is None:
        raise RenderError("artifact build rendererVersion must be strict semantic versioning")
    for digest_field in (
        "rendererSha256",
        "renderConfigSha256",
        "adapterConfigSha256",
    ):
        if not is_sha256(build[digest_field]):
            raise RenderError(f"artifact build {digest_field} must be a sha256 value")
    assert_isolated_manifest(artifact_root, expected_target)
    verify_target_manifest(artifact_root, expected_target, manifest)
    source = manifest.get("source")
    if not isinstance(source, dict):
        raise RenderError("artifact source must be an object")
    require_exact_keys(
        source,
        {"kind", "inputTreeSha256", "includedTreeSha256", "upstreamLocks", "skills"},
        "artifact source",
    )
    if source["kind"] != "canonical-tree":
        raise RenderError("artifact source kind must be canonical-tree")
    if not is_sha256(source["inputTreeSha256"]) or not is_sha256(
        source["includedTreeSha256"]
    ):
        raise RenderError("artifact source digests must be sha256 values")
    if not isinstance(source["upstreamLocks"], list):
        raise RenderError("artifact upstreamLocks must be an array")
    upstream_ids: List[str] = []
    for index, lock in enumerate(source["upstreamLocks"]):
        if not isinstance(lock, dict):
            raise RenderError(f"artifact upstreamLocks[{index}] must be an object")
        require_exact_keys(
            lock, {"id", "revision", "sha256", "licenses"},
            f"artifact upstreamLocks[{index}]",
        )
        upstream_id = require_nonempty_string(lock["id"], f"upstream lock {index} id")
        upstream_ids.append(upstream_id)
        require_nonempty_string(lock["revision"], f"upstream lock {upstream_id} revision")
        if not is_sha256(lock["sha256"]):
            raise RenderError(f"upstream lock {upstream_id} sha256 is invalid")
        require_string_list(
            lock["licenses"], f"upstream lock {upstream_id} licenses", nonempty=True
        )
    if len(upstream_ids) != len(set(upstream_ids)):
        raise RenderError("artifact upstream lock ids must be unique")
    skills = source["skills"]
    if not isinstance(skills, list) or not skills:
        raise RenderError("artifact source skills must be a non-empty array")
    skill_ids: List[str] = []
    for index, skill in enumerate(skills):
        if not isinstance(skill, dict):
            raise RenderError(f"artifact source skills[{index}] must be an object")
        require_exact_keys(
            skill,
            {
                "id", "inputTreeSha256", "includedTreeSha256", "includedFiles",
                "excludedPaths",
            },
            f"artifact source skills[{index}]",
        )
        skill_id = require_nonempty_string(skill["id"], f"artifact skill {index} id")
        skill_ids.append(skill_id)
        if not is_sha256(skill["inputTreeSha256"]) or not is_sha256(
            skill["includedTreeSha256"]
        ):
            raise RenderError(f"artifact skill {skill_id} digests must be sha256 values")
        if (
            not isinstance(skill["includedFiles"], int)
            or isinstance(skill["includedFiles"], bool)
            or skill["includedFiles"] < 1
        ):
            raise RenderError(f"artifact skill {skill_id} includedFiles must be positive")
        require_string_list(skill["excludedPaths"], f"artifact skill {skill_id} excludedPaths")
    if len(skill_ids) != len(set(skill_ids)):
        raise RenderError("artifact source skill ids must be unique")
    payload = manifest.get("payload")
    if not isinstance(payload, dict):
        raise RenderError("artifact payload must be an object")
    require_exact_keys(payload, {"sha256", "files"}, "artifact payload")
    actual_files = payload_records(artifact_root)
    if payload["files"] != actual_files:
        raise RenderError(f"artifact payload inventory or file digest mismatch: {artifact_root}")
    if not is_sha256(payload["sha256"]) or payload["sha256"] != tree_digest(actual_files):
        raise RenderError(f"artifact aggregate payload digest mismatch: {artifact_root}")
    aggregate_included: List[Dict[str, str]] = []
    for skill in skills:
        skill_id = skill["id"]
        prefix = f"skills/{skill_id}/"
        included = [
            {**record, "path": record["path"][len(prefix):]}
            for record in actual_files
            if record["path"].startswith(prefix)
        ]
        if skill["includedFiles"] != len(included):
            raise RenderError(f"artifact skill {skill_id} includedFiles does not match payload")
        if skill["includedTreeSha256"] != tree_digest(included):
            raise RenderError(
                f"artifact skill {skill_id} includedTreeSha256 does not match payload"
            )
        aggregate_included.extend(
            {**record, "path": f"{skill_id}/{record['path']}"}
            for record in included
        )
    if source["includedTreeSha256"] != tree_digest(aggregate_included):
        raise RenderError("artifact aggregate includedTreeSha256 does not match payload")
    claims = manifest.get("claims")
    if not isinstance(claims, dict):
        raise RenderError("artifact claims must be an object")
    require_exact_keys(
        claims,
        {"targetLevel", "earnedLevel", "authority", "validationStatus", "testedHosts"},
        "artifact claims",
    )
    if claims["earnedLevel"] != "unverified":
        raise RenderError("renderer may emit only unverified earnedLevel")
    if claims["targetLevel"] not in TARGET_LEVELS:
        raise RenderError("artifact targetLevel is unknown")
    if claims["authority"] not in AUTHORITIES:
        raise RenderError("artifact authority is unknown")
    if claims["validationStatus"] not in VALIDATION_STATUSES:
        raise RenderError("artifact validationStatus is unknown")
    require_string_list(claims["testedHosts"], "artifact testedHosts")
    if claims["validationStatus"] == "fixture-only" and claims["testedHosts"]:
        raise RenderError("fixture-only artifact must not claim tested hosts")
    skill_root = artifact_root / "skills"
    discovered = sorted(
        path.parent.name for path in skill_root.glob("*/SKILL.md") if path.is_file()
    )
    if not discovered:
        raise RenderError(f"artifact has zero immediate-child skills: {artifact_root}")
    if discovered != sorted(skill_ids):
        raise RenderError(
            f"artifact source/payload skill inventory mismatch: source={sorted(skill_ids)} "
            f"payload={discovered}"
        )
    for skill in discovered:
        parse_skill_frontmatter(skill_root / skill / "SKILL.md", skill)
    return manifest


def verify_render_root(
    output_root: Path,
    render_config: Dict[str, Any],
) -> Dict[str, Dict[str, Any]]:
    if not output_root.is_dir():
        raise RenderError(f"rendered output directory is absent: {output_root}")
    expected = sorted(render_config["targets"])
    actual = sorted(path.name for path in output_root.iterdir() if path.is_dir())
    root_files = sorted(path.name for path in output_root.iterdir() if not path.is_dir())
    if actual != expected or root_files != [RENDER_INDEX]:
        raise RenderError(
            f"render root inventory mismatch: targets={actual} root_files={root_files} "
            f"expected={expected}"
        )
    index = read_json_object(output_root / RENDER_INDEX, "render index")
    require_exact_keys(
        index, {"$schema", "schemaVersion", "coreVersion", "targets"}, "render index"
    )
    if index["$schema"] != RENDER_INDEX_SCHEMA or index["schemaVersion"] != 1:
        raise RenderError("render index schema identity is invalid")
    if index["coreVersion"] != render_config["package"]["coreVersion"]:
        raise RenderError("render index coreVersion does not match render config")
    indexed_targets = index["targets"]
    if not isinstance(indexed_targets, dict) or sorted(indexed_targets) != expected:
        raise RenderError("render index target inventory does not match render config")
    manifests: Dict[str, Dict[str, Any]] = {}
    for target in expected:
        manifests[target] = verify_artifact(output_root / target, target)
        entry = indexed_targets[target]
        if not isinstance(entry, dict):
            raise RenderError(f"render index target {target} must be an object")
        require_exact_keys(
            entry,
            {
                "artifactId", "packageVersion", "adapterRevision", "artifactSha256",
                "payloadSha256",
            },
            f"render index target {target}",
        )
        expected_entry = {
            "artifactId": manifests[target]["artifactId"],
            "packageVersion": manifests[target]["packageVersion"],
            "adapterRevision": manifests[target]["adapterRevision"],
            "artifactSha256": tree_digest(complete_artifact_records(output_root / target)),
            "payloadSha256": manifests[target]["payload"]["sha256"],
        }
        if entry != expected_entry:
            raise RenderError(f"render index target {target} does not match artifact bytes")
    return manifests


def snapshot_tree(root: Path) -> List[Tuple[str, str, bytes]]:
    snapshot: List[Tuple[str, str, bytes]] = []
    for path in sorted(root.rglob("*"), key=lambda item: item.as_posix()):
        if path.is_file():
            snapshot.append(
                (path.relative_to(root).as_posix(), normalized_mode(path), path.read_bytes())
            )
    return snapshot


def selftest() -> int:
    checks = 0
    failures = 0

    def expect(label: str, predicate: bool) -> None:
        nonlocal checks, failures
        checks += 1
        print(f"  {'PASS' if predicate else 'FAIL'} {label}")
        if not predicate:
            failures += 1

    def expect_error(label: str, call: Any) -> None:
        nonlocal checks, failures
        checks += 1
        try:
            call()
        except RenderError:
            print(f"  PASS {label}")
            return
        except Exception as exc:
            print(f"  FAIL {label}: wrong exception {exc!r}")
            failures += 1
            return
        print(f"  FAIL {label}: no error")
        failures += 1

    def expect_error_containing(label: str, expected: str, call: Any) -> None:
        nonlocal checks, failures
        checks += 1
        try:
            call()
        except RenderError as exc:
            if expected in str(exc):
                print(f"  PASS {label}")
                return
            print(f"  FAIL {label}: wrong error {exc!r}")
            failures += 1
            return
        except Exception as exc:
            print(f"  FAIL {label}: wrong exception {exc!r}")
            failures += 1
            return
        print(f"  FAIL {label}: no error")
        failures += 1

    render_config, adapter_config = load_inputs()
    with tempfile.TemporaryDirectory(prefix="z-harness-render-selftest-") as raw_temp:
        temp = Path(raw_temp)
        first = temp / "first"
        second = temp / "second"
        render_all(ROOT, first, render_config, adapter_config)
        render_all(ROOT, second, render_config, adapter_config)
        expect(
            "same declared inputs produce byte-and-mode-identical trees",
            snapshot_tree(first) == snapshot_tree(second),
        )
        verified = verify_render_root(first, render_config)
        expect(
            "all configured targets verify",
            sorted(verified) == sorted(render_config["targets"]),
        )
        expect(
            "pilot target inventory is pinned to all five supported package surfaces",
            set(render_config["targets"])
            == {"agent-plugins", "codex", "claude", "kimi", "hermes"},
        )
        expect(
            "every artifact discovers the real ground-claims skill",
            all((first / target / "skills/ground-claims/SKILL.md").is_file()
                for target in render_config["targets"]),
        )
        source_evals = sorted((ROOT / "skills/ground-claims/evals").glob("*.json"))
        expect("real source fixture has non-empty excluded evals", bool(source_evals))
        expect(
            "runtime artifacts exclude eval directories",
            all(not (first / target / "skills/ground-claims/evals").exists()
                for target in render_config["targets"]),
        )
        expect(
            "each target has exactly its intended competing-format manifest set",
            all(
                sorted(path for path in COMPETING_MANIFESTS
                       if (first / target / path).is_file())
                == ([] if EXPECTED_MANIFEST_PATHS[target] is None
                    else [EXPECTED_MANIFEST_PATHS[target]])
                for target in render_config["targets"]
            ),
        )
        expect(
            "portable manifest uses the pinned Agent Plugins schema",
            read_json_object(first / "agent-plugins/plugin.json", "portable manifest").get(
                "$schema"
            ) == AGENT_PLUGIN_SCHEMA,
        )
        expect(
            "kimi artifact uses its native skills-only plugin manifest",
            read_json_object(first / "kimi/kimi.plugin.json", "kimi manifest").get(
                "skills"
            ) == "./skills/",
        )
        expect(
            "hermes artifact is a non-executable skill tap, not a Python plugin",
            (first / "hermes/skills/ground-claims/SKILL.md").is_file()
            and not (first / "hermes/plugin.yaml").exists()
            and not (first / "hermes/__init__.py").exists(),
        )
        expect(
            "rendered claims cannot self-promote runtime evidence",
            all(manifest["claims"]["earnedLevel"] == "unverified"
                and manifest["claims"]["testedHosts"] == []
                for manifest in verified.values()),
        )
        expect(
            "every artifact records the exact renderer and canonical config inputs",
            all(
                manifest["build"]["rendererSha256"]
                == sha256_bytes(Path(__file__).resolve().read_bytes())
                and manifest["build"]["renderConfigSha256"]
                == canonical_json_digest(render_config)
                and manifest["build"]["adapterConfigSha256"]
                == canonical_json_digest(adapter_config["targets"][target])
                for target, manifest in verified.items()
            ),
        )
        index = read_json_object(first / RENDER_INDEX, "render index")
        expect(
            "render index binds each complete artifact including its manifest",
            all(
                index["targets"][target]["artifactSha256"]
                == tree_digest(complete_artifact_records(first / target))
                for target in render_config["targets"]
            ),
        )
        split_adapters = json.loads(json.dumps(adapter_config))
        split_adapters["targets"]["codex"]["packageVersion"] = "0.4.0-alpha.2"
        split_output = temp / "split-version"
        split_results = render_all(ROOT, split_output, render_config, split_adapters)
        split_index = read_json_object(split_output / RENDER_INDEX, "split render index")
        expect(
            "target package versions can advance without changing the core version",
            split_results["codex"]["packageVersion"] == "0.4.0-alpha.2"
            and split_results["agent-plugins"]["packageVersion"] == "0.4.0-alpha.1"
            and split_results["codex"]["coreVersion"]
            == split_results["agent-plugins"]["coreVersion"],
        )
        expect(
            "target-only manifest version changes only that target's payload and artifact",
            split_index["targets"]["codex"]["artifactSha256"]
            != index["targets"]["codex"]["artifactSha256"]
            and split_index["targets"]["codex"]["payloadSha256"]
            != index["targets"]["codex"]["payloadSha256"]
            and split_index["targets"]["agent-plugins"]["artifactSha256"]
            == index["targets"]["agent-plugins"]["artifactSha256"],
        )
        expect_error(
            "renderer refuses to overwrite an existing output root",
            lambda: render_all(ROOT, second, render_config, adapter_config),
        )

        fixture_root = temp / "fixture-repo"
        (fixture_root / "skills").mkdir(parents=True)
        shutil.copytree(ROOT / "skills/ground-claims", fixture_root / "skills/ground-claims")
        before_mutation = temp / "before-mutation"
        after_mutation = temp / "after-mutation"
        render_all(fixture_root, before_mutation, render_config, adapter_config)
        expect_error(
            "renderer rejects output paths inside a selected skill source",
            lambda: render_all(
                fixture_root,
                fixture_root / "skills/ground-claims/rendered-artifact",
                render_config,
                adapter_config,
            ),
        )
        contract = fixture_root / "skills/ground-claims/CONTRACT.md"
        contract.write_text(contract.read_text(encoding="utf-8") + "\nmutation\n", encoding="utf-8")
        render_all(fixture_root, after_mutation, render_config, adapter_config)
        before_manifest = read_json_object(
            before_mutation / f"codex/{ARTIFACT_MANIFEST}", "before artifact manifest"
        )
        after_manifest = read_json_object(
            after_mutation / f"codex/{ARTIFACT_MANIFEST}", "after artifact manifest"
        )
        expect(
            "an included source mutation changes source and payload digests",
            before_manifest["source"]["inputTreeSha256"]
            != after_manifest["source"]["inputTreeSha256"]
            and before_manifest["payload"]["sha256"]
            != after_manifest["payload"]["sha256"],
        )

        tampered = before_mutation / "claude/skills/ground-claims/CONTRACT.md"
        tampered.write_text(tampered.read_text(encoding="utf-8") + "tampered\n", encoding="utf-8")
        expect_error(
            "artifact verification rejects a post-render file mutation",
            lambda: verify_artifact(before_mutation / "claude", "claude"),
        )

        write_json(
            before_mutation / "kimi/.kimi-plugin/plugin.json",
            {"name": "shadow-manifest"},
        )
        expect_error_containing(
            "kimi verification rejects competing native manifest locations",
            "manifest isolation failed",
            lambda: verify_artifact(before_mutation / "kimi", "kimi"),
        )

        write_bytes(before_mutation / "hermes/plugin.yaml", b"name: executable-shadow\n")
        expect_error_containing(
            "hermes tap verification rejects executable plugin conversion",
            "manifest isolation failed",
            lambda: verify_artifact(before_mutation / "hermes", "hermes"),
        )

        portable_manifest_path = before_mutation / f"agent-plugins/{ARTIFACT_MANIFEST}"
        portable_manifest = read_json_object(portable_manifest_path, "portable artifact manifest")
        portable_manifest["claims"]["earnedLevel"] = "governed-parity"
        write_json(portable_manifest_path, portable_manifest)
        expect_error(
            "artifact verification rejects render-time compatibility self-promotion",
            lambda: verify_artifact(before_mutation / "agent-plugins", "agent-plugins"),
        )

        codex_manifest_path = before_mutation / f"codex/{ARTIFACT_MANIFEST}"
        codex_manifest = read_json_object(codex_manifest_path, "codex artifact manifest")
        codex_manifest["source"]["skills"][0]["includedTreeSha256"] = "0" * 64
        write_json(codex_manifest_path, codex_manifest)
        expect_error(
            "artifact verification binds included-source provenance to payload bytes",
            lambda: verify_artifact(before_mutation / "codex", "codex"),
        )

        skill_manifest = fixture_root / "skills/ground-claims/SKILL.md"
        original_skill = skill_manifest.read_text(encoding="utf-8")
        skill_manifest.write_text(
            original_skill.replace("name: ground-claims", "name: wrong-name", 1),
            encoding="utf-8",
        )
        expect_error(
            "renderer rejects a skill directory/frontmatter mismatch",
            lambda: render_all(
                fixture_root, temp / "bad-skill-name", render_config, adapter_config
            ),
        )
        skill_manifest.write_text(original_skill, encoding="utf-8")

        linked_skills = fixture_root / "linked-skills"
        linked_skills.symlink_to(fixture_root / "skills", target_is_directory=True)
        linked_config = json.loads(json.dumps(render_config))
        linked_config["sourceSkillsPath"] = "linked-skills"
        expect_error(
            "renderer rejects a symlink in the configured source path",
            lambda: render_all(
                fixture_root,
                temp / "linked-source-root",
                linked_config,
                adapter_config,
            ),
        )

        symlink = fixture_root / "skills/ground-claims/leak"
        symlink.symlink_to(ROOT / "README.md")
        expect_error(
            "renderer rejects symlinks in canonical skill input",
            lambda: render_all(fixture_root, temp / "symlink", render_config, adapter_config),
        )

    print(f"\n  selftest: {failures} failure(s)")
    print(f"SELFTEST-SUMMARY checks={checks} failures={failures}")
    return 1 if failures else 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--output", type=Path, help="new directory to receive rendered targets")
    action.add_argument("--verify", type=Path, help="existing rendered directory to verify")
    action.add_argument("--selftest", action="store_true", help="run planted-failure checks")
    parser.add_argument("--config", type=Path, default=DEFAULT_RENDER_CONFIG)
    parser.add_argument("--adapters", type=Path, default=DEFAULT_ADAPTER_CONFIG)
    parser.add_argument("--version", action="version", version=f"render-packages {VERSION}")
    return parser


def main(argv: Sequence[str]) -> int:
    args = build_parser().parse_args(argv[1:])
    if args.selftest:
        return selftest()
    try:
        render_config, adapter_config = load_inputs(args.config, args.adapters)
        if args.output is not None:
            results = render_all(ROOT, args.output, render_config, adapter_config)
            index = read_json_object(args.output / RENDER_INDEX, "render index")
            for target in sorted(results):
                print(
                    f"{target} artifact_sha256={index['targets'][target]['artifactSha256']} "
                    f"payload_sha256={results[target]['payload']['sha256']}"
                )
            return 0
        results = verify_render_root(args.verify, render_config)
        index = read_json_object(args.verify / RENDER_INDEX, "render index")
        for target in sorted(results):
            print(
                f"{target} artifact_sha256={index['targets'][target]['artifactSha256']} "
                f"payload_sha256={results[target]['payload']['sha256']}"
            )
        return 0
    except RenderError as exc:
        sys.stderr.write(f"render-packages: {exc}\n")
        return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
