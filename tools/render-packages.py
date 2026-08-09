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
from datetime import date
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import sys
import tempfile
import unicodedata
from typing import Any, Dict, Iterable, List, NamedTuple, Optional, Sequence, Tuple


VERSION = "0.4.0"
ROOT = Path(__file__).resolve().parent.parent
DEFAULT_RENDER_CONFIG = ROOT / "release" / "render.json"
DEFAULT_ADAPTER_CONFIG = ROOT / "adapters" / "targets.json"
CONTRACTS = ROOT / "contracts"
VENDORED_SCHEMAS = CONTRACTS / "vendor"
GOLDENS = CONTRACTS / "goldens"
ARTIFACT_MANIFEST = "z-harness-artifact.json"
RENDER_INDEX = "render-index.json"
ARTIFACT_SCHEMA = (
    "https://github.com/ChrisHuie/z-harness/blob/v0.4.0-alpha.2/"
    "contracts/artifact-manifest.schema.json"
)
RENDER_INDEX_SCHEMA = (
    "https://github.com/ChrisHuie/z-harness/blob/v0.4.0-alpha.2/"
    "contracts/render-index.schema.json"
)
AGENT_PLUGIN_SCHEMA = "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json"
ARTIFACT_SCHEMA_FILE = CONTRACTS / "artifact-manifest.schema.json"
RENDER_INDEX_SCHEMA_FILE = CONTRACTS / "render-index.schema.json"
AGENT_PLUGIN_SCHEMA_FILE = VENDORED_SCHEMAS / "agent-plugins-1.0.0.plugin.schema.json"
VENDOR_SOURCES_FILE = VENDORED_SCHEMAS / "SOURCES.json"
NATIVE_MANIFEST_GOLDEN = GOLDENS / "native-manifests.json"
PROJECTION_GOLDEN = GOLDENS / "ground-claims-projection.json"
DIGEST_GOLDEN = GOLDENS / "digests.json"
DIGEST_ALGORITHM = "z-harness-framed-sha256-v2"
FILESYSTEM_PROFILE = "z-harness-posix-tree-v1"
CONTRACT_FILES = (
    Path(__file__).resolve(),
    ARTIFACT_SCHEMA_FILE,
    RENDER_INDEX_SCHEMA_FILE,
    AGENT_PLUGIN_SCHEMA_FILE,
    NATIVE_MANIFEST_GOLDEN,
    PROJECTION_GOLDEN,
    DIGEST_GOLDEN,
)
SEMVER = re.compile(
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?"
    r"(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?$"
)
SKILL_NAME = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
# Agent Skills specification, "Frontmatter": name is "Max 64 characters", description
# "Max 1024 characters. Non-empty." Hand-transcribed from prose at
# https://agentskills.io/specification -- that authority publishes no machine schema to
# vendor, so these two constants have no local pinned source to diff against.
SKILL_NAME_MAX = 64
SKILL_DESCRIPTION_MAX = 1024
PACKAGE_NAME = re.compile(r"^[a-z0-9]+(?:[.-][a-z0-9]+)*$")
KIMI_PLUGIN_NAME = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")
# YAML indicators that change a scalar's meaning. The renderer reads frontmatter without
# a YAML dependency, so any form it cannot faithfully decode is refused by name rather
# than mis-decoded: "description: >-" would otherwise validate as the 2-char string ">-".
YAML_UNSUPPORTED_LEADERS = ">|&*!{[]},%@`"
EXPECTED_MANIFEST_PATHS = {
    "agent-plugins": "plugin.json",
    "codex": ".codex-plugin/plugin.json",
    "claude": ".claude-plugin/plugin.json",
    "kimi": "kimi.plugin.json",
    "hermes": None,
}
EXPECTED_FORMATS = {
    "agent-plugins": "agent-plugins/1.0.0",
    "codex": "codex-plugin/native",
    "claude": "claude-plugin/native",
    "kimi": "kimi-code-plugin/native",
    "hermes": "hermes-skill-tap/github",
}
COMPETING_MANIFESTS = {
    "plugin.json",
    ".codex-plugin/plugin.json",
    ".claude-plugin/plugin.json",
    "kimi.plugin.json",
    ".kimi-plugin/plugin.json",
    "plugin.yaml",
}
WINDOWS_RESERVED_NAMES = {
    "CON", "PRN", "AUX", "NUL", "CONIN$", "CONOUT$",
    *(f"COM{suffix}" for suffix in "123456789\u00b9\u00b2\u00b3"),
    *(f"LPT{suffix}" for suffix in "123456789\u00b9\u00b2\u00b3"),
}
VENDOR_SOURCE_KEYS = {
    "id", "file", "url", "publishedUrl", "upstreamRepository", "revision",
    "sourcePath", "sha256", "license", "licensePath", "licenseSha256",
    "retrieved", "governs",
}
HOST_BODY_CONSTRUCTS = (
    ("skill.body.arguments", re.compile(r"\$ARGUMENTS(?:\[[^\]]+\]|\.[A-Za-z_][\w-]*)?|\$[0-9]+")),
    ("skill.body.claude_variable", re.compile(
        r"\$(?:\{CLAUDE_[^}\r\n]+\}|CLAUDE_[A-Za-z0-9_]+)"
    )),
    ("skill.body.dynamic_command", re.compile(r"!`|^```!", re.M)),
    ("skill.body.frontmatter_directive", re.compile(
        r"(?im)^(?:context\s*:\s*fork|agent|model|background|hooks|shell|"
        r"allowed-tools|argument-hint|disable-model-invocation|user-invocable)\s*:"
    )),
    ("skill.body.ultrathink", re.compile(r"(?i)\bultrathink\b")),
)


class RenderError(Exception):
    """A deterministic failure with a stable machine code and human detail."""

    def __init__(self, code: str, detail: Optional[str] = None):
        if detail is None:
            detail = code
            code = "render.invalid"
        self.code = code
        self.detail = detail
        super().__init__(f"{code}: {detail}")


def read_json_object(path: Path, label: str) -> Dict[str, Any]:
    def reject_duplicate_keys(pairs: Sequence[Tuple[str, Any]]) -> Dict[str, Any]:
        value: Dict[str, Any] = {}
        for key, member in pairs:
            if key in value:
                raise RenderError(
                    "json.duplicate_key",
                    f"{label} repeats JSON key {key!r}: {path}",
                )
            value[key] = member
        return value

    def reject_nonfinite(token: str) -> Any:
        raise RenderError(
            "json.nonfinite",
            f"{label} contains non-finite JSON number {token}: {path}",
        )

    try:
        value = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=reject_duplicate_keys,
            parse_constant=reject_nonfinite,
        )
    except OSError as exc:
        raise RenderError(f"cannot read {label} {path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise RenderError(f"{label} is not valid JSON: {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise RenderError(f"{label} must contain a JSON object: {path}")
    return value


def load_vendor_sources(path: Path = VENDOR_SOURCES_FILE) -> List[Dict[str, Any]]:
    value = read_json_object(path, "vendored sources")
    if set(value) != {"schemaVersion", "note", "sources"}:
        raise RenderError(
            "vendor.sources_shape", "vendored sources has missing or unknown fields"
        )
    if value["schemaVersion"] != 1 or not isinstance(value["note"], str):
        raise RenderError(
            "vendor.sources_shape", "vendored sources must be a schemaVersion 1 record"
        )
    sources = value["sources"]
    if not isinstance(sources, list) or not sources:
        raise RenderError("vendor.sources_shape", "vendored source inventory is empty")
    root = path.parent.resolve()
    observed_ids: set[str] = set()
    observed_files: set[str] = set()
    validated: List[Dict[str, Any]] = []
    for position, source in enumerate(sources):
        if not isinstance(source, dict) or set(source) != VENDOR_SOURCE_KEYS:
            raise RenderError(
                "vendor.source_shape",
                f"vendored source {position} has missing or unknown fields",
            )
        source_id = source["id"]
        relative_file = source["file"]
        if (
            not isinstance(source_id, str)
            or not source_id
            or source_id in observed_ids
            or not isinstance(relative_file, str)
            or not relative_file
            or relative_file in observed_files
        ):
            raise RenderError(
                "vendor.source_identity", "vendored source ids and files must be unique"
            )
        repository = source["upstreamRepository"]
        revision = source["revision"]
        source_path = source["sourcePath"]
        license_path = source["licensePath"]
        repository_match = re.fullmatch(
            r"https://github\.com/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)",
            str(repository),
        )
        if (
            repository_match is None
            or re.fullmatch(r"[0-9a-f]{40}", str(revision)) is None
            or any(
                not isinstance(relative, str)
                or not relative
                or "\\" in relative
                or any(part in ("", ".", "..") for part in relative.split("/"))
                or any(
                    re.fullmatch(r"[A-Za-z0-9_.-]+", part) is None
                    for part in relative.split("/")
                )
                for relative in (source_path, license_path)
            )
        ):
            raise RenderError(
                "vendor.source_identity", f"invalid upstream identity for {source_id!r}"
            )
        owner, repository_name = repository_match.groups()
        expected_url = (
            f"https://raw.githubusercontent.com/{owner}/{repository_name}/"
            f"{revision}/{source_path}"
        )
        if source["url"] != expected_url:
            raise RenderError(
                "vendor.source_url",
                f"vendored source URL does not derive from its identity: {source_id!r}",
            )
        if not str(source["publishedUrl"]).startswith("https://"):
            raise RenderError(
                "vendor.source_identity", f"invalid published URL for {source_id!r}"
            )
        if any(
            re.fullmatch(r"[0-9a-f]{64}", str(source[field])) is None
            for field in ("sha256", "licenseSha256")
        ):
            raise RenderError(
                "vendor.source_identity", f"invalid digest for {source_id!r}"
            )
        try:
            retrieved = date.fromisoformat(source["retrieved"])
        except (TypeError, ValueError):
            raise RenderError(
                "vendor.source_identity", f"invalid retrieval date for {source_id!r}"
            )
        if retrieved.isoformat() != source["retrieved"]:
            raise RenderError(
                "vendor.source_identity", f"non-canonical retrieval date for {source_id!r}"
            )
        if (
            not isinstance(relative_file, str)
            or not relative_file
            or "\\" in relative_file
            or any(part in ("", ".", "..") for part in relative_file.split("/"))
        ):
            raise RenderError(
                "vendor.source_identity", f"invalid file for {source_id!r}"
            )
        candidate = path.parent / relative_file
        local = candidate.resolve()
        if (
            root not in local.parents
            or candidate.is_symlink()
            or not local.is_file()
        ):
            raise RenderError(
                "vendor.source_file", f"absent or escaped file for {source_id!r}"
            )
        if sha256_bytes(local.read_bytes()) != source["sha256"]:
            raise RenderError(
                "vendor.source_digest", f"vendored source digest mismatch for {source_id!r}"
            )
        if not all(
            isinstance(source[field], str) and source[field]
            for field in ("license", "governs")
        ):
            raise RenderError(
                "vendor.source_identity", f"empty license or scope for {source_id!r}"
            )
        observed_ids.add(source_id)
        observed_files.add(relative_file)
        validated.append(source)
    return validated


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
            "runtimeExcludeFiles",
            "targets",
        },
        "render config",
    )
    if render_config["schemaVersion"] != 2:
        raise RenderError("config.schema_version", "render config schemaVersion must be 2")
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
    excluded_files = require_string_list(
        render_config["runtimeExcludeFiles"], "runtimeExcludeFiles"
    )
    for excluded in excluded_files:
        if Path(excluded).name != excluded or excluded in (".", ".."):
            raise RenderError("runtimeExcludeFiles entries must be immediate file names")
    if "SKILL.md" in excluded_files:
        raise RenderError("runtimeExcludeFiles must not exclude SKILL.md")
    targets = require_string_list(render_config["targets"], "targets", nonempty=True)

    require_exact_keys(adapter_config, {"schemaVersion", "targets"}, "adapter config")
    if adapter_config["schemaVersion"] != 2:
        raise RenderError("adapter.schema_version", "adapter config schemaVersion must be 2")
    adapters = adapter_config["targets"]
    if not isinstance(adapters, dict) or not adapters:
        raise RenderError("adapter config targets must be a non-empty object")
    if sorted(adapters) != sorted(targets):
        raise RenderError(
            "adapter.target_inventory",
            f"adapter target inventory must exactly equal render targets: "
            f"adapters={sorted(adapters)} render={sorted(targets)}",
        )
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
        if adapter["format"] != EXPECTED_FORMATS[target]:
            raise RenderError(
                "adapter.format",
                f"adapter {target} format must be {EXPECTED_FORMATS[target]!r}",
            )
        if adapter["manifestPath"] != EXPECTED_MANIFEST_PATHS[target]:
            raise RenderError(f"adapter {target} manifestPath is not the implemented path")
    return render_config, adapter_config


def decode_scalar(raw: str, label: str) -> str:
    value = raw.strip()
    if not value:
        raise RenderError(f"{label} must be a single-line scalar")
    if value[0] in YAML_UNSUPPORTED_LEADERS:
        raise RenderError(
            f"{label} uses YAML syntax this reader does not decode ({value[0]!r}): "
            f"write it as a single-line plain, single-quoted, or double-quoted scalar"
        )
    if value[0] in "-?:" and (len(value) == 1 or value[1].isspace()):
        raise RenderError(
            "skill.frontmatter_ambiguous_plain_scalar",
            f"{label} uses a YAML indicator: quote the scalar",
        )
    if value.startswith('"'):
        try:
            decoded = json.loads(value)
        except json.JSONDecodeError as exc:
            raise RenderError(f"{label} has invalid quoted text") from exc
        return require_nonempty_string(decoded, label)
    if value.startswith("'"):
        if not value.endswith("'") or len(value) < 2:
            raise RenderError(f"{label} has invalid quoted text")
        interior = value[1:-1]
        if "'" in interior.replace("''", ""):
            raise RenderError(f"{label} has an unpaired single quote")
        return require_nonempty_string(interior.replace("''", "'"), label)
    if re.search(r"(^|[ \t])#", value) or re.search(r":[ \t]", value):
        raise RenderError(
            "skill.frontmatter_ambiguous_plain_scalar",
            f"{label} uses YAML comment or mapping syntax: quote the scalar",
        )
    if (
        value.casefold() in {"null", "~", "true", "false", ".nan", ".inf", "+.inf", "-.inf"}
        or re.fullmatch(r"[-+]?(?:0|[1-9]\d*)(?:\.\d+)?(?:[eE][-+]?\d+)?", value)
        or re.fullmatch(r"\d{4}-\d{2}-\d{2}(?:[Tt ].*)?", value)
    ):
        raise RenderError(
            "skill.frontmatter_ambiguous_plain_scalar",
            f"{label} has a YAML implicit type: quote the scalar",
        )
    return value


class SkillDocument(NamedTuple):
    values: Dict[str, str]
    argument_hint: Optional[str]
    body: bytes


def parse_skill_document(path: Path, expected_name: str) -> SkillDocument:
    try:
        raw = path.read_bytes()
        text = raw.decode("utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise RenderError(f"cannot read skill manifest {path}: {exc}") from exc
    if not raw.startswith(b"---\n"):
        raise RenderError(f"skill {expected_name} has no opening YAML frontmatter delimiter")
    closing = raw.find(b"\n---\n", 4)
    if closing < 0:
        raise RenderError(f"skill {expected_name} has no closing frontmatter delimiter")
    frontmatter = raw[4:closing].decode("utf-8")
    body = raw[closing + 5:]
    values: Dict[str, str] = {}
    argument_hint: Optional[str] = None
    top_keys: List[str] = []
    metadata_keys: List[str] = []
    current = ""
    for line in frontmatter.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if line[0].isspace():
            if current != "metadata" or not line.startswith("  ") or ":" not in line:
                raise RenderError(
                    "skill.frontmatter_unknown",
                    f"skill {expected_name} has unsupported nested frontmatter: {line!r}",
                )
            key, scalar = line.strip().split(":", 1)
            metadata_keys.append(key)
            if key != "version":
                raise RenderError(
                    "skill.frontmatter_unknown",
                    f"skill {expected_name} metadata key {key!r} is not portable",
                )
            values["version"] = decode_scalar(
                scalar, f"skill {expected_name} metadata.version"
            )
            continue
        if ":" not in line:
            raise RenderError(
                "skill.frontmatter_unknown",
                f"skill {expected_name} has unsupported frontmatter line: {line!r}",
            )
        key, scalar = line.split(":", 1)
        if key in top_keys:
            raise RenderError(
                "skill.frontmatter_duplicate",
                f"skill {expected_name} repeats frontmatter key {key!r}",
            )
        top_keys.append(key)
        current = key
        if key in ("name", "description"):
            values[key] = decode_scalar(scalar, f"skill {expected_name} {key}")
        elif key == "argument-hint":
            argument_hint = decode_scalar(scalar, f"skill {expected_name} argument-hint")
        elif key == "allowed-tools":
            decode_scalar(scalar, f"skill {expected_name} allowed-tools")
        elif key == "metadata":
            if scalar.strip():
                raise RenderError(
                    "skill.frontmatter_unknown",
                    f"skill {expected_name} metadata must be a mapping",
                )
        else:
            raise RenderError(
                "skill.frontmatter_unknown",
                f"skill {expected_name} top-level key {key!r} has no target classification",
            )
    if set(values) != {"name", "description", "version"}:
        raise RenderError(
            f"skill {expected_name} requires name, description, and metadata.version"
        )
    if metadata_keys != ["version"]:
        raise RenderError(f"skill {expected_name} metadata must contain only version")
    if values["name"] != expected_name:
        raise RenderError(
            f"skill directory/name mismatch: directory={expected_name!r} "
            f"frontmatter={values['name']!r}"
        )
    if SKILL_NAME.fullmatch(values["name"]) is None:
        raise RenderError(f"skill name is not portable kebab-case: {values['name']!r}")
    if len(values["name"]) > SKILL_NAME_MAX:
        raise RenderError(
            f"skill name exceeds the Agent Skills {SKILL_NAME_MAX}-character limit: "
            f"{len(values['name'])} characters"
        )
    if not 1 <= len(values["description"]) <= SKILL_DESCRIPTION_MAX:
        raise RenderError(
            f"skill {expected_name} description must be 1-{SKILL_DESCRIPTION_MAX} characters"
        )
    if SEMVER.fullmatch(values["version"]) is None:
        raise RenderError(f"skill {expected_name} metadata.version must be semantic versioning")
    for code, pattern in HOST_BODY_CONSTRUCTS:
        match = pattern.search(body.decode("utf-8"))
        if match:
            raise RenderError(
                code,
                f"skill {expected_name} body uses unclassified host construct {match.group(0)!r}",
            )
    return SkillDocument(values, argument_hint, body)


def parse_skill_frontmatter(path: Path, expected_name: str) -> Dict[str, str]:
    return parse_skill_document(path, expected_name).values


def projected_skill_bytes(path: Path, expected_name: str, target: str) -> bytes:
    document = parse_skill_document(path, expected_name)
    values = document.values
    lines = [
        "---",
        f"name: {json.dumps(values['name'], ensure_ascii=False)}",
        f"description: {json.dumps(values['description'], ensure_ascii=False)}",
    ]
    if target == "claude" and document.argument_hint is not None:
        lines.append(
            f"argument-hint: {json.dumps(document.argument_hint, ensure_ascii=False)}"
        )
    lines += [
        "metadata:",
        f"  version: {json.dumps(values['version'], ensure_ascii=False)}",
        "---",
    ]
    return ("\n".join(lines) + "\n").encode("utf-8") + document.body


def normalized_mode(path: Path) -> str:
    mode = stat.S_IMODE(path.stat().st_mode)
    return "0755" if mode & 0o111 else "0644"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _frame(digest: Any, value: bytes) -> None:
    digest.update(len(value).to_bytes(8, "big"))
    digest.update(value)


def framed_digest(domain: str, values: Sequence[bytes]) -> str:
    digest = hashlib.sha256()
    _frame(digest, DIGEST_ALGORITHM.encode("ascii"))
    _frame(digest, domain.encode("utf-8"))
    for value in values:
        _frame(digest, value)
    return digest.hexdigest()


def canonical_json_digest(value: Any, domain: str) -> str:
    data = json.dumps(
        value, ensure_ascii=False, separators=(",", ":"), sort_keys=True,
        allow_nan=False,
    ).encode("utf-8")
    return framed_digest(domain, [data])


def file_record(path: Path, relative: str) -> Dict[str, Any]:
    data = path.read_bytes()
    return {
        "path": relative,
        "mode": normalized_mode(path),
        "size": len(data),
        "sha256": sha256_bytes(data),
    }


def tree_digest(records: Sequence[Dict[str, Any]], domain: str) -> str:
    values: List[bytes] = []
    for record in sorted(records, key=lambda item: item["path"]):
        values.extend(
            str(record[key]).encode("utf-8")
            for key in ("path", "mode", "size", "sha256")
        )
    return framed_digest(domain, values)


def scan_skill(
    skill_dir: Path,
    skill_name: str,
    excluded_directories: Sequence[str],
    excluded_files: Sequence[str] = (),
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[str]]:
    if not skill_dir.is_dir():
        raise RenderError(f"selected skill directory is absent: {skill_dir}")
    if skill_dir.is_symlink():
        raise RenderError(f"selected skill directory must not be a symlink: {skill_dir}")
    parse_skill_frontmatter(skill_dir / "SKILL.md", skill_name)
    all_records: List[Dict[str, Any]] = []
    included: List[Dict[str, Any]] = []
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
        parts = Path(relative).parts
        immediate_file = len(parts) == 1 and parts[0] in excluded_files
        if parts[0] in excluded_directories or immediate_file:
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
    write_bytes(path, json_bytes(value))


def json_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n"
    ).encode("utf-8")


def record_for_bytes(relative: str, data: bytes, mode: str = "0644") -> Dict[str, Any]:
    return {"path": relative, "mode": mode, "size": len(data), "sha256": sha256_bytes(data)}


def copy_skill_payload(
    source_dir: Path,
    target_dir: Path,
    included: Sequence[Dict[str, Any]],
    target: str,
) -> None:
    for record in sorted(included, key=lambda item: item["path"]):
        source = source_dir / record["path"]
        destination = target_dir / record["path"]
        data = (
            projected_skill_bytes(source, source_dir.name, target)
            if record["path"] == "SKILL.md"
            else source.read_bytes()
        )
        write_bytes(destination, data, record["mode"])


def portable_path_key(relative: str) -> str:
    if not relative or relative.startswith("/") or "\\" in relative or "\0" in relative:
        raise RenderError("tree.path_nonportable", f"non-portable path {relative!r}")
    parts = relative.split("/")
    for part in parts:
        # Win32 also reserves device names with an extension, spaces immediately
        # before that extension, and the superscript 1/2/3 COM/LPT aliases.
        base = part.partition(".")[0].rstrip(" ").upper()
        if (
            part in ("", ".", "..")
            or part.endswith((" ", "."))
            or any(char in '<>:"|?*' for char in part)
            or any(ord(char) < 32 for char in part)
            or base in WINDOWS_RESERVED_NAMES
        ):
            raise RenderError("tree.path_nonportable", f"non-portable path {relative!r}")
    normalized = unicodedata.normalize("NFC", relative)
    if normalized != relative:
        raise RenderError(
            "tree.path_nonportable",
            f"non-portable non-NFC path {relative!r}",
        )
    return normalized.casefold()


def verify_path_aliases(paths: Sequence[str]) -> None:
    aliases: Dict[str, str] = {}
    for path in paths:
        prefixes = ["/".join(path.split("/")[:index]) for index in range(1, len(path.split("/")) + 1)]
        for prefix in prefixes:
            key = portable_path_key(prefix)
            prior = aliases.get(key)
            if prior is not None and prior != prefix:
                raise RenderError(
                    "tree.path_alias",
                    f"portable path alias collision: {prior!r} and {prefix!r}",
                )
            aliases[key] = prefix


def inspect_physical_tree(root: Path, *, normalized: bool) -> List[str]:
    try:
        root_stat = root.lstat()
    except OSError as exc:
        raise RenderError("tree.root_absent", f"cannot inspect render root {root}: {exc}") from exc
    if not stat.S_ISDIR(root_stat.st_mode):
        raise RenderError("tree.root_type", f"render root is not a directory: {root}")
    paths: List[str] = []
    seen_inodes: Dict[Tuple[int, int], str] = {}
    directories: List[Tuple[str, os.stat_result]] = [(".", root_stat)]
    for dirpath, dirnames, filenames in os.walk(root, topdown=True, followlinks=False):
        directory = Path(dirpath)
        names = sorted(dirnames + filenames)
        if not names:
            raise RenderError(
                "tree.empty_directory",
                f"rendered tree contains an empty directory: {directory}",
            )
        for name in names:
            path = directory / name
            relative = path.relative_to(root).as_posix()
            info = path.lstat()
            if stat.S_ISLNK(info.st_mode):
                raise RenderError("tree.symlink", f"rendered tree contains a symlink: {path}")
            if stat.S_ISDIR(info.st_mode):
                directories.append((relative, info))
                paths.append(relative)
                continue
            if not stat.S_ISREG(info.st_mode):
                raise RenderError(
                    "tree.non_regular",
                    f"rendered tree contains a non-regular file: {path}",
                )
            if info.st_nlink != 1:
                raise RenderError(
                    "tree.hardlink",
                    f"rendered file has link count {info.st_nlink}, expected 1: {path}",
                )
            inode = (info.st_dev, info.st_ino)
            prior = seen_inodes.get(inode)
            if prior is not None:
                raise RenderError(
                    "tree.hardlink",
                    f"rendered files share an inode: {prior!r} and {relative!r}",
                )
            seen_inodes[inode] = relative
            paths.append(relative)
            if normalized:
                expected_mode = 0o755 if info.st_mode & 0o111 else 0o644
                if stat.S_IMODE(info.st_mode) != expected_mode or info.st_mtime_ns != 0:
                    raise RenderError(
                        "tree.file_profile",
                        f"rendered file violates mode/mtime profile: {path}",
                    )
    if normalized:
        for relative, info in directories:
            if stat.S_IMODE(info.st_mode) != 0o755 or info.st_mtime_ns != 0:
                raise RenderError(
                    "tree.directory_profile",
                    f"rendered directory violates 0755/epoch profile: {relative}",
                )
    verify_path_aliases(paths)
    return paths


def normalize_physical_tree(root: Path) -> None:
    inspect_physical_tree(root, normalized=False)
    directories: List[Path] = []
    for dirpath, dirnames, filenames in os.walk(root, topdown=True, followlinks=False):
        directory = Path(dirpath)
        directories.append(directory)
        for filename in filenames:
            path = directory / filename
            info = path.lstat()
            mode = 0o755 if info.st_mode & 0o111 else 0o644
            path.chmod(mode)
            os.utime(path, ns=(0, 0), follow_symlinks=False)
    for directory in reversed(directories):
        directory.chmod(0o755)
        os.utime(directory, ns=(0, 0), follow_symlinks=False)
    inspect_physical_tree(root, normalized=True)


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


def golden_native_manifests() -> Dict[str, Any]:
    value = read_json_object(NATIVE_MANIFEST_GOLDEN, "native manifest golden")
    require_exact_keys(value, EXPECTED_MANIFEST_PATHS, "native manifest golden")
    return value


def expected_payload_records(
    scan: "SourceScan",
    target: str,
) -> List[Dict[str, Any]]:
    records: List[Dict[str, Any]] = []
    for skill_name, included in sorted(scan.included_by_skill.items()):
        for source_record in sorted(included, key=lambda item: item["path"]):
            source = scan.source_root / skill_name / source_record["path"]
            data = (
                projected_skill_bytes(source, skill_name, target)
                if source_record["path"] == "SKILL.md"
                else source.read_bytes()
            )
            records.append(record_for_bytes(
                f"skills/{skill_name}/{source_record['path']}",
                data,
                source_record["mode"],
            ))
    manifest_path = EXPECTED_MANIFEST_PATHS[target]
    native = golden_native_manifests()[target]
    if manifest_path is None:
        if native is not None:
            raise RenderError(
                "manifest.golden_invalid", f"{target} absence golden must be null"
            )
    else:
        if not isinstance(native, dict):
            raise RenderError(
                "manifest.golden_invalid", f"{target} native manifest golden must be an object"
            )
        records.append(record_for_bytes(manifest_path, json_bytes(native)))
    return sorted(records, key=lambda item: item["path"])


def artifact_records(
    artifact_root: Path,
    *,
    include_manifest: bool,
) -> List[Dict[str, str]]:
    """Inventory a rendered target directory.

    The payload inventory omits the artifact manifest because a manifest cannot contain a
    digest of itself; the render index hashes the complete directory instead.
    """
    inspect_physical_tree(artifact_root, normalized=False)
    records: List[Dict[str, Any]] = []
    for path in sorted(artifact_root.rglob("*"), key=lambda item: item.as_posix()):
        if path.is_symlink():
            raise RenderError(f"rendered artifact contains a symlink: {path}")
        if path.is_dir():
            continue
        if not path.is_file():
            raise RenderError(f"rendered artifact contains a non-regular file: {path}")
        relative = path.relative_to(artifact_root).as_posix()
        if not include_manifest and relative == ARTIFACT_MANIFEST:
            continue
        records.append(file_record(path, relative))
    if not records:
        scope = "files" if include_manifest else "payload files"
        raise RenderError(f"artifact has zero {scope}: {artifact_root}")
    return records


def payload_records(artifact_root: Path) -> List[Dict[str, Any]]:
    return artifact_records(artifact_root, include_manifest=False)


def complete_artifact_records(artifact_root: Path) -> List[Dict[str, Any]]:
    return artifact_records(artifact_root, include_manifest=True)


# Split deliberately. A keyword listed as supported but never evaluated is the silent
# hatch this reader exists to avoid, so metadata that carries no constraint is named
# separately from the keywords with a branch below, and a selftest asserts each
# constraint keyword actually rejects a violating value.
SCHEMA_METADATA_KEYWORDS = {"$schema", "$id", "$defs", "title", "description"}
SCHEMA_CONSTRAINT_KEYWORDS = {
    "$ref", "type", "const", "enum", "required", "properties", "additionalProperties",
    "propertyNames", "minLength", "maxLength", "pattern", "items", "minItems",
    "minProperties", "minimum",
}
SUPPORTED_SCHEMA_KEYWORDS = SCHEMA_METADATA_KEYWORDS | SCHEMA_CONSTRAINT_KEYWORDS
JSON_TYPES = {
    "object": dict, "array": list, "string": str, "integer": int,
    "number": (int, float), "boolean": bool, "null": type(None),
}


def load_schema(path: Path) -> Dict[str, Any]:
    return read_json_object(path, f"schema {path.name}")


def conform_to_schema(
    value: Any,
    schema: Dict[str, Any],
    label: str,
    root: Optional[Dict[str, Any]] = None,
) -> None:
    """Validate `value` against the subset of JSON Schema these contracts use.

    An unrecognised keyword raises instead of being skipped: a validator that silently
    ignores what it cannot evaluate reports a clean result over an unchecked constraint.
    Written against the stdlib so the renderer keeps no third-party dependency, matching
    the Agent Plugins loading rule that a client selects locally supported validation
    rules rather than retrieving a schema.
    """
    root = schema if root is None else root
    unknown = sorted(set(schema) - SUPPORTED_SCHEMA_KEYWORDS)
    if unknown:
        raise RenderError(f"{label}: schema uses unsupported keywords {unknown}")
    if "$ref" in schema:
        siblings = sorted(set(schema) - {"$ref"} - SCHEMA_METADATA_KEYWORDS)
        if siblings:
            raise RenderError(f"{label}: $ref alongside unapplied keywords {siblings}")
        ref = schema["$ref"]
        if not isinstance(ref, str) or not ref.startswith("#/"):
            raise RenderError(f"{label}: only local $ref is supported, got {ref!r}")
        target: Any = root
        for part in ref[2:].split("/"):
            if not isinstance(target, dict) or part not in target:
                raise RenderError(f"{label}: unresolvable $ref {ref!r}")
            target = target[part]
        conform_to_schema(value, target, label, root)
        return
    if "const" in schema and value != schema["const"]:
        raise RenderError(f"{label}: expected {schema['const']!r}, got {value!r}")
    if "enum" in schema and value not in schema["enum"]:
        raise RenderError(f"{label}: {value!r} is not one of {schema['enum']}")
    declared = schema.get("type")
    if declared is not None:
        if declared not in JSON_TYPES:
            raise RenderError(f"{label}: unsupported schema type {declared!r}")
        expected = JSON_TYPES[declared]
        numeric = declared in ("integer", "number")
        if not isinstance(value, expected) or (numeric and isinstance(value, bool)):
            raise RenderError(f"{label}: expected {declared}, got {type(value).__name__}")
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if "minimum" in schema and value < schema["minimum"]:
            raise RenderError(f"{label}: {value} is below minimum {schema['minimum']}")
    if isinstance(value, str):
        if "minLength" in schema and len(value) < schema["minLength"]:
            raise RenderError(f"{label}: shorter than minLength {schema['minLength']}")
        if "maxLength" in schema and len(value) > schema["maxLength"]:
            raise RenderError(
                f"{label}: {len(value)} characters exceeds maxLength {schema['maxLength']}"
            )
        if "pattern" in schema and re.search(schema["pattern"], value) is None:
            raise RenderError(f"{label}: {value!r} does not match {schema['pattern']!r}")
    if isinstance(value, list):
        if "minItems" in schema and len(value) < schema["minItems"]:
            raise RenderError(
                f"{label}: {len(value)} items is fewer than minItems {schema['minItems']}"
            )
        item_schema = schema.get("items")
        if isinstance(item_schema, dict):
            for index, item in enumerate(value):
                conform_to_schema(item, item_schema, f"{label}[{index}]", root)
    if isinstance(value, dict):
        if "minProperties" in schema and len(value) < schema["minProperties"]:
            raise RenderError(
                f"{label}: {len(value)} properties is fewer than "
                f"minProperties {schema['minProperties']}"
            )
        for name in schema.get("required", []):
            if name not in value:
                raise RenderError(f"{label}: required property {name!r} is absent")
        properties = schema.get("properties", {})
        extra = schema.get("additionalProperties", True)
        names = schema.get("propertyNames")
        for key, member in sorted(value.items()):
            where = f"{label}.{key}"
            if isinstance(names, dict):
                conform_to_schema(key, names, f"{where} (property name)", root)
            if key in properties:
                conform_to_schema(member, properties[key], where, root)
            elif extra is False:
                raise RenderError(f"{label}: property {key!r} is not permitted")
            elif isinstance(extra, dict):
                conform_to_schema(member, extra, where, root)


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
    golden = golden_native_manifests()[target]
    if manifest_relative is None:
        if target != "hermes":
            raise RenderError(f"target {target} unexpectedly has no native manifest")
        if golden is not None:
            raise RenderError("manifest.golden_invalid", "Hermes absence golden is not null")
        return
    manifest_path = artifact_root / manifest_relative
    manifest = read_json_object(manifest_path, f"{target} package manifest")
    if manifest != golden or manifest_path.read_bytes() != json_bytes(golden):
        raise RenderError(
            "manifest.golden_mismatch",
            f"{target} native manifest differs from the hand-authored byte golden",
        )
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


def renderer_digest() -> str:
    return sha256_bytes(Path(__file__).resolve().read_bytes())


def derived_build(render_config: Dict[str, Any], adapter: Dict[str, Any]) -> Dict[str, str]:
    """The build record an artifact must carry for these exact inputs.

    Rendering writes this and verification recomputes it, so a manifest cannot record a
    renderer or configuration it was not produced from. Both sides call the same digest
    helpers, so this binds artifact to inputs and cannot detect a fault inside
    `canonical_json_digest` itself.
    """
    return {
        "renderer": "z-harness/render-packages",
        "rendererVersion": VERSION,
        "digestAlgorithm": DIGEST_ALGORITHM,
        "filesystemProfile": FILESYSTEM_PROFILE,
        "rendererSha256": renderer_digest(),
        "contractsSha256": tree_digest(
            [
                file_record(path, path.relative_to(ROOT).as_posix())
                for path in CONTRACT_FILES
            ],
            "build.contracts",
        ),
        "renderConfigSha256": canonical_json_digest(render_config, "config.render"),
        "adapterConfigSha256": canonical_json_digest(adapter, "config.adapter-entry"),
    }


def derived_upstream_locks(render_config: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Upstream locks the render inputs authorise. Nothing declares an upstream yet."""
    return []


class SourceScan(NamedTuple):
    """One reading of the selected skill sources, shared by rendering and verification."""

    source_root: Path
    skills: List[Dict[str, Any]]
    aggregate_input: List[Dict[str, Any]]
    aggregate_included: List[Dict[str, Any]]
    included_by_skill: Dict[str, List[Dict[str, Any]]]


def scan_selected_skills(repo_root: Path, render_config: Dict[str, Any]) -> SourceScan:
    source_root = resolve_source_skills_root(repo_root, render_config)
    excluded_directories = render_config["runtimeExcludeDirectories"]
    excluded_files = render_config["runtimeExcludeFiles"]
    skills: List[Dict[str, Any]] = []
    aggregate_input: List[Dict[str, Any]] = []
    aggregate_included: List[Dict[str, Any]] = []
    included_by_skill: Dict[str, List[Dict[str, Any]]] = {}
    for skill_name in sorted(render_config["selectedSkills"]):
        all_records, included, excluded = scan_skill(
            source_root / skill_name, skill_name, excluded_directories, excluded_files
        )
        skills.append({
            "id": skill_name,
            "inputTreeSha256": tree_digest(all_records, f"source.skill.{skill_name}.input"),
            "includedTreeSha256": tree_digest(
                included, f"source.skill.{skill_name}.selected"
            ),
            "includedFiles": len(included),
            "excludedPaths": sorted(excluded),
        })
        included_by_skill[skill_name] = included
        for record in all_records:
            aggregate_input.append({**record, "path": f"{skill_name}/{record['path']}"})
        for record in included:
            aggregate_included.append({**record, "path": f"{skill_name}/{record['path']}"})
    return SourceScan(
        source_root, skills, aggregate_input, aggregate_included, included_by_skill
    )


def render_target(
    repo_root: Path,
    target_root: Path,
    target: str,
    render_config: Dict[str, Any],
    adapter_config: Dict[str, Any],
) -> Dict[str, Any]:
    package = render_config["package"]
    adapter = adapter_config["targets"][target]
    scan = scan_selected_skills(repo_root, render_config)
    skill_manifests = scan.skills
    aggregate_input = scan.aggregate_input
    aggregate_included = scan.aggregate_included

    target_root.mkdir(parents=True, exist_ok=False)
    for skill_name, included in sorted(scan.included_by_skill.items()):
        copy_skill_payload(
            scan.source_root / skill_name,
            target_root / "skills" / skill_name,
            included,
            target,
        )

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
        "schemaVersion": 2,
        "artifactId": f"{package['name']}/{target}",
        "packageName": package["name"],
        "coreVersion": package["coreVersion"],
        "packageVersion": adapter["packageVersion"],
        "licenses": package["licenses"],
        "target": target,
        "format": adapter["format"],
        "adapterRevision": adapter["adapterRevision"],
        "build": derived_build(render_config, adapter),
        "source": {
            "kind": "canonical-tree",
            "inputTreeSha256": tree_digest(aggregate_input, "source.input"),
            "includedTreeSha256": tree_digest(aggregate_included, "source.selected"),
            "upstreamLocks": derived_upstream_locks(render_config),
            "skills": skill_manifests,
        },
        "payload": {
            "sha256": tree_digest(payload, "payload"),
            "files": payload,
        },
    }
    write_json(target_root / ARTIFACT_MANIFEST, artifact_manifest)
    verify_artifact(repo_root, target_root, target, render_config, adapter_config)
    return artifact_manifest


def render_all(
    repo_root: Path,
    output_root: Path,
    render_config: Dict[str, Any],
    adapter_config: Dict[str, Any],
) -> Dict[str, Dict[str, Any]]:
    repo_root = repo_root.resolve()
    requested_root = Path(os.path.abspath(output_root))
    if os.path.lexists(requested_root):
        raise RenderError("output.exists", f"output path already exists: {requested_root}")
    requested_root.parent.mkdir(parents=True, exist_ok=True)
    output_root = requested_root.parent.resolve() / requested_root.name
    if os.path.lexists(output_root):
        raise RenderError(f"output path already exists: {output_root}")
    source_skills = resolve_source_skills_root(repo_root, render_config)
    for skill_name in render_config["selectedSkills"]:
        source_dir = (source_skills / skill_name).resolve()
        if output_root == source_dir or source_dir in output_root.parents:
            raise RenderError(
                f"output path must not overlap selected skill source {skill_name!r}: "
                f"{output_root}"
            )
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
            "schemaVersion": 2,
            "coreVersion": render_config["package"]["coreVersion"],
            "targets": {
                target: {
                    "artifactId": results[target]["artifactId"],
                    "packageVersion": results[target]["packageVersion"],
                    "adapterRevision": results[target]["adapterRevision"],
                    "artifactSha256": tree_digest(
                        complete_artifact_records(temp_root / target), "artifact"
                    ),
                    "payloadSha256": results[target]["payload"]["sha256"],
                }
                for target in sorted(results)
            },
        }
        write_json(temp_root / RENDER_INDEX, render_index)
        normalize_physical_tree(temp_root)
        verify_render_root(repo_root, temp_root, render_config, adapter_config)
        if os.path.lexists(output_root):
            raise RenderError(
                "output.raced",
                f"output path appeared before publication: {output_root}",
            )
        temp_root.rename(output_root)
    except Exception:
        shutil.rmtree(temp_root, ignore_errors=True)
        raise
    return results


def verify_artifact(
    repo_root: Path,
    artifact_root: Path,
    expected_target: str,
    render_config: Dict[str, Any],
    adapter_config: Dict[str, Any],
) -> Dict[str, Any]:
    """Answer whether this tree was produced by this renderer from these inputs.

    Three distinct questions are settled here, and a manifest must pass all of them:
    schema conformance against the committed contract, internal consistency between the
    recorded inventory and the bytes on disk, and identity against the render config,
    adapter entry, renderer digest, and current source tree. The third is why a manifest
    field cannot be edited after rendering: every immutable build fact is recomputed, not
    shape-checked. Host authority and promotion are deliberately absent from this artifact.

    Binding to the live source means an artifact rendered from an older tree fails once
    the source moves. That verdict is correct -- the artifact is stale -- and is the
    property that makes `inputTreeSha256` mean anything.
    """
    artifact_root = artifact_root.resolve()
    manifest_path = artifact_root / ARTIFACT_MANIFEST
    manifest = read_json_object(manifest_path, "artifact manifest")
    if manifest_path.read_bytes() != json_bytes(manifest):
        raise RenderError(
            "json.noncanonical",
            f"artifact manifest is not canonical renderer JSON: {manifest_path}",
        )
    conform_to_schema(
        manifest, load_schema(ARTIFACT_SCHEMA_FILE), "artifact manifest"
    )
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
        },
        "artifact manifest",
    )
    if manifest["$schema"] != ARTIFACT_SCHEMA or manifest["schemaVersion"] != 2:
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

    # --- identity against the declared inputs -------------------------------------
    package = render_config["package"]
    adapter = adapter_config["targets"].get(expected_target)
    if not isinstance(adapter, dict):
        raise RenderError(f"adapter config has no object for target {expected_target!r}")
    for field, expected in (
        ("packageName", package["name"]),
        ("coreVersion", package["coreVersion"]),
        ("licenses", package["licenses"]),
        ("packageVersion", adapter["packageVersion"]),
        ("format", adapter["format"]),
        ("adapterRevision", adapter["adapterRevision"]),
    ):
        if manifest[field] != expected:
            raise RenderError(
                f"artifact {field} does not match the render inputs: "
                f"artifact={manifest[field]!r} configured={expected!r}"
            )
    expected_build = derived_build(render_config, adapter)
    if manifest["build"] != expected_build:
        drifted = sorted(
            key for key in expected_build
            if not isinstance(manifest["build"], dict)
            or manifest["build"].get(key) != expected_build[key]
        )
        raise RenderError(
            f"artifact build record was not produced by this renderer and configuration: "
            f"{drifted}"
        )
    build = manifest["build"]
    renderer_version = build["rendererVersion"]
    if SEMVER.fullmatch(renderer_version) is None:
        raise RenderError("artifact build rendererVersion must be strict semantic versioning")
    for digest_field in (
        "rendererSha256",
        "contractsSha256",
        "renderConfigSha256",
        "adapterConfigSha256",
    ):
        if not is_sha256(build[digest_field]):
            raise RenderError(f"artifact build {digest_field} must be a sha256 value")
    assert_isolated_manifest(artifact_root, expected_target)
    verify_target_manifest(artifact_root, expected_target, manifest)
    if expected_target == "agent-plugins":
        conform_to_schema(
            read_json_object(artifact_root / "plugin.json", "portable manifest"),
            load_schema(AGENT_PLUGIN_SCHEMA_FILE),
            "agent-plugins plugin.json",
        )
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
    # No configuration declares an upstream, so the renderer has nothing to derive a lock
    # from and every recorded lock would be an unbacked provenance and license claim. When
    # upstreams become declarable this compares against the declared set instead of empty.
    if source["upstreamLocks"] != derived_upstream_locks(render_config):
        raise RenderError(
            "artifact records upstream locks no render input declares: "
            "an upstream provenance or license claim cannot originate in the artifact"
        )
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
    if not is_sha256(payload["sha256"]) or payload["sha256"] != tree_digest(
        actual_files, "payload"
    ):
        raise RenderError(f"artifact aggregate payload digest mismatch: {artifact_root}")

    # --- source provenance against the tree that is claimed to have produced it ----
    scan = scan_selected_skills(repo_root, render_config)
    if actual_files != expected_payload_records(scan, expected_target):
        raise RenderError(
            "artifact.payload_projection",
            "artifact payload does not equal the independently inventoried source projection",
        )
    if source["inputTreeSha256"] != tree_digest(scan.aggregate_input, "source.input"):
        raise RenderError(
            "artifact source inputTreeSha256 does not match the current source tree: "
            "the artifact is stale, or its recorded provenance was edited"
        )
    recorded_by_id = {entry["id"]: entry for entry in skills}
    scanned_by_id = {entry["id"]: entry for entry in scan.skills}
    if sorted(recorded_by_id) != sorted(scanned_by_id):
        raise RenderError(
            f"artifact skill selection does not match the render config: "
            f"artifact={sorted(recorded_by_id)} configured={sorted(scanned_by_id)}"
        )
    for skill_id, scanned in sorted(scanned_by_id.items()):
        if recorded_by_id[skill_id] != scanned:
            raise RenderError(
                f"artifact skill {skill_id} provenance does not match the source tree: "
                f"input digest, included digest, file count, or excluded-path record differs"
            )

    if source["includedTreeSha256"] != tree_digest(
        scan.aggregate_included, "source.selected"
    ):
        raise RenderError("artifact selected source digest does not match the current source tree")
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
        rendered = skill_root / skill / "SKILL.md"
        parse_skill_frontmatter(rendered, skill)
        if rendered.read_bytes() != projected_skill_bytes(
            scan.source_root / skill / "SKILL.md", skill, expected_target
        ):
            raise RenderError(
                "skill.projection_mismatch",
                f"rendered {skill} frontmatter/body is not the target projection",
            )
    return manifest


def verify_render_root(
    repo_root: Path,
    output_root: Path,
    render_config: Dict[str, Any],
    adapter_config: Dict[str, Any],
) -> Dict[str, Dict[str, Any]]:
    if not output_root.is_dir():
        raise RenderError(f"rendered output directory is absent: {output_root}")
    inspect_physical_tree(output_root, normalized=True)
    expected = sorted(render_config["targets"])
    actual = sorted(path.name for path in output_root.iterdir() if path.is_dir())
    root_files = sorted(path.name for path in output_root.iterdir() if not path.is_dir())
    if actual != expected or root_files != [RENDER_INDEX]:
        raise RenderError(
            f"render root inventory mismatch: targets={actual} root_files={root_files} "
            f"expected={expected}"
        )
    index = read_json_object(output_root / RENDER_INDEX, "render index")
    if (output_root / RENDER_INDEX).read_bytes() != json_bytes(index):
        raise RenderError(
            "json.noncanonical",
            f"render index is not canonical renderer JSON: {output_root / RENDER_INDEX}",
        )
    conform_to_schema(index, load_schema(RENDER_INDEX_SCHEMA_FILE), "render index")
    require_exact_keys(
        index, {"$schema", "schemaVersion", "coreVersion", "targets"}, "render index"
    )
    if index["$schema"] != RENDER_INDEX_SCHEMA or index["schemaVersion"] != 2:
        raise RenderError("render index schema identity is invalid")
    if index["coreVersion"] != render_config["package"]["coreVersion"]:
        raise RenderError("render index coreVersion does not match render config")
    indexed_targets = index["targets"]
    if not isinstance(indexed_targets, dict) or sorted(indexed_targets) != expected:
        raise RenderError("render index target inventory does not match render config")
    manifests: Dict[str, Dict[str, Any]] = {}
    for target in expected:
        manifests[target] = verify_artifact(
            repo_root, output_root / target, target, render_config, adapter_config
        )
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
            "artifactSha256": tree_digest(
                complete_artifact_records(output_root / target), "artifact"
            ),
            "payloadSha256": manifests[target]["payload"]["sha256"],
        }
        if entry != expected_entry:
            raise RenderError(f"render index target {target} does not match artifact bytes")
    return manifests


def leaf_paths(node: Any, prefix: str = "") -> List[str]:
    """Every addressable leaf of a JSON document, empty containers included."""
    if isinstance(node, dict) and node:
        found: List[str] = []
        for key, member in sorted(node.items()):
            found += leaf_paths(member, f"{prefix}.{key}" if prefix else key)
        return found
    if isinstance(node, list) and node:
        found = []
        for index, member in enumerate(node):
            found += leaf_paths(member, f"{prefix}[{index}]")
        return found
    return [prefix]


def _walk_to(root: Any, path: str) -> Tuple[Any, Any]:
    tokens: List[Any] = []
    for part in path.split("."):
        while "[" in part:
            head, rest = part.split("[", 1)
            if head:
                tokens.append(head)
            index, part = rest.split("]", 1)
            tokens.append(int(index))
        if part:
            tokens.append(part)
    node = root
    for token in tokens[:-1]:
        node = node[token]
    return node, tokens[-1]


def read_path(root: Any, path: str) -> Any:
    node, last = _walk_to(root, path)
    return node[last]


def write_path(root: Any, path: str, value: Any) -> None:
    node, last = _walk_to(root, path)
    node[last] = value


def shape_preserving_variant(value: Any) -> Any:
    """A different value of the same JSON shape, so a binding is tested, not a type rule."""
    if isinstance(value, bool):
        return not value
    if isinstance(value, int):
        return value + 1
    if isinstance(value, str):
        if is_sha256(value):
            return "a" * 64
        return value + "-x"
    if isinstance(value, list):
        return ["injected"] if not value else value[:-1]
    if isinstance(value, dict):
        return {**value, "injected": 1}
    return "injected"


def load_inputs_from(
    render_config: Dict[str, Any],
    adapter_config: Dict[str, Any],
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Round-trip two in-memory configs through the real input validation."""
    with tempfile.TemporaryDirectory(prefix="z-harness-inputs-") as raw:
        temp = Path(raw)
        write_json(temp / "render.json", render_config)
        write_json(temp / "targets.json", adapter_config)
        return load_inputs(temp / "render.json", temp / "targets.json")


def snapshot_tree(root: Path) -> List[Tuple[str, str, int, bytes]]:
    snapshot: List[Tuple[str, str, int, bytes]] = []
    for path in [root] + sorted(root.rglob("*"), key=lambda item: item.as_posix()):
        info = path.lstat()
        relative = "." if path == root else path.relative_to(root).as_posix()
        if stat.S_ISDIR(info.st_mode):
            snapshot.append((relative, "d" + oct(stat.S_IMODE(info.st_mode)), info.st_mtime_ns, b""))
        elif stat.S_ISREG(info.st_mode):
            snapshot.append((relative, "f" + oct(stat.S_IMODE(info.st_mode)), info.st_mtime_ns, path.read_bytes()))
        else:
            snapshot.append((relative, "other", info.st_mtime_ns, b""))
    return snapshot


def selftest(
    render_path: Path = DEFAULT_RENDER_CONFIG,
    adapter_path: Path = DEFAULT_ADAPTER_CONFIG,
) -> int:
    checks = 0
    failures = 0

    def expect(label: str, predicate: bool) -> None:
        nonlocal checks, failures
        checks += 1
        print(f"  {'PASS' if predicate else 'FAIL'} {label}")
        if not predicate:
            failures += 1

    def expect_code(label: str, code: str, call: Any) -> None:
        nonlocal checks, failures
        checks += 1
        try:
            call()
        except RenderError as exc:
            if exc.code == code:
                print(f"  PASS {label}")
                return
            print(f"  FAIL {label}: code={exc.code!r} expected={code!r}")
            failures += 1
            return
        except Exception as exc:
            print(f"  FAIL {label}: wrong exception {exc!r}")
            failures += 1
            return
        print(f"  FAIL {label}: no error")
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

    render_config, adapter_config = load_inputs(render_path, adapter_path)
    with tempfile.TemporaryDirectory(prefix="z-harness-render-selftest-") as raw_temp:
        temp = Path(raw_temp)
        first = temp / "first"
        second = temp / "second"
        render_all(ROOT, first, render_config, adapter_config)
        render_all(ROOT, second, render_config, adapter_config)
        expect("same inputs produce identical physical trees", snapshot_tree(first) == snapshot_tree(second))
        expect("all file and directory mtimes are epoch", all(row[2] == 0 for row in snapshot_tree(first)))
        expect("all rendered directories are 0755", all(
            not row[1].startswith("d") or row[1] == "d0o755"
            for row in snapshot_tree(first)
        ))
        expect("all rendered files use canonical 0644/0755 modes", all(
            not row[1].startswith("f") or row[1] in {"f0o644", "f0o755"}
            for row in snapshot_tree(first)
        ))
        verified = verify_render_root(ROOT, first, render_config, adapter_config)
        expect(
            "all configured targets verify",
            sorted(verified) == sorted(render_config["targets"]),
        )
        expect(
            "runtime artifacts exclude authoring-only root files",
            all(not (first / target / "skills/ground-claims/CONTRACT.md").exists()
                for target in render_config["targets"])
            and (ROOT / "skills/ground-claims/CONTRACT.md").is_file(),
        )
        expect(
            "every excluded source file is recorded as provenance",
            all(
                "CONTRACT.md" in manifest["source"]["skills"][0]["excludedPaths"]
                for manifest in verified.values()
            ),
        )
        expect(
            "pilot target inventory is pinned to all five supported package surfaces",
            set(render_config["targets"])
            == {"agent-plugins", "codex", "claude", "kimi", "hermes"},
        )
        wrong_format = json.loads(json.dumps(adapter_config))
        wrong_format["targets"]["claude"]["format"] = "agent-plugins/1.0.0"
        expect_code(
            "input validation rejects a target format substituted across adapters",
            "adapter.format",
            lambda: load_inputs_from(render_config, wrong_format),
        )
        extra_adapter = json.loads(json.dumps(adapter_config))
        extra_adapter["targets"]["ghost"] = json.loads(
            json.dumps(extra_adapter["targets"]["claude"])
        )
        expect_code(
            "input validation rejects an undeclared extra adapter target",
            "adapter.target_inventory",
            lambda: load_inputs_from(render_config, extra_adapter),
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
        forbidden_fact_keys = {
            "claims", "authority", "targetLevel", "earnedLevel", "validationStatus",
            "evidence", "installedArtifactSha256",
        }
        expect("artifact manifests contain no host authority or promotion fields", all(
            not forbidden_fact_keys.intersection(json.dumps(manifest).split('"'))
            for manifest in verified.values()
        ))
        expect(
            "every artifact records the exact renderer and canonical config inputs",
            all(
                manifest["build"] == derived_build(
                    render_config, adapter_config["targets"][target]
                )
                for target, manifest in verified.items()
            ),
        )
        expect(
            "emitted artifacts satisfy the committed artifact-manifest contract",
            all(
                conform_to_schema(
                    manifest, load_schema(ARTIFACT_SCHEMA_FILE), f"{target} manifest"
                ) is None
                for target, manifest in verified.items()
            ),
        )
        expect(
            "the portable manifest satisfies the vendored Agent Plugins 1.0.0 schema",
            conform_to_schema(
                read_json_object(first / "agent-plugins/plugin.json", "portable manifest"),
                load_schema(AGENT_PLUGIN_SCHEMA_FILE),
                "agent-plugins plugin.json",
            ) is None,
        )
        vendor_sources = load_vendor_sources()
        expect(
            "vendored schema provenance has one internally consistent pinned source",
            [entry["file"] for entry in vendor_sources]
            == [AGENT_PLUGIN_SCHEMA_FILE.name],
        )
        vendor_fixture = temp / "vendor-provenance"
        vendor_fixture.mkdir(parents=True)
        shutil.copy2(AGENT_PLUGIN_SCHEMA_FILE, vendor_fixture / AGENT_PLUGIN_SCHEMA_FILE.name)
        contradictory_sources = read_json_object(
            VENDOR_SOURCES_FILE, "vendored source fixture"
        )
        contradictory_sources["sources"][0]["revision"] = (
            "a" + contradictory_sources["sources"][0]["revision"][1:]
        )
        write_json(vendor_fixture / "SOURCES.json", contradictory_sources)
        expect_code(
            "vendored source provenance rejects a revision and raw-URL contradiction",
            "vendor.source_url",
            lambda: load_vendor_sources(vendor_fixture / "SOURCES.json"),
        )
        invalid_date_sources = read_json_object(
            VENDOR_SOURCES_FILE, "vendored source invalid-date fixture"
        )
        invalid_date_sources["sources"][0]["retrieved"] = "2026-99-99"
        write_json(vendor_fixture / "invalid-date-SOURCES.json", invalid_date_sources)
        expect_code(
            "vendored source provenance rejects an impossible calendar date",
            "vendor.source_identity",
            lambda: load_vendor_sources(
                vendor_fixture / "invalid-date-SOURCES.json"
            ),
        )
        index = read_json_object(first / RENDER_INDEX, "render index")
        expect(
            "render index binds each complete artifact including its manifest",
            all(
                index["targets"][target]["artifactSha256"]
                == tree_digest(complete_artifact_records(first / target), "artifact")
                for target in render_config["targets"]
            ),
        )
        expect_code(
            "renderer refuses to overwrite an existing output root",
            "output.exists",
            lambda: render_all(ROOT, second, render_config, adapter_config),
        )

        broken_output = temp / "broken-output"
        broken_output.symlink_to(temp / "absent-target", target_is_directory=True)
        expect_code(
            "lexists rejects a broken output symlink",
            "output.exists",
            lambda: render_all(ROOT, broken_output, render_config, adapter_config),
        )

        projection = read_json_object(PROJECTION_GOLDEN, "projection golden")
        canonical = parse_skill_document(ROOT / "skills/ground-claims/SKILL.md", "ground-claims")
        expect("projection golden binds canonical body bytes", sha256_bytes(canonical.body) == projection["canonicalBodySha256"])
        for target in render_config["targets"]:
            rendered_skill = first / target / "skills/ground-claims/SKILL.md"
            raw = rendered_skill.read_bytes()
            closing = raw.find(b"\n---\n", 4)
            frontmatter = raw[:closing + 5].decode("utf-8")
            expected_frontmatter = projection[
                "claudeFrontmatter" if target == "claude" else "portableFrontmatter"
            ]
            expect(f"{target} frontmatter equals its byte golden", frontmatter == expected_frontmatter)
            expect(f"{target} body is byte-identical to canonical", raw[closing + 5:] == canonical.body)
            expect(f"{target} omits allowed-tools", b"allowed-tools:" not in raw[:closing + 5])
        expect("only Claude retains argument-hint", all(
            ((b"argument-hint:" in (first / target / "skills/ground-claims/SKILL.md").read_bytes()) == (target == "claude"))
            for target in render_config["targets"]
        ))
        reference_bytes = {
            (first / target / "skills/ground-claims/references/evidence-method.md").read_bytes()
            for target in render_config["targets"]
        }
        expect("included references are byte-identical across targets", len(reference_bytes) == 1)
        native_goldens = golden_native_manifests()
        for target, path in EXPECTED_MANIFEST_PATHS.items():
            if path is None:
                expect("Hermes has an explicit no-native-manifest golden", native_goldens[target] is None)
            else:
                expect(f"{target} native manifest bytes equal the hand-authored golden", (first / target / path).read_bytes() == json_bytes(native_goldens[target]))

        digest_goldens = read_json_object(DIGEST_GOLDEN, "digest golden")
        expect("canonical JSON digest equals independent fixed golden", canonical_json_digest(
            digest_goldens["canonicalJson"]["value"], digest_goldens["canonicalJson"]["domain"]
        ) == digest_goldens["canonicalJson"]["expected"])
        expect("tree digest equals independent fixed golden", tree_digest(
            digest_goldens["tree"]["records"], digest_goldens["tree"]["domain"]
        ) == digest_goldens["tree"]["expected"])
        expect("digest domains cannot be re-aimed", tree_digest(
            digest_goldens["tree"]["records"], "golden.tree.other"
        ) != digest_goldens["tree"]["expected"])

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
        skill_body = fixture_root / "skills/ground-claims/SKILL.md"
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
            "an excluded source mutation moves the input digest and leaves the payload fixed",
            before_manifest["source"]["inputTreeSha256"]
            != after_manifest["source"]["inputTreeSha256"]
            and before_manifest["payload"]["sha256"]
            == after_manifest["payload"]["sha256"],
        )
        included_mutation = temp / "included-mutation"
        original_body = skill_body.read_text(encoding="utf-8")
        skill_body.write_text(original_body + "\nmutation\n", encoding="utf-8")
        included_manifest = render_all(
            fixture_root, included_mutation, render_config, adapter_config
        )["codex"]
        expect(
            "an included source mutation moves both the input and payload digests",
            included_manifest["source"]["inputTreeSha256"]
            != after_manifest["source"]["inputTreeSha256"]
            and included_manifest["payload"]["sha256"]
            != after_manifest["payload"]["sha256"],
        )
        skill_body.write_text(original_body, encoding="utf-8")
        contract.write_text(
            contract.read_text(encoding="utf-8").replace("\nmutation\n", ""), encoding="utf-8"
        )

        tamper_base = temp / "tamper-base"
        render_all(fixture_root, tamper_base, render_config, adapter_config)
        case_index = 0

        def planted(label: str, target: str, mutate: Any, code: Optional[str] = None) -> None:
            nonlocal case_index
            case_index += 1
            case_root = temp / f"tamper-{case_index:02d}"
            shutil.copytree(tamper_base / target, case_root)
            mutate(case_root)
            call = lambda: verify_artifact(  # noqa: E731
                fixture_root, case_root, target, render_config, adapter_config
            )
            if code:
                expect_code(label, code, call)
            else:
                expect_error(label, call)

        def edit_manifest(change: Any) -> Any:
            def apply(root: Path) -> None:
                path = root / ARTIFACT_MANIFEST
                manifest = read_json_object(path, "artifact manifest")
                change(manifest)
                write_json(path, manifest)
            return apply

        def touch_payload(root: Path) -> None:
            target_file = root / "skills/ground-claims/SKILL.md"
            target_file.write_text(
                target_file.read_text(encoding="utf-8") + "tampered\n", encoding="utf-8"
            )

        planted("verification rejects a post-render payload mutation", "claude", touch_payload)
        planted(
            "verification rejects a post-render payload mode change",
            "claude",
            lambda root: (root / "skills/ground-claims/SKILL.md").chmod(0o755),
        )
        planted(
            "verification rejects a file smuggled into the payload",
            "claude",
            lambda root: write_bytes(root / "skills/ground-claims/EXTRA.md", b"smuggled\n"),
        )
        planted(
            "kimi verification rejects competing native manifest locations",
            "kimi",
            lambda root: write_json(root / ".kimi-plugin/plugin.json", {"name": "shadow"}),
            "render.invalid",
        )
        planted(
            "hermes tap verification rejects executable plugin conversion",
            "hermes",
            lambda root: write_bytes(root / "plugin.yaml", b"name: executable-shadow\n"),
            "render.invalid",
        )
        for field in ("rendererSha256", "contractsSha256", "renderConfigSha256", "adapterConfigSha256"):
            planted(
                f"verification rejects a substituted build.{field}",
                "codex",
                edit_manifest(lambda m, f=field: m["build"].__setitem__(f, "a" * 64)),
            )
        planted(
            "verification rejects a substituted build.rendererVersion",
            "codex",
            edit_manifest(lambda m: m["build"].__setitem__("rendererVersion", "9.9.9")),
        )
        for field, value in (
            ("coreVersion", "9.9.9"),
            ("packageVersion", "9.9.9"),
            ("adapterRevision", 7),
            ("format", "bogus/format"),
            ("licenses", ["MIT"]),
        ):
            planted(
                f"verification rejects a manifest {field} the configuration did not authorise",
                "codex",
                edit_manifest(lambda m, f=field, v=value: m.__setitem__(f, v)),
            )
        planted(
            "verification binds included-source provenance to payload bytes",
            "codex",
            edit_manifest(
                lambda m: m["source"]["skills"][0].__setitem__("includedTreeSha256", "0" * 64)
            ),
        )
        planted(
            "verification binds recorded input provenance to the source tree",
            "codex",
            edit_manifest(
                lambda m: m["source"].__setitem__("inputTreeSha256", "0" * 64)
            ),
        )
        planted(
            "verification rejects an emptied excluded-path record",
            "codex",
            edit_manifest(
                lambda m: m["source"]["skills"][0].__setitem__("excludedPaths", [])
            ),
        )

        base_manifest = read_json_object(
            tamper_base / f"claude/{ARTIFACT_MANIFEST}", "sweep manifest"
        )
        manifest_paths = leaf_paths(base_manifest)
        survivors: List[str] = []
        for position, path in enumerate(manifest_paths):
            case_root = temp / f"sweep-manifest-{position:03d}"
            shutil.copytree(tamper_base / "claude", case_root)
            mutated = json.loads(json.dumps(base_manifest))
            write_path(mutated, path, shape_preserving_variant(read_path(mutated, path)))
            write_json(case_root / ARTIFACT_MANIFEST, mutated)
            try:
                verify_artifact(
                    fixture_root, case_root, "claude", render_config, adapter_config
                )
                survivors.append(path)
            except RenderError:
                continue
            except Exception as exc:  # noqa: BLE001
                survivors.append(f"{path} (crashed: {type(exc).__name__})")
        expect(
            f"no artifact-manifest leaf survives mutation ({len(manifest_paths)} swept)"
            + (f" -- survived: {survivors}" if survivors else ""),
            bool(manifest_paths) and not survivors,
        )

        base_index = read_json_object(tamper_base / RENDER_INDEX, "sweep render index")
        index_paths = leaf_paths(base_index)
        index_survivors: List[str] = []
        for position, path in enumerate(index_paths):
            case_root = temp / f"sweep-index-{position:03d}"
            shutil.copytree(tamper_base, case_root)
            mutated = json.loads(json.dumps(base_index))
            write_path(mutated, path, shape_preserving_variant(read_path(mutated, path)))
            write_json(case_root / RENDER_INDEX, mutated)
            try:
                verify_render_root(fixture_root, case_root, render_config, adapter_config)
                index_survivors.append(path)
            except RenderError:
                continue
            except Exception as exc:  # noqa: BLE001
                index_survivors.append(f"{path} (crashed: {type(exc).__name__})")
        expect(
            f"no render-index leaf survives mutation ({len(index_paths)} swept)"
            + (f" -- survived: {index_survivors}" if index_survivors else ""),
            bool(index_paths) and not index_survivors,
        )

        planted(
            "verification rejects a well-formed but undeclared upstream lock",
            "codex",
            edit_manifest(lambda m: m["source"]["upstreamLocks"].append({
                "id": "some-vendor/pack",
                "revision": "v2.1.0",
                "sha256": "b" * 64,
                "licenses": ["Apache-2.0"],
            })),
        )
        planted(
            "verification rejects a well-formed but absent extra skill record",
            "codex",
            edit_manifest(lambda m: m["source"]["skills"].append({
                "id": "ghost",
                "inputTreeSha256": "c" * 64,
                "includedTreeSha256": "d" * 64,
                "includedFiles": 1,
                "excludedPaths": [],
            })),
        )

        planted(
            "verification rejects a well-formed authority claim injected into immutable facts",
            "codex",
            edit_manifest(lambda m: m.__setitem__("authority", "instruction-only")),
        )

        index_injection = temp / "index-injection"
        shutil.copytree(tamper_base, index_injection)
        injected_index = read_json_object(index_injection / RENDER_INDEX, "injected index")
        injected_index["targets"]["ghost"] = json.loads(json.dumps(next(iter(injected_index["targets"].values()))))
        write_json(index_injection / RENDER_INDEX, injected_index)
        normalize_physical_tree(index_injection)
        expect_error("verification rejects a well-formed extra index target", lambda: verify_render_root(
            fixture_root, index_injection, render_config, adapter_config
        ))

        duplicate_index = temp / "duplicate-index-key"
        shutil.copytree(tamper_base, duplicate_index)
        duplicate_index_path = duplicate_index / RENDER_INDEX
        duplicate_index_path.write_bytes(
            duplicate_index_path.read_bytes().replace(
                b'  "schemaVersion": 2,\n',
                b'  "schemaVersion": 999,\n  "schemaVersion": 2,\n',
                1,
            )
        )
        normalize_physical_tree(duplicate_index)
        expect_code(
            "public verification rejects a duplicate top-level JSON key",
            "json.duplicate_key",
            lambda: verify_render_root(
                fixture_root, duplicate_index, render_config, adapter_config
            ),
        )

        duplicate_nested = temp / "duplicate-nested-key"
        shutil.copytree(tamper_base, duplicate_nested)
        duplicate_manifest_path = duplicate_nested / f"codex/{ARTIFACT_MANIFEST}"
        duplicate_manifest_path.write_bytes(
            duplicate_manifest_path.read_bytes().replace(
                b'    "renderer": "z-harness/render-packages",\n',
                b'    "renderer": "shadow/renderer",\n'
                b'    "renderer": "z-harness/render-packages",\n',
                1,
            )
        )
        normalize_physical_tree(duplicate_nested)
        expect_code(
            "public verification rejects a duplicate nested JSON key",
            "json.duplicate_key",
            lambda: verify_render_root(
                fixture_root, duplicate_nested, render_config, adapter_config
            ),
        )
        nonfinite_json = temp / "nonfinite.json"
        nonfinite_json.write_text('{"value": NaN}\n', encoding="utf-8")
        expect_code(
            "JSON reader rejects non-finite numeric constants",
            "json.nonfinite",
            lambda: read_json_object(nonfinite_json, "non-finite fixture"),
        )
        try:
            json_bytes({"value": float("nan")})
            nonfinite_writer_rejected = False
        except ValueError:
            nonfinite_writer_rejected = True
        expect(
            "canonical JSON writer rejects non-finite numeric values",
            nonfinite_writer_rejected,
        )

        noncanonical_index = temp / "noncanonical-index"
        shutil.copytree(tamper_base, noncanonical_index)
        noncanonical_index_path = noncanonical_index / RENDER_INDEX
        noncanonical_index_path.write_bytes(noncanonical_index_path.read_bytes() + b"\n")
        normalize_physical_tree(noncanonical_index)
        expect_code(
            "public verification rejects semantically equal noncanonical index bytes",
            "json.noncanonical",
            lambda: verify_render_root(
                fixture_root, noncanonical_index, render_config, adapter_config
            ),
        )

        noncanonical_artifact = temp / "noncanonical-artifact"
        shutil.copytree(tamper_base, noncanonical_artifact)
        noncanonical_artifact_path = noncanonical_artifact / f"codex/{ARTIFACT_MANIFEST}"
        noncanonical_artifact_path.write_bytes(
            noncanonical_artifact_path.read_bytes() + b"\n"
        )
        rethreaded_index = read_json_object(
            noncanonical_artifact / RENDER_INDEX, "rethreaded index"
        )
        rethreaded_index["targets"]["codex"]["artifactSha256"] = tree_digest(
            complete_artifact_records(noncanonical_artifact / "codex"), "artifact"
        )
        write_json(noncanonical_artifact / RENDER_INDEX, rethreaded_index)
        normalize_physical_tree(noncanonical_artifact)
        expect_code(
            "public verification rejects a rethreaded noncanonical artifact manifest",
            "json.noncanonical",
            lambda: verify_render_root(
                fixture_root, noncanonical_artifact, render_config, adapter_config
            ),
        )

        rethreaded_payload = temp / "rethreaded-payload"
        shutil.copytree(tamper_base, rethreaded_payload)
        rethreaded_reference = (
            rethreaded_payload
            / "codex/skills/ground-claims/references/evidence-method.md"
        )
        rethreaded_reference.write_bytes(
            rethreaded_reference.read_bytes() + b"\ncoherently rethreaded tamper\n"
        )
        rethreaded_manifest_path = rethreaded_payload / f"codex/{ARTIFACT_MANIFEST}"
        rethreaded_manifest = read_json_object(
            rethreaded_manifest_path, "rethreaded artifact manifest"
        )
        rethreaded_records = payload_records(rethreaded_payload / "codex")
        rethreaded_manifest["payload"] = {
            "sha256": tree_digest(rethreaded_records, "payload"),
            "files": rethreaded_records,
        }
        write_json(rethreaded_manifest_path, rethreaded_manifest)
        rethreaded_payload_index = read_json_object(
            rethreaded_payload / RENDER_INDEX, "rethreaded payload index"
        )
        rethreaded_payload_index["targets"]["codex"]["payloadSha256"] = (
            rethreaded_manifest["payload"]["sha256"]
        )
        rethreaded_payload_index["targets"]["codex"]["artifactSha256"] = tree_digest(
            complete_artifact_records(rethreaded_payload / "codex"), "artifact"
        )
        write_json(rethreaded_payload / RENDER_INDEX, rethreaded_payload_index)
        normalize_physical_tree(rethreaded_payload)
        expect_code(
            "public verification rejects coherently rethreaded projected support-file bytes",
            "artifact.payload_projection",
            lambda: verify_render_root(
                fixture_root, rethreaded_payload, render_config, adapter_config
            ),
        )

        physical_cases: List[Tuple[str, str, Any]] = [
            ("empty directory", "tree.empty_directory", lambda root: (root / "codex/EMPTY").mkdir()),
            ("symlink", "tree.symlink", lambda root: (root / "codex/link").symlink_to("skills")),
            ("hardlink", "tree.hardlink", lambda root: os.link(root / "codex/skills/ground-claims/SKILL.md", root / "codex/HARDLINK")),
            ("file mode drift", "tree.file_profile", lambda root: (root / "codex/skills/ground-claims/SKILL.md").chmod(0o600)),
            ("directory mode drift", "tree.directory_profile", lambda root: (root / "codex/skills").chmod(0o700)),
            ("file mtime drift", "tree.file_profile", lambda root: os.utime(root / "codex/skills/ground-claims/SKILL.md", ns=(1, 1))),
            ("directory mtime drift", "tree.directory_profile", lambda root: os.utime(root / "codex/skills", ns=(1, 1))),
        ]
        for position, (label, code, mutate) in enumerate(physical_cases):
            case_root = temp / f"physical-{position:02d}"
            shutil.copytree(tamper_base, case_root)
            mutate(case_root)
            expect_code(f"physical verification rejects {label}", code, lambda root=case_root: verify_render_root(
                fixture_root, root, render_config, adapter_config
            ))

        fifo_root = temp / "physical-fifo"
        shutil.copytree(tamper_base, fifo_root)
        os.mkfifo(fifo_root / "codex/FIFO")
        expect_code("physical verification rejects a FIFO", "tree.non_regular", lambda: verify_render_root(
            fixture_root, fifo_root, render_config, adapter_config
        ))
        expect_code(
            "portable path preflight rejects a casefold alias even on a case-insensitive host",
            "tree.path_alias",
            lambda: verify_path_aliases(["README", "readme"]),
        )
        expect_code(
            "portable path preflight rejects a standalone non-NFC path",
            "tree.path_nonportable",
            lambda: portable_path_key("re\u0301ference.md"),
        )
        for forbidden_character in '<>"|?*':
            expect_code(
                f"portable path preflight rejects Windows-forbidden {forbidden_character!r}",
                "tree.path_nonportable",
                lambda character=forbidden_character: portable_path_key(
                    f"references/bad{character}.md"
                ),
            )
        for reserved_name in ("COM\u00b9.txt", "LPT\u00b2.doc", "CONIN$", "AUX  .txt"):
            expect_code(
                f"portable path preflight rejects Windows device alias {reserved_name!r}",
                "tree.path_nonportable",
                lambda name=reserved_name: portable_path_key(
                    f"references/{name}"
                ),
            )
        forbidden_source = fixture_root / "skills/ground-claims/references/bad?.md"
        def render_forbidden_source() -> None:
            forbidden_source.write_text("forbidden path fixture\n", encoding="utf-8")
            try:
                render_all(
                    fixture_root,
                    temp / "forbidden-path-render",
                    render_config,
                    adapter_config,
                )
            finally:
                forbidden_source.unlink(missing_ok=True)
        expect_code(
            "production render rejects a Windows-forbidden included source path",
            "tree.path_nonportable",
            render_forbidden_source,
        )
        reserved_source = fixture_root / "skills/ground-claims/references/AUX  .txt"
        def render_reserved_source() -> None:
            reserved_source.write_text("reserved path fixture\n", encoding="utf-8")
            try:
                render_all(
                    fixture_root,
                    temp / "reserved-path-render",
                    render_config,
                    adapter_config,
                )
            finally:
                reserved_source.unlink(missing_ok=True)
        expect_code(
            "production render rejects an extended Windows device alias",
            "tree.path_nonportable",
            render_reserved_source,
        )
        nfd_root = temp / "physical-nfd"
        shutil.copytree(tamper_base, nfd_root)
        nfd_file = nfd_root / "codex/re\u0301ference.md"
        write_bytes(nfd_file, b"non-NFC\n")
        os.utime(nfd_file.parent, ns=(0, 0))
        expect_code(
            "public physical verification rejects a standalone non-NFC filename",
            "tree.path_nonportable",
            lambda: verify_render_root(
                fixture_root, nfd_root, render_config, adapter_config
            ),
        )
        original_alias_verifier = globals()["verify_path_aliases"]
        def planted_alias_verifier(_paths: Sequence[str]) -> None:
            raise RenderError(
                "selftest.path_alias_callsite",
                "planted physical-scanner alias verifier",
            )
        globals()["verify_path_aliases"] = planted_alias_verifier
        try:
            expect_code(
                "physical scanner invokes the path-alias verifier call site",
                "selftest.path_alias_callsite",
                lambda: inspect_physical_tree(tamper_base, normalized=True),
            )
        finally:
            globals()["verify_path_aliases"] = original_alias_verifier
        planted(
            "verification rejects a well-formed but absent extra payload record",
            "codex",
            edit_manifest(lambda m: m["payload"]["files"].append({
                "path": "skills/ground-claims/GHOST.md",
                "mode": "0644",
                "size": 0,
                "sha256": "e" * 64,
            })),
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

        # The frontmatter reader has no YAML parser, so every form it cannot decode fails.
        for leader, shape in ((">-", "folded block"), ("|", "literal block"), ("&a", "anchor")):
            skill_manifest.write_text(
                original_skill.replace(
                    "description: Ground", f"description: {leader}\n  Ground", 1
                ),
                encoding="utf-8",
            )
            expect_error(
                f"renderer refuses a {shape} scalar instead of mis-decoding it",
                lambda: render_all(
                    fixture_root, temp / f"yaml-{shape.split()[0]}", render_config, adapter_config
                ),
            )
        skill_manifest.write_text(original_skill, encoding="utf-8")

        for position, (code, construct) in enumerate((
            ("skill.body.arguments", "$ARGUMENTS"),
            ("skill.body.claude_variable", "${CLAUDE_SKILL_DIR}"),
            ("skill.body.claude_variable", "${CLAUDE_SESSION_ID}"),
            ("skill.body.claude_variable", "${CLAUDE_PLUGIN_ROOT}"),
            ("skill.body.claude_variable", "${CLAUDE_EFFORT}"),
            ("skill.body.dynamic_command", "!`date`"),
            ("skill.body.dynamic_command", "- PR diff: !`gh pr diff`"),
            ("skill.body.frontmatter_directive", "model: sonnet"),
            ("skill.body.ultrathink", "ultrathink"),
        )):
            isolated = temp / f"host-body-{position}"
            shutil.copytree(ROOT / "skills/ground-claims", isolated / "skills/ground-claims")
            path = isolated / "skills/ground-claims/SKILL.md"
            path.write_text(path.read_text(encoding="utf-8") + f"\n{construct}\n", encoding="utf-8")
            expect_code(f"projection refuses host body construct {construct}", code, lambda path=path: parse_skill_document(path, "ground-claims"))

        near_miss_host_body = temp / "host-body-near-miss.md"
        near_miss_host_body.write_text(
            original_skill + "\n$CLAUDEX_PLUGIN_ROOT\n", encoding="utf-8"
        )
        try:
            parse_skill_document(near_miss_host_body, "ground-claims")
            near_miss_ok = True
        except RenderError:
            near_miss_ok = False
        expect("host-variable detector permits a non-Claude namespace near miss", near_miss_ok)

        image_near_miss = temp / "host-body-image-near-miss.md"
        image_near_miss.write_text(
            original_skill + "\n![portable image](assets/example.png)\n",
            encoding="utf-8",
        )
        try:
            parse_skill_document(image_near_miss, "ground-claims")
            image_near_miss_ok = True
        except RenderError:
            image_near_miss_ok = False
        expect("dynamic-command detector permits a portable Markdown image", image_near_miss_ok)

        expect_code(
            "frontmatter reader rejects a plain scalar YAML comment",
            "skill.frontmatter_ambiguous_plain_scalar",
            lambda: decode_scalar("visible # hidden comment", "probe"),
        )
        expect_code(
            "frontmatter reader rejects a plain scalar YAML implicit type",
            "skill.frontmatter_ambiguous_plain_scalar",
            lambda: decode_scalar("true", "probe"),
        )
        expect(
            "frontmatter reader preserves a quoted comment marker literally",
            decode_scalar('"visible # literal"', "probe") == "visible # literal",
        )
        yaml_leader_cases = ("- item", "? key", "@host", "`code`", "]", "}", ",")
        for value in yaml_leader_cases:
            expect_error(
                f"frontmatter reader rejects YAML indicator plain scalar {value!r}",
                lambda value=value: decode_scalar(value, "probe"),
            )
        expect(
            "frontmatter reader preserves YAML indicators when quoted",
            all(
                decode_scalar(json.dumps(value), "probe") == value
                for value in yaml_leader_cases
            ),
        )
        for value in ("'foo' junk'", "'foo'bar'"):
            expect_error(
                f"frontmatter reader rejects unpaired quote in {value!r}",
                lambda value=value: decode_scalar(value, "probe"),
            )
        expect(
            "frontmatter reader decodes paired YAML single quotes literally",
            decode_scalar("'it''s literal # text'", "probe")
            == "it's literal # text",
        )

        unknown_frontmatter = temp / "unknown-frontmatter.md"
        unknown_frontmatter.write_text(original_skill.replace("metadata:\n", "invented-host-key: yes\nmetadata:\n", 1), encoding="utf-8")
        expect_code("projection refuses an unknown target extension", "skill.frontmatter_unknown", lambda: parse_skill_document(unknown_frontmatter, "ground-claims"))

        expect_error(
            "the schema reader refuses a keyword it cannot evaluate",
            lambda: conform_to_schema(1, {"type": "integer", "multipleOf": 2}, "probe"),
        )
        # Every keyword the reader claims to support must reject a violating value. A
        # keyword listed as supported but never branched on would otherwise report a
        # clean result over an unchecked constraint -- which it did for `minimum`.
        violations = {
            "$ref": ({"$defs": {"n": {"type": "integer"}}, "$ref": "#/$defs/n"}, "no"),
            "type": ({"type": "integer"}, "no"),
            "const": ({"const": "a"}, "b"),
            "enum": ({"enum": ["a"]}, "b"),
            "required": ({"type": "object", "required": ["a"]}, {}),
            "properties": ({"type": "object", "properties": {"a": {"type": "integer"}}},
                           {"a": "no"}),
            "additionalProperties": ({"type": "object", "additionalProperties": False},
                                     {"a": 1}),
            "propertyNames": ({"type": "object", "propertyNames": {"maxLength": 1}},
                              {"ab": 1}),
            "minLength": ({"minLength": 2}, "a"),
            "maxLength": ({"maxLength": 1}, "ab"),
            "pattern": ({"pattern": "^a$"}, "b"),
            "items": ({"type": "array", "items": {"type": "integer"}}, ["no"]),
            "minItems": ({"type": "array", "minItems": 2}, [1]),
            "minProperties": ({"type": "object", "minProperties": 2}, {"a": 1}),
            "minimum": ({"type": "integer", "minimum": 2}, 1),
        }
        expect(
            "every constraint keyword the reader supports has a violation case",
            set(violations) == SCHEMA_CONSTRAINT_KEYWORDS,
        )
        for keyword, (schema_fragment, bad_value) in sorted(violations.items()):
            expect_error(
                f"schema keyword {keyword} rejects a violating value",
                lambda s=schema_fragment, v=bad_value: conform_to_schema(v, s, "probe"),
            )
        expect_error(
            "the schema reader enforces the vendored Agent Plugins name limit",
            lambda: conform_to_schema(
                {"$schema": AGENT_PLUGIN_SCHEMA, "name": "z-" + "a" * 70},
                load_schema(AGENT_PLUGIN_SCHEMA_FILE),
                "oversized plugin name",
            ),
        )

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

        domains: List[str] = []
        original_tree_digest = globals()["tree_digest"]
        def recording_tree_digest(records: Sequence[Dict[str, Any]], domain: str) -> str:
            domains.append(domain)
            return original_tree_digest(records, domain)
        globals()["tree_digest"] = recording_tree_digest
        try:
            render_all(ROOT, temp / "domain-callsite", render_config, adapter_config)
        finally:
            globals()["tree_digest"] = original_tree_digest
        required_domains = {"build.contracts", "source.input", "source.selected", "payload", "artifact"}
        expect("production call sites exercise every required digest domain", required_domains <= set(domains))

        original_verify_root = globals()["verify_render_root"]
        def planted_stage_verify(*_args: Any, **_kwargs: Any) -> Any:
            raise RenderError("selftest.staging_verify", "planted staging verifier")
        globals()["verify_render_root"] = planted_stage_verify
        staged_output = temp / "staging-callsite"
        try:
            expect_code("render_all invokes full staging-root verification before exposure", "selftest.staging_verify", lambda: render_all(
                ROOT, staged_output, render_config, adapter_config
            ))
        finally:
            globals()["verify_render_root"] = original_verify_root
        expect("failed staging verification exposes no output root", not os.path.lexists(staged_output))

    print(f"\n  selftest: {failures} failure(s)")
    print(f"SELFTEST-SUMMARY suite=render-packages checks={checks} failures={failures}")
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
    action = "selftest" if args.selftest else ("render" if args.output is not None else "verify")
    try:
        if args.selftest:
            return selftest(args.config, args.adapters)
        render_config, adapter_config = load_inputs(args.config, args.adapters)
        if args.output is not None:
            results = render_all(ROOT, args.output, render_config, adapter_config)
            index = read_json_object(args.output / RENDER_INDEX, "render index")
            for target in sorted(results):
                print(
                    f"{target} artifact_sha256={index['targets'][target]['artifactSha256']} "
                    f"payload_sha256={results[target]['payload']['sha256']}"
                )
            print(f"RENDER-SUMMARY action=render targets={len(results)} failures=0 exit=0")
            return 0
        results = verify_render_root(ROOT, args.verify, render_config, adapter_config)
        index = read_json_object(args.verify / RENDER_INDEX, "render index")
        for target in sorted(results):
            print(
                f"{target} artifact_sha256={index['targets'][target]['artifactSha256']} "
                f"payload_sha256={results[target]['payload']['sha256']}"
            )
        print(f"RENDER-SUMMARY action=verify targets={len(results)} failures=0 exit=0")
        return 0
    except RenderError as exc:
        sys.stderr.write(f"render-packages: {exc}\n")
        print(
            f"RENDER-SUMMARY action={action} targets=0 failures=1 exit=1 code={exc.code}"
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
