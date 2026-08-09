#!/usr/bin/env python3
"""Run pinned networked validators against a fresh render on Ubuntu x64."""

from __future__ import annotations

import hashlib
import importlib.metadata
from datetime import date
from email.parser import Parser
import io
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import sysconfig
import tarfile
import tempfile
import tomllib
from typing import Any, Callable, Dict, List, Sequence, Tuple
import urllib.error
import urllib.request
import zipfile


VERSION = "1.0.1"
ROOT = Path(__file__).resolve().parent.parent
LOCK_PATH = ROOT / "contracts/portable-conformance.lock.json"
VENDOR_SOURCES_PATH = ROOT / "contracts/vendor/SOURCES.json"
VENDORED_SCHEMA_PATH = (
    ROOT / "contracts/vendor/agent-plugins-1.0.0.plugin.schema.json"
)
PORTABLE_TARGETS = ("agent-plugins", "codex", "kimi", "hermes")
ARTIFACT_TARGETS = ("agent-plugins", "codex", "claude", "kimi", "hermes")
BASE_CONFORMANCE_LABELS = {
    "python-version",
    "agent-skills-source",
    "agent-plugin-schema-source",
    "dependency-imports",
    "fresh-render",
    *(f"artifact-schema:{target}" for target in ARTIFACT_TARGETS),
    "render-index-schema",
    "agent-plugin-schema",
    "claude-signature",
    "claude-version",
    "claude-plugin",
}
EXPECTED_WHEELS = {
    "attrs": ("26.1.0", "attrs-26.1.0-py3-none-any.whl"),
    "click": ("8.3.1", "click-8.3.1-py3-none-any.whl"),
    "jsonschema": ("4.26.0", "jsonschema-4.26.0-py3-none-any.whl"),
    "jsonschema-specifications": (
        "2025.9.1", "jsonschema_specifications-2025.9.1-py3-none-any.whl"
    ),
    "python-dateutil": (
        "2.9.0.post0", "python_dateutil-2.9.0.post0-py2.py3-none-any.whl"
    ),
    "referencing": ("0.37.0", "referencing-0.37.0-py3-none-any.whl"),
    "rpds-py": (
        "2026.6.3",
        "rpds_py-2026.6.3-cp313-cp313-manylinux_2_17_x86_64.manylinux2014_x86_64.whl",
    ),
    "six": ("1.17.0", "six-1.17.0-py2.py3-none-any.whl"),
    "strictyaml": ("1.7.3", "strictyaml-1.7.3-py3-none-any.whl"),
}
EXPECTED_RUNTIME_EDGES = {
    "attrs": set(),
    "click": set(),
    "jsonschema": {"attrs", "jsonschema-specifications", "referencing", "rpds-py"},
    "jsonschema-specifications": {"referencing"},
    "python-dateutil": {"six"},
    "referencing": {"attrs", "rpds-py"},
    "rpds-py": set(),
    "six": set(),
    "strictyaml": {"python-dateutil"},
}
VENDOR_SOURCE_KEYS = {
    "id", "file", "url", "publishedUrl", "upstreamRepository", "revision",
    "sourcePath", "sha256", "license", "licensePath", "licenseSha256",
    "retrieved", "governs",
}


# The index response chooses the file URL. Pin the hosts that may serve it so a poisoned
# or intercepted response cannot redirect the fetch to an arbitrary origin.
PYPI_FILE_HOSTS = {"files.pythonhosted.org"}


class ConformanceError(Exception):
    pass


class TransportError(ConformanceError):
    """The upstream could not be reached, so no verdict about this change is available.

    An unreachable or rate-limited host says nothing about whether the rendered artifact
    conforms, and reporting the two identically turns an outage into a false verdict. Three
    kinds of failure are deliberately NOT transport, because each IS a statement about the
    subject: a digest mismatch (supply chain), an HTTP status the server chose to return
    such as 404 or 410 (the pinned artifact is gone, which is a fact about the pin), and a
    local filesystem error (our disk, not their host).
    """


def strict_json_loads(data: str, label: str) -> Any:
    def reject_duplicates(pairs: Sequence[Tuple[str, Any]]) -> Dict[str, Any]:
        value: Dict[str, Any] = {}
        for key, member in pairs:
            if key in value:
                raise ConformanceError(f"{label} repeats JSON key {key!r}")
            value[key] = member
        return value

    def reject_nonfinite(token: str) -> Any:
        raise ConformanceError(f"{label} contains non-finite JSON number {token}")

    try:
        return json.loads(
            data,
            object_pairs_hook=reject_duplicates,
            parse_constant=reject_nonfinite,
        )
    except json.JSONDecodeError as exc:
        raise ConformanceError(f"{label} is not valid JSON: {exc}") from exc


def strict_json_path(path: Path, label: str) -> Any:
    try:
        return strict_json_loads(path.read_text(encoding="utf-8"), label)
    except OSError as exc:
        raise ConformanceError(f"cannot read {label} {path}: {exc}") from exc


def load_agent_plugin_vendor_source(
    path: Path = VENDOR_SOURCES_PATH,
) -> Dict[str, Any]:
    value = strict_json_path(path, "vendored sources")
    if (
        not isinstance(value, dict)
        or set(value) != {"schemaVersion", "note", "sources"}
        or value.get("schemaVersion") != 1
        or not isinstance(value.get("note"), str)
    ):
        raise ConformanceError("vendored sources must be an exact schemaVersion 1 record")
    sources = value.get("sources")
    if not isinstance(sources, list) or len(sources) != 1:
        raise ConformanceError("vendored source inventory must contain exactly one source")
    source = sources[0]
    if not isinstance(source, dict) or set(source) != VENDOR_SOURCE_KEYS:
        raise ConformanceError("Agent Plugins source has missing or unknown fields")
    if (
        source["id"] != "agent-plugins-1.0.0-plugin-manifest"
        or source["file"] != VENDORED_SCHEMA_PATH.name
        or source["publishedUrl"]
        != "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json"
        or source["license"] != "Apache-2.0"
        or source["licensePath"] != "LICENSES/Apache-2.0.txt"
        or not isinstance(source["governs"], str)
        or not source["governs"]
    ):
        raise ConformanceError("Agent Plugins source identity or scope changed")
    repository_match = re.fullmatch(
        r"https://github\.com/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)",
        str(source["upstreamRepository"]),
    )
    revision = str(source["revision"])
    source_path = source["sourcePath"]
    license_path = source["licensePath"]
    if (
        repository_match is None
        or re.fullmatch(r"[0-9a-f]{40}", revision) is None
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
        raise ConformanceError("Agent Plugins upstream identity is invalid")
    owner, repository = repository_match.groups()
    derived_url = (
        f"https://raw.githubusercontent.com/{owner}/{repository}/"
        f"{revision}/{source_path}"
    )
    if source["url"] != derived_url:
        raise ConformanceError(
            "Agent Plugins raw URL does not derive from revision and source path"
        )
    if any(
        re.fullmatch(r"[0-9a-f]{64}", str(source[field])) is None
        for field in ("sha256", "licenseSha256")
    ):
        raise ConformanceError("Agent Plugins source digest is invalid")
    try:
        retrieved = date.fromisoformat(source["retrieved"])
    except (TypeError, ValueError) as exc:
        raise ConformanceError("Agent Plugins retrieval date is invalid") from exc
    if retrieved.isoformat() != source["retrieved"]:
        raise ConformanceError("Agent Plugins retrieval date is non-canonical")
    schema_candidate = path.parent / source["file"]
    local_schema = schema_candidate.resolve()
    vendor_root = path.parent.resolve()
    if (
        vendor_root not in local_schema.parents
        or schema_candidate.is_symlink()
        or not local_schema.is_file()
        or sha256(local_schema) != source["sha256"]
    ):
        raise ConformanceError("Agent Plugins local schema provenance is invalid")
    return source


def vendor_license_url(source: Dict[str, Any]) -> str:
    repository = str(source["upstreamRepository"])
    relative_repository = repository.removeprefix("https://github.com/")
    return (
        f"https://raw.githubusercontent.com/{relative_repository}/"
        f"{source['revision']}/{source['licensePath']}"
    )


def normalized_package(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def isolated_import_paths(site: Path, skills_source: Path) -> List[str]:
    stdlib = Path(sysconfig.get_paths()["stdlib"]).resolve()
    platstdlib = Path(sysconfig.get_paths()["platstdlib"]).resolve()
    raw_destshared = sysconfig.get_config_var("DESTSHARED")
    if not isinstance(raw_destshared, str) or not raw_destshared:
        raise ConformanceError("Python runtime does not declare DESTSHARED")
    destshared = Path(raw_destshared).resolve()
    runtime_root = Path(sys.base_prefix).resolve()
    if not destshared.is_dir() or (
        destshared != runtime_root and runtime_root not in destshared.parents
    ):
        raise ConformanceError(
            f"Python extension-module path is outside the base runtime: {destshared}"
        )
    return list(dict.fromkeys(
        str(path)
        for path in (site.resolve(), skills_source.resolve(), stdlib, platstdlib, destshared)
    ))


def expected_conformance_labels(skills: Sequence[str]) -> set[str]:
    if not skills or len(skills) != len(set(skills)) or not all(
        isinstance(skill, str) and skill for skill in skills
    ):
        raise ConformanceError("portable skill inventory must be non-empty and unique")
    return BASE_CONFORMANCE_LABELS | {
        f"portable:{target}:{skill}"
        for target in PORTABLE_TARGETS
        for skill in skills
    }


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download(
    url: str,
    destination: Path,
    expected: str,
    *,
    response_opener: Callable[..., Any] = urllib.request.urlopen,
) -> None:
    request = urllib.request.Request(url, headers={"User-Agent": "z-harness-conformance/1"})
    try:
        response_context = response_opener(request, timeout=60)
    except urllib.error.HTTPError as exc:
        # The server answered. A pinned artifact that returns 404/410 is a fact about the
        # pin, not an outage, so it must not be excused as transport.
        raise ConformanceError(
            f"pinned artifact unavailable at {url}: HTTP {exc.code} {exc.reason}"
        ) from exc
    except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as exc:
        raise TransportError(f"upstream unreachable for {url}: {exc}") from exc
    try:
        with response_context as response:
            try:
                out = destination.open("wb")
            except OSError as exc:
                raise ConformanceError(f"cannot write {destination}: {exc}") from exc
            with out:
                try:
                    shutil.copyfileobj(response, out, length=1024 * 1024)
                except OSError as exc:
                    raise TransportError(
                        f"upstream stream failed for {url}: {exc}"
                    ) from exc
    except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
        raise TransportError(f"upstream unreachable for {url}: {exc}") from exc
    actual = sha256(destination)
    if actual != expected:
        raise ConformanceError(
            f"download digest mismatch for {url}: expected={expected} actual={actual}"
        )


def validate_vendor_source(
    source: Dict[str, Any],
    destination: Path,
    *,
    downloader: Callable[[str, Path, str], None] = download,
) -> List[str]:
    downloader(source["url"], destination, source["sha256"])
    if destination.read_bytes() != VENDORED_SCHEMA_PATH.read_bytes():
        raise ConformanceError(
            "downloaded Agent Plugins schema differs from the vendored schema"
        )
    downloader(
        vendor_license_url(source),
        destination.with_name("agent-plugins-Apache-2.0.txt"),
        source["licenseSha256"],
    )
    return ["agent-plugin-schema-source"]


def load_lock(path: Path = LOCK_PATH) -> Dict[str, Any]:
    value = strict_json_path(path, "conformance lock")
    if not isinstance(value, dict) or value.get("schemaVersion") != 1:
        raise ConformanceError("conformance lock must be a schemaVersion 1 object")
    if set(value) != {
        "schemaVersion", "pythonVersion", "agentSkills", "claudeCode", "pythonWheels"
    }:
        raise ConformanceError("conformance lock has missing or unknown top-level fields")
    agent = value["agentSkills"]
    if not isinstance(agent, dict) or set(agent) != {
        "archiveSha256", "archiveUrl", "commit", "pyprojectSha256", "uvLockSha256"
    }:
        raise ConformanceError("Agent Skills lock has missing or unknown fields")
    claude = value["claudeCode"]
    if not isinstance(claude, dict) or set(claude) != {
        "binarySha256",
        "binaryUrl",
        "commit",
        "keyFingerprint",
        "keySha256",
        "keyUrl",
        "manifestSha256",
        "manifestSignatureSha256",
        "manifestSignatureUrl",
        "manifestUrl",
        "version",
    }:
        raise ConformanceError("Claude Code lock has missing or unknown fields")
    for label, member in (("Agent Skills", agent), ("Claude Code", claude)):
        for key, item in member.items():
            if key.endswith("Sha256") and re.fullmatch(r"[0-9a-f]{64}", str(item)) is None:
                raise ConformanceError(f"{label} {key} is not a sha256")
            if key.endswith("Url") and not str(item).startswith("https://"):
                raise ConformanceError(f"{label} {key} is not an HTTPS URL")
    if re.fullmatch(r"[0-9a-f]{40}", str(agent["commit"])) is None:
        raise ConformanceError("Agent Skills commit is not a full Git sha")
    if re.fullmatch(r"[0-9a-f]{40}", str(claude["commit"])) is None:
        raise ConformanceError("Claude Code commit is not a full Git sha")
    if re.fullmatch(r"[0-9A-F]{40}", str(claude["keyFingerprint"])) is None:
        raise ConformanceError("Claude Code signing fingerprint is invalid")
    wheels = value["pythonWheels"]
    if not isinstance(wheels, list):
        raise ConformanceError("conformance lock pythonWheels must be an array")
    observed: Dict[str, Tuple[str, str]] = {}
    filenames: set[str] = set()
    for position, entry in enumerate(wheels):
        if not isinstance(entry, dict) or set(entry) != {
            "package", "version", "filename", "sha256"
        }:
            raise ConformanceError(f"wheel lock entry {position} has missing or unknown fields")
        package = normalized_package(str(entry["package"]))
        filename = str(entry["filename"])
        if package in observed or filename in filenames:
            raise ConformanceError(
                f"wheel lock repeats package or filename: {package!r} {filename!r}"
            )
        if re.fullmatch(r"[0-9a-f]{64}", str(entry["sha256"])) is None:
            raise ConformanceError(f"wheel lock {package} has an invalid sha256")
        observed[package] = (str(entry["version"]), filename)
        filenames.add(filename)
    if observed != EXPECTED_WHEELS:
        raise ConformanceError(
            "wheel lock inventory differs from the exact Linux cp313 validator closure"
        )
    return value


def safe_extract_tar(
    archive: Path,
    destination: Path,
    *,
    omitted_symlinks: Dict[str, str] | None = None,
) -> None:
    expected_omissions = omitted_symlinks or {}
    with tarfile.open(archive, "r:gz") as bundle:
        members = bundle.getmembers()
        if not members:
            raise ConformanceError("Agent Skills archive is empty")
        extractable = []
        observed_omissions = set()
        observed_destinations: Dict[Path, str] = {}
        for member in members:
            candidate = (destination / member.name).resolve()
            if destination.resolve() not in candidate.parents and candidate != destination.resolve():
                raise ConformanceError(f"archive path escapes extraction root: {member.name}")
            if candidate in observed_destinations:
                raise ConformanceError(
                    f"archive entries collide at one destination: "
                    f"{observed_destinations[candidate]!r} and {member.name!r}"
                )
            observed_destinations[candidate] = member.name
            if member.issym():
                if expected_omissions.get(member.name) != member.linkname:
                    raise ConformanceError(f"archive contains unsupported entry: {member.name}")
                observed_omissions.add(member.name)
                continue
            if not (member.isreg() or member.isdir()):
                raise ConformanceError(f"archive contains unsupported entry: {member.name}")
            extractable.append(member)
        missing = set(expected_omissions) - observed_omissions
        if missing:
            raise ConformanceError(
                f"archive omits expected non-materialized symlink(s): {sorted(missing)}"
            )
        bundle.extractall(destination, members=extractable, filter="data")


def safe_extract_wheel(wheel: Path, destination: Path) -> None:
    with zipfile.ZipFile(wheel) as bundle:
        names = bundle.namelist()
        if not names:
            raise ConformanceError(f"wheel is empty: {wheel.name}")
        for name in names:
            candidate = (destination / name).resolve()
            if destination.resolve() not in candidate.parents and candidate != destination.resolve():
                raise ConformanceError(f"wheel path escapes extraction root: {name}")
        bundle.extractall(destination)


def active_linux_cp313_requirement(requirement: str) -> bool:
    if ";" not in requirement:
        return True
    marker = requirement.split(";", 1)[1].strip()
    if re.search(r"\bextra\s*==\s*(['\"]).+?\1", marker):
        return False
    if re.fullmatch(r"platform_system\s*==\s*(['\"])Windows\1", marker):
        return False
    if re.fullmatch(r"python_version\s*<\s*(['\"])3\.13\1", marker):
        return False
    raise ConformanceError(f"unclassified wheel environment marker: {marker!r}")


def verify_wheel_metadata(wheel: Path, entry: Dict[str, Any]) -> None:
    with zipfile.ZipFile(wheel) as bundle:
        metadata_names = [
            name for name in bundle.namelist() if name.endswith(".dist-info/METADATA")
        ]
        if len(metadata_names) != 1:
            raise ConformanceError(
                f"wheel {wheel.name} contains {len(metadata_names)} METADATA files"
            )
        metadata = Parser().parsestr(
            bundle.read(metadata_names[0]).decode("utf-8")
        )
    package = normalized_package(str(metadata.get("Name", "")))
    version = str(metadata.get("Version", ""))
    expected_package = normalized_package(entry["package"])
    if package != expected_package or version != entry["version"]:
        raise ConformanceError(
            f"wheel metadata identity mismatch for {wheel.name}: {package} {version}"
        )
    active_dependencies = {
        normalized_package(match.group(1))
        for requirement in metadata.get_all("Requires-Dist", [])
        if active_linux_cp313_requirement(requirement)
        if (match := re.match(r"^([A-Za-z0-9_.-]+)", requirement)) is not None
    }
    if active_dependencies != EXPECTED_RUNTIME_EDGES[expected_package]:
        raise ConformanceError(
            f"wheel dependency edges changed for {expected_package}: "
            f"{sorted(active_dependencies)}"
        )


def active_linux_cp313_uv_dependency(dependency: Dict[str, Any]) -> bool:
    marker = dependency.get("marker")
    if marker is None:
        return True
    if marker == "sys_platform == 'win32'":
        return False
    raise ConformanceError(f"unclassified uv.lock dependency marker {marker!r}")


def verify_upstream_dependency_lock(skills_ref: Path) -> None:
    pyproject = tomllib.loads((skills_ref / "pyproject.toml").read_text(encoding="utf-8"))
    direct = {
        normalized_package(match.group(1))
        for requirement in pyproject.get("project", {}).get("dependencies", [])
        if (match := re.match(r"^([A-Za-z0-9_.-]+)", requirement)) is not None
    }
    if direct != {"click", "strictyaml"}:
        raise ConformanceError(f"skills-ref direct dependencies changed: {sorted(direct)}")

    uv_lock = tomllib.loads((skills_ref / "uv.lock").read_text(encoding="utf-8"))
    packages = uv_lock.get("package", [])
    by_name: Dict[str, Dict[str, Any]] = {}
    for package in packages:
        name = normalized_package(str(package.get("name", "")))
        if not name or name in by_name:
            raise ConformanceError(f"uv.lock has absent or duplicate package {name!r}")
        by_name[name] = package
    closure = {"skills-ref"}
    queue = ["skills-ref"]
    while queue:
        name = queue.pop()
        package = by_name.get(name)
        if package is None:
            raise ConformanceError(f"uv.lock omits dependency package {name!r}")
        for dependency in package.get("dependencies", []):
            if not active_linux_cp313_uv_dependency(dependency):
                continue
            dependency_name = normalized_package(str(dependency.get("name", "")))
            if not dependency_name:
                raise ConformanceError(f"uv.lock {name} has an unnamed dependency")
            if dependency_name not in closure:
                closure.add(dependency_name)
                queue.append(dependency_name)
    expected = {"skills-ref", "click", "strictyaml", "python-dateutil", "six"}
    if closure != expected:
        raise ConformanceError(
            f"skills-ref uv.lock runtime closure changed: {sorted(closure)}"
        )


def prepare_agent_skills_source(
    archive: Path,
    source_root: Path,
    agent_lock: Dict[str, Any],
    *,
    dependency_verifier: Callable[[Path], None] = verify_upstream_dependency_lock,
) -> Path:
    archive_root = f"agentskills-{agent_lock['commit']}"
    safe_extract_tar(
        archive,
        source_root,
        omitted_symlinks={f"{archive_root}/CLAUDE.md": "AGENTS.md"},
    )
    checkout = source_root / archive_root
    skills_ref = checkout / "skills-ref"
    if sha256(skills_ref / "pyproject.toml") != agent_lock["pyprojectSha256"]:
        raise ConformanceError("pinned skills-ref pyproject digest does not match")
    if sha256(skills_ref / "uv.lock") != agent_lock["uvLockSha256"]:
        raise ConformanceError("pinned skills-ref uv.lock digest does not match")
    dependency_verifier(skills_ref)
    readme = (skills_ref / "README.md").read_text(encoding="utf-8")
    if "intended for demonstration purposes only" not in readme:
        raise ConformanceError("skills-ref README no longer carries the demo-only warning")
    return skills_ref


def fetch_pypi_metadata(metadata_url: str) -> Any:
    request = urllib.request.Request(
        metadata_url, headers={"User-Agent": "z-harness-conformance/1"}
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            raw = response.read()
    except urllib.error.HTTPError as exc:
        raise ConformanceError(
            f"pinned metadata unavailable at {metadata_url}: HTTP {exc.code} {exc.reason}"
        ) from exc
    except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as exc:
        raise TransportError(f"upstream unreachable for {metadata_url}: {exc}") from exc
    # A non-UTF8 or non-JSON body is an intermediary serving something other than the
    # index -- a transport-shaped failure. UnicodeDecodeError is a ValueError, so it has
    # to be named explicitly or it escapes classification entirely.
    try:
        payload = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise TransportError(f"non-UTF8 body from {metadata_url}: {exc}") from exc
    try:
        return strict_json_loads(payload, f"PyPI metadata from {metadata_url}")
    except ConformanceError as exc:
        raise TransportError(f"non-JSON body from {metadata_url}: {exc}") from exc


def download_wheels(
    lock: Dict[str, Any],
    download_root: Path,
    site: Path,
    *,
    metadata_loader: Callable[[str], Any] = fetch_pypi_metadata,
    downloader: Callable[[str, Path, str], None] = download,
) -> None:
    for entry in lock["pythonWheels"]:
        metadata_url = (
            f"https://pypi.org/pypi/{entry['package']}/{entry['version']}/json"
        )
        metadata = metadata_loader(metadata_url)
        matches = [
            item for item in metadata.get("urls", [])
            if item.get("filename") == entry["filename"]
        ]
        if len(matches) != 1:
            raise ConformanceError(
                f"PyPI returned {len(matches)} files named {entry['filename']!r}"
            )
        published = matches[0].get("digests", {}).get("sha256")
        if published != entry["sha256"]:
            raise ConformanceError(
                f"PyPI metadata digest differs for {entry['filename']}: {published}"
            )
        wheel = download_root / entry["filename"]
        # The URL is chosen by the index response, not by our lock, so it is untrusted
        # input. The digest still bounds what gets USED, but an unvalidated URL is an
        # arbitrary-fetch primitive from the runner: any scheme urllib supports, any host,
        # no TLS. Lock URLs are already required to be https; hold the response to the
        # same rule and to the host that serves this index's files.
        wheel_url = matches[0].get("url")
        if not isinstance(wheel_url, str) or not wheel_url.startswith("https://"):
            raise ConformanceError(
                f"PyPI supplied a non-https URL for {entry['filename']}: {wheel_url!r}"
            )
        wheel_host = wheel_url.split("/", 3)[2]
        if wheel_host not in PYPI_FILE_HOSTS:
            raise ConformanceError(
                f"PyPI supplied {entry['filename']} from an unexpected host "
                f"{wheel_host!r}; permitted: {sorted(PYPI_FILE_HOSTS)}"
            )
        downloader(wheel_url, wheel, entry["sha256"])
        verify_wheel_metadata(wheel, entry)
        safe_extract_wheel(wheel, site)


def run_checked(argv: Sequence[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        list(argv), capture_output=True, text=True, timeout=120, **kwargs
    )
    if completed.returncode != 0:
        raise ConformanceError(
            f"command failed ({completed.returncode}): {' '.join(argv)}\n"
            f"stdout={completed.stdout}\nstderr={completed.stderr}"
        )
    return completed


def validate_portable_targets(
    render_root: Path,
    skills: Sequence[str],
    validator: Callable[[Path], Any],
) -> List[str]:
    completed: List[str] = []
    for target in PORTABLE_TARGETS:
        for skill in skills:
            problems = validator(render_root / target / "skills" / skill)
            if problems:
                raise ConformanceError(
                    f"skills-ref rejected {target}/{skill} portable skill: {problems}"
                )
            completed.append(f"portable:{target}:{skill}")
    return completed


def validate_artifact_targets(
    render_root: Path,
    artifact_schema: Dict[str, Any],
    validator: Callable[[Any, Dict[str, Any]], Any],
) -> List[str]:
    completed: List[str] = []
    for target in ARTIFACT_TARGETS:
        artifact = strict_json_path(
            render_root / target / "z-harness-artifact.json",
            f"{target} artifact manifest",
        )
        validator(artifact, artifact_schema)
        completed.append(f"artifact-schema:{target}")
    return completed


def validate_claude_cli(
    binary_path: Path,
    render_root: Path,
    expected_version: str,
    *,
    env: Dict[str, str],
    cwd: Path,
    runner: Callable[..., subprocess.CompletedProcess[str]] = run_checked,
) -> List[str]:
    version = runner([str(binary_path), "--version"], env=env, cwd=cwd)
    if not version.stdout.startswith(f"{expected_version} "):
        raise ConformanceError(f"Claude binary reported unexpected version: {version.stdout}")
    runner(
        [str(binary_path), "plugin", "validate", "--strict", str(render_root / "claude")],
        env=env,
        cwd=cwd,
    )
    return ["claude-version", "claude-plugin"]


def validate_claude_signature(
    manifest_path: Path,
    signature_path: Path,
    key_path: Path,
    claude_lock: Dict[str, Any],
    *,
    env: Dict[str, str],
    cwd: Path,
    runner: Callable[..., subprocess.CompletedProcess[str]] = run_checked,
) -> List[str]:
    manifest = strict_json_path(manifest_path, "signed Claude release manifest")
    if (
        manifest.get("version") != claude_lock["version"]
        or manifest.get("commit") != claude_lock["commit"]
        or manifest.get("platforms", {}).get("linux-x64", {}).get("checksum")
        != claude_lock["binarySha256"]
    ):
        raise ConformanceError("Claude release manifest identity does not match lock")
    runner(["gpg", "--batch", "--import", str(key_path)], env=env, cwd=cwd)
    fingerprint = runner(
        ["gpg", "--batch", "--with-colons", "--fingerprint", "security@anthropic.com"],
        env=env,
        cwd=cwd,
    )
    fingerprints = re.findall(
        r"^fpr:::::::::([0-9A-F]+):$", fingerprint.stdout, re.M
    )
    if claude_lock["keyFingerprint"] not in fingerprints:
        raise ConformanceError(f"Claude signing-key fingerprint mismatch: {fingerprints}")
    verification = runner(
        [
            "gpg", "--batch", "--status-fd", "1", "--verify",
            str(signature_path), str(manifest_path),
        ],
        env=env,
        cwd=cwd,
    )
    valid_signatures: List[Tuple[str, str]] = []
    for line in verification.stdout.splitlines():
        fields = line.split()
        if fields[:2] != ["[GNUPG:]", "VALIDSIG"]:
            continue
        if (
            len(fields) != 12
            or re.fullmatch(r"[0-9A-F]{40}", fields[2]) is None
            or re.fullmatch(r"[0-9A-F]{40}", fields[11]) is None
        ):
            raise ConformanceError(f"malformed GPG VALIDSIG status: {line!r}")
        valid_signatures.append((fields[2], fields[11]))
    if (
        len(valid_signatures) != 1
        or valid_signatures[0][1] != claude_lock["keyFingerprint"]
    ):
        raise ConformanceError(
            f"Claude manifest signer fingerprint mismatch: {valid_signatures}"
        )
    return ["claude-signature"]


def conformance() -> int:
    completed: List[str] = []
    try:
        lock = load_lock()
        render_config = strict_json_path(
            ROOT / "release/render.json", "render configuration"
        )
        selected_skills = render_config.get("selectedSkills")
        if not isinstance(selected_skills, list):
            raise ConformanceError("render configuration selectedSkills must be an array")
        expected_labels = expected_conformance_labels(selected_skills)
        actual_python = ".".join(str(part) for part in sys.version_info[:3])
        if actual_python != lock["pythonVersion"]:
            raise ConformanceError(
                f"Python version {actual_python} does not equal pinned {lock['pythonVersion']}"
            )
        completed.append("python-version")
        with tempfile.TemporaryDirectory(prefix="z-harness-conformance-") as raw:
            temp = Path(raw)
            downloads = temp / "downloads"
            source_root = temp / "source"
            site = temp / "site"
            render_root = temp / "rendered"
            gnupg = temp / "gnupg"
            for directory in (downloads, source_root, site, gnupg):
                directory.mkdir(mode=0o700)

            vendor_source = load_agent_plugin_vendor_source()
            completed.extend(validate_vendor_source(
                vendor_source,
                downloads / "agent-plugins-1.0.0.plugin.schema.json",
            ))

            agent_lock = lock["agentSkills"]
            archive = downloads / "agent-skills.tar.gz"
            download(agent_lock["archiveUrl"], archive, agent_lock["archiveSha256"])
            skills_ref = prepare_agent_skills_source(archive, source_root, agent_lock)
            completed.append("agent-skills-source")

            download_wheels(lock, downloads, site)
            sys.path[:] = isolated_import_paths(site, skills_ref / "src")
            import jsonschema  # type: ignore[import-not-found]
            import skills_ref as skills_reference  # type: ignore[import-not-found]
            import strictyaml  # type: ignore[import-not-found]
            if skills_reference.__version__ != "0.1.0":
                raise ConformanceError(
                    f"skills-ref version is {skills_reference.__version__!r}, expected '0.1.0'"
                )
            if importlib.metadata.version("jsonschema") != "4.26.0":
                raise ConformanceError("jsonschema import did not resolve to pinned 4.26.0")
            site_root = site.resolve()
            for package in EXPECTED_WHEELS:
                distribution_root = Path(
                    importlib.metadata.distribution(package).locate_file("")
                ).resolve()
                if distribution_root != site_root:
                    raise ConformanceError(
                        f"distribution {package} resolved outside isolated site: "
                        f"{distribution_root}"
                    )
            if site_root not in Path(jsonschema.__file__).resolve().parents:
                raise ConformanceError("jsonschema module resolved outside isolated site")
            skills_source = (skills_ref / "src").resolve()
            if skills_source not in Path(skills_reference.__file__).resolve().parents:
                raise ConformanceError("skills_ref module resolved outside pinned source")
            yaml_indicators = ("- item", "? key", "@host", "`code`", "]", "}", ",")
            for value in yaml_indicators:
                try:
                    strictyaml.dirty_load(f"value: {value}\n")
                except Exception:
                    continue
                raise ConformanceError(
                    f"pinned StrictYAML unexpectedly accepted indicator scalar {value!r}"
                )
            comment_value = strictyaml.dirty_load(
                "value: visible # hidden comment\n"
            ).data["value"]
            if comment_value != "visible":
                raise ConformanceError(
                    "pinned StrictYAML plain-scalar comment semantics changed"
                )
            completed.append("dependency-imports")

            render = run_checked(
                [sys.executable, "tools/render-packages.py", "--output", str(render_root)],
                cwd=ROOT,
            )
            if not re.search(
                r"^RENDER-SUMMARY action=render targets=5 failures=0 exit=0$",
                render.stdout,
                re.M,
            ):
                raise ConformanceError("fresh renderer output has no successful terminal receipt")
            completed.append("fresh-render")

            completed.extend(
                validate_portable_targets(
                    render_root, selected_skills, skills_reference.validate
                )
            )

            artifact_schema = strict_json_path(
                ROOT / "contracts/artifact-manifest.schema.json", "artifact schema"
            )
            index_schema = strict_json_path(
                ROOT / "contracts/render-index.schema.json", "render-index schema"
            )
            plugin_schema = strict_json_path(
                ROOT / "contracts/vendor/agent-plugins-1.0.0.plugin.schema.json",
                "Agent Plugins schema",
            )
            jsonschema.Draft202012Validator.check_schema(artifact_schema)
            jsonschema.Draft202012Validator.check_schema(index_schema)
            completed.extend(
                validate_artifact_targets(
                    render_root, artifact_schema, jsonschema.validate
                )
            )
            jsonschema.validate(
                strict_json_path(render_root / "render-index.json", "render index"),
                index_schema,
            )
            completed.append("render-index-schema")
            jsonschema.validate(
                strict_json_path(
                    render_root / "agent-plugins/plugin.json", "Agent Plugin manifest"
                ),
                plugin_schema,
            )
            completed.append("agent-plugin-schema")

            claude_lock = lock["claudeCode"]
            manifest_path = downloads / "claude-manifest.json"
            signature_path = downloads / "claude-manifest.json.sig"
            key_path = downloads / "claude-code.asc"
            binary_path = downloads / "claude"
            download(claude_lock["manifestUrl"], manifest_path, claude_lock["manifestSha256"])
            download(
                claude_lock["manifestSignatureUrl"],
                signature_path,
                claude_lock["manifestSignatureSha256"],
            )
            download(claude_lock["keyUrl"], key_path, claude_lock["keySha256"])
            env = {**os.environ, "GNUPGHOME": str(gnupg)}
            completed.extend(validate_claude_signature(
                manifest_path,
                signature_path,
                key_path,
                claude_lock,
                env=env,
                cwd=temp,
            ))

            download(claude_lock["binaryUrl"], binary_path, claude_lock["binarySha256"])
            binary_path.chmod(0o755)
            binary_env = {
                **os.environ,
                "HOME": str(temp / "home"),
                "DISABLE_AUTOUPDATER": "1",
                "DISABLE_TELEMETRY": "1",
            }
            (temp / "home").mkdir()
            completed.extend(validate_claude_cli(
                binary_path,
                render_root,
                claude_lock["version"],
                env=binary_env,
                cwd=temp,
            ))
            if (
                len(completed) != len(set(completed))
                or set(completed) != expected_labels
            ):
                raise ConformanceError(
                    "conformance coverage mismatch: "
                    f"missing={sorted(expected_labels - set(completed))} "
                    f"unknown={sorted(set(completed) - expected_labels)} "
                    f"duplicates={len(completed) - len(set(completed))}"
                )
    except TransportError as exc:
        # An outage is not a verdict about this change. Still non-zero so nothing merges on
        # an unverified conformance claim, but labelled so the red is readable.
        print(f"portable-conformance: transport: {exc}", file=sys.stderr)
        print(
            f"CONFORMANCE-SUMMARY checks={len(completed)} failures=0 "
            f"transport_failures=1 exit=1"
        )
        return 1
    except Exception as exc:
        print(f"portable-conformance: {exc}", file=sys.stderr)
        print(
            f"CONFORMANCE-SUMMARY checks={len(completed)} failures=1 "
            f"transport_failures=0 exit=1"
        )
        return 1
    print(
        f"CONFORMANCE-SUMMARY checks={len(completed)} failures=0 "
        f"transport_failures=0 exit=0"
    )
    return 0


def _classification_of(opener: Callable[..., Any]) -> BaseException:
    """Return the exception fetch_pypi_metadata raises for a given opener."""
    import unittest.mock
    with unittest.mock.patch.object(urllib.request, "urlopen", opener):
        try:
            fetch_pypi_metadata("https://pypi.invalid/simple/x/json")
        except BaseException as exc:  # noqa: BLE001
            return exc
    return RuntimeError("no exception raised")


def selftest() -> int:
    checks = failures = 0
    def expect(label: str, predicate: bool) -> None:
        nonlocal checks, failures
        checks += 1
        failures += not predicate
        print(f"  {'PASS' if predicate else 'FAIL'} {label}")

    def rejects(call: Callable[[], Any]) -> bool:
        try:
            call()
        except ConformanceError:
            return True
        except Exception:
            return False
        return False

    lock = load_lock()
    wheels = lock["pythonWheels"]
    expect("lock pins exact Python 3.13.14", lock["pythonVersion"] == "3.13.14")
    expect("wheel closure is non-empty and fully hashed", bool(wheels) and all(
        re.fullmatch(r"[0-9a-f]{64}", item.get("sha256", "")) for item in wheels
    ))
    versions = {item["package"]: item["version"] for item in wheels}
    expect("skills-ref runtime dependency versions are pinned", all(
        versions.get(name) == version for name, version in {
            "click": "8.3.1", "strictyaml": "1.7.3",
            "python-dateutil": "2.9.0.post0", "six": "1.17.0",
        }.items()
    ))
    expect("jsonschema independent oracle is pinned", versions.get("jsonschema") == "4.26.0")
    expect("Claude binary and signing fingerprint are pinned", lock["claudeCode"]["binarySha256"] == "4e9bec1177ce9690e8bd988b710ac24105e70da428dd094c5adcbbe786a55555" and lock["claudeCode"]["keyFingerprint"] == "31DDDE24DDFAB679F42D7BD2BAA929FF1A7ECACE")
    expect("Agent Skills archive and source files are independently pinned", all(
        re.fullmatch(r"[0-9a-f]{64}", lock["agentSkills"][key])
        for key in ("archiveSha256", "pyprojectSha256", "uvLockSha256")
    ))
    expect(
        "conformance coverage registry is exact and non-empty",
        len(expected_conformance_labels(["ground-claims"])) == 19,
    )
    expect(
        "strict JSON loader rejects every non-finite numeric constant",
        all(
            rejects(lambda token=token: strict_json_loads(
                f'{{"value": {token}}}', "non-finite fixture"
            ))
            for token in ("NaN", "Infinity", "-Infinity")
        ),
    )
    import_paths = isolated_import_paths(Path("isolated-site"), Path("skills-source"))
    import_probe = subprocess.run(
        [
            sys.executable,
            "-I",
            "-S",
            "-c",
            f"import sys; sys.path[:] = {import_paths!r}; import _ssl, math, zlib",
        ],
        capture_output=True,
        text=True,
    )
    expect(
        "isolated import path retains base-runtime extension modules",
        import_probe.returncode == 0,
    )
    expect(
        "marker parser excludes extras with either quote style",
        all(not active_linux_cp313_requirement(
            f"demo; extra == {quote}format{quote}"
        ) for quote in ("'", '"')),
    )
    expect(
        "marker parser excludes Windows dependencies with either quote style",
        all(not active_linux_cp313_requirement(
            f"demo; platform_system == {quote}Windows{quote}"
        ) for quote in ("'", '"')),
    )
    expect(
        "marker parser excludes pre-3.13 dependencies with either quote style",
        all(not active_linux_cp313_requirement(
            f"demo; python_version < {quote}3.13{quote}"
        ) for quote in ("'", '"')),
    )
    expect(
        "marker parser rejects an unclassified environment expression",
        rejects(lambda: active_linux_cp313_requirement(
            "demo; implementation_name == 'pypy'"
        )),
    )
    expect(
        "uv.lock marker filter includes runtime and excludes Windows-only edges",
        active_linux_cp313_uv_dependency({"name": "click"})
        and not active_linux_cp313_uv_dependency({
            "name": "colorama", "marker": "sys_platform == 'win32'"
        }),
    )
    expect(
        "uv.lock marker filter rejects an unclassified edge",
        rejects(lambda: active_linux_cp313_uv_dependency({
            "name": "demo", "marker": "implementation_name == 'pypy'"
        })),
    )

    portable_calls: List[Tuple[str, str]] = []
    def fake_portable(path: Path) -> List[str]:
        portable_calls.append((path.parts[-3], path.name))
        return []
    pilot_skills = ("ground-claims", "second-skill")
    portable_labels = validate_portable_targets(
        Path("render"), pilot_skills, fake_portable
    )
    expect(
        "portable validator helper covers the exact target by skill matrix",
        portable_calls
        == [(target, skill) for target in PORTABLE_TARGETS for skill in pilot_skills]
        and portable_labels
        == [
            f"portable:{target}:{skill}"
            for target in PORTABLE_TARGETS
            for skill in pilot_skills
        ],
    )
    expect(
        "portable validator helper propagates a target rejection",
        rejects(lambda: validate_portable_targets(
            Path("render"),
            ["ground-claims"],
            lambda path: ["planted"] if "codex" in path.parts else [],
        )),
    )

    with tempfile.TemporaryDirectory(prefix="portable-conformance-selftest-") as raw:
        temp = Path(raw)
        vendor_source = load_agent_plugin_vendor_source()
        expect(
            "vendored Agent Plugins source derives its raw URL from its revision",
            f"/{vendor_source['revision']}/{vendor_source['sourcePath']}"
            in vendor_source["url"]
            and f"/{vendor_source['revision']}/{vendor_source['licensePath']}"
            in vendor_license_url(vendor_source),
        )
        vendor_fixture = temp / "vendor"
        vendor_fixture.mkdir(parents=True)
        shutil.copy2(VENDORED_SCHEMA_PATH, vendor_fixture / VENDORED_SCHEMA_PATH.name)
        contradictory_vendor = strict_json_path(
            VENDOR_SOURCES_PATH, "vendored source fixture"
        )
        contradictory_vendor["sources"][0]["revision"] = (
            "a" + contradictory_vendor["sources"][0]["revision"][1:]
        )
        contradictory_path = vendor_fixture / "SOURCES.json"
        contradictory_path.write_text(
            json.dumps(contradictory_vendor, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        expect(
            "vendored Agent Plugins source rejects a revision and raw-URL contradiction",
            rejects(lambda: load_agent_plugin_vendor_source(contradictory_path)),
        )
        invalid_date_vendor = strict_json_path(
            VENDOR_SOURCES_PATH, "vendored source invalid-date fixture"
        )
        invalid_date_vendor["sources"][0]["retrieved"] = "2026-99-99"
        invalid_date_path = vendor_fixture / "invalid-date-SOURCES.json"
        invalid_date_path.write_text(
            json.dumps(invalid_date_vendor, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        expect(
            "vendored Agent Plugins source rejects an impossible calendar date",
            rejects(lambda: load_agent_plugin_vendor_source(invalid_date_path)),
        )
        vendor_download_calls: List[Tuple[str, Path, str]] = []
        def fake_vendor_downloader(
            url: str, destination: Path, expected: str
        ) -> None:
            vendor_download_calls.append((url, destination, expected))
            shutil.copy2(VENDORED_SCHEMA_PATH, destination)
        vendor_destination = temp / "downloaded-agent-plugin-schema.json"
        vendor_labels = validate_vendor_source(
            vendor_source,
            vendor_destination,
            downloader=fake_vendor_downloader,
        )
        expect(
            "vendored schema network helper invokes the exact derived source download",
            vendor_labels == ["agent-plugin-schema-source"]
            and vendor_download_calls
            == [
                (vendor_source["url"], vendor_destination, vendor_source["sha256"]),
                (
                    vendor_license_url(vendor_source),
                    vendor_destination.with_name("agent-plugins-Apache-2.0.txt"),
                    vendor_source["licenseSha256"],
                ),
            ],
        )
        def rejecting_vendor_downloader(
            _url: str, _destination: Path, _expected: str
        ) -> None:
            raise ConformanceError("planted vendored-source download rejection")
        expect(
            "vendored schema network helper propagates source-download failure",
            rejects(lambda: validate_vendor_source(
                vendor_source,
                temp / "rejected-agent-plugin-schema.json",
                downloader=rejecting_vendor_downloader,
            )),
        )

        fixture_commit = "f" * 40
        fixture_root = f"agentskills-{fixture_commit}"
        fixture_pyproject = b"[project]\nname = 'fixture'\n"
        fixture_uv_lock = b"version = 1\n"
        fixture_readme = b"intended for demonstration purposes only\n"
        source_archive = temp / "agent-skills-source.tar.gz"
        with tarfile.open(source_archive, "w:gz") as bundle:
            for relative, data in (
                ("skills-ref/pyproject.toml", fixture_pyproject),
                ("skills-ref/uv.lock", fixture_uv_lock),
                ("skills-ref/README.md", fixture_readme),
                ("AGENTS.md", b"fixture policy\n"),
            ):
                member = tarfile.TarInfo(f"{fixture_root}/{relative}")
                member.size = len(data)
                bundle.addfile(member, io.BytesIO(data))
            claude_link = tarfile.TarInfo(f"{fixture_root}/CLAUDE.md")
            claude_link.type = tarfile.SYMTYPE
            claude_link.linkname = "AGENTS.md"
            bundle.addfile(claude_link)
        fixture_lock = {
            "commit": fixture_commit,
            "pyprojectSha256": hashlib.sha256(fixture_pyproject).hexdigest(),
            "uvLockSha256": hashlib.sha256(fixture_uv_lock).hexdigest(),
        }
        dependency_calls: List[Path] = []
        prepared_root = temp / "prepared-agent-skills"
        prepared_root.mkdir()
        try:
            prepared_skills = prepare_agent_skills_source(
                source_archive,
                prepared_root,
                fixture_lock,
                dependency_verifier=lambda path: dependency_calls.append(path),
            )
            pinned_source_ok = (
                prepared_skills == prepared_root / fixture_root / "skills-ref"
                and dependency_calls == [prepared_skills]
                and not (prepared_root / fixture_root / "CLAUDE.md").exists()
                and (prepared_skills / "README.md").read_bytes() == fixture_readme
            )
        except (ConformanceError, OSError):
            pinned_source_ok = False
        expect(
            "Agent Skills source preparation omits only the pinned CLAUDE symlink",
            pinned_source_ok,
        )
        expect(
            "tar extraction rejects the pinned symlink path with a changed target",
            rejects(lambda: safe_extract_tar(
                source_archive,
                temp / "wrong-agent-skills-link-target",
                omitted_symlinks={f"{fixture_root}/CLAUDE.md": "README.md"},
            )),
        )
        expect(
            "tar extraction rejects an allowlisted symlink absent from the archive",
            rejects(lambda: safe_extract_tar(
                source_archive,
                temp / "missing-agent-skills-link",
                omitted_symlinks={f"{fixture_root}/missing-link": "AGENTS.md"},
            )),
        )

        duplicate_member = tarfile.TarInfo("root/file.txt")
        duplicate_tar = temp / "duplicate-destination.tar.gz"

        def write_tar_case(
            path: Path, member: tarfile.TarInfo, data: bytes = b""
        ) -> None:
            with tarfile.open(path, "w:gz") as bundle:
                regular = tarfile.TarInfo("root/file.txt")
                regular.size = 1
                bundle.addfile(regular, io.BytesIO(b"x"))
                member.size = len(data)
                bundle.addfile(member, io.BytesIO(data) if data else None)

        write_tar_case(duplicate_tar, duplicate_member, b"second")
        expect(
            "tar extraction rejects duplicate members targeting one destination",
            rejects(lambda: safe_extract_tar(
                duplicate_tar, temp / "duplicate-destination-output"
            )),
        )

        unknown_member = tarfile.TarInfo("root/unknown")
        unknown_member.type = b"V"
        unknown_tar = temp / "unknown-entry.tar.gz"
        write_tar_case(unknown_tar, unknown_member, b"unknown")
        expect(
            "tar extraction rejects entry types outside files and directories",
            rejects(lambda: safe_extract_tar(
                unknown_tar, temp / "unknown-entry-output"
            )),
        )

        symlink_member = tarfile.TarInfo("root/link")
        symlink_member.type = tarfile.SYMTYPE
        symlink_member.linkname = "file.txt"
        symlink_tar = temp / "internal-symlink.tar.gz"
        write_tar_case(symlink_tar, symlink_member)
        expect(
            "tar extraction rejects an internal symlink permitted by the data filter",
            rejects(lambda: safe_extract_tar(
                symlink_tar, temp / "internal-symlink-output"
            )),
        )

        hardlink_member = tarfile.TarInfo("root/hardlink")
        hardlink_member.type = tarfile.LNKTYPE
        hardlink_member.linkname = "root/file.txt"
        hardlink_tar = temp / "internal-hardlink.tar.gz"
        write_tar_case(hardlink_tar, hardlink_member)
        expect(
            "tar extraction rejects an internal hardlink",
            rejects(lambda: safe_extract_tar(
                hardlink_tar, temp / "internal-hardlink-output"
            )),
        )

        device_member = tarfile.TarInfo("root/device")
        device_member.type = tarfile.CHRTYPE
        device_member.devmajor = 1
        device_member.devminor = 3
        device_tar = temp / "device.tar.gz"
        write_tar_case(device_tar, device_member)
        expect(
            "tar extraction rejects a special device entry",
            rejects(lambda: safe_extract_tar(device_tar, temp / "device-output")),
        )

        traversal_member = tarfile.TarInfo("../escape.txt")
        traversal_tar = temp / "tar-traversal.tar.gz"
        write_tar_case(traversal_tar, traversal_member, b"escape")
        expect(
            "tar extraction rejects a path traversal entry",
            rejects(lambda: safe_extract_tar(
                traversal_tar, temp / "tar-traversal-output"
            )),
        )

        zip_traversal = temp / "zip-traversal.whl"
        with zipfile.ZipFile(zip_traversal, "w") as bundle:
            bundle.writestr("../escape.py", "escape")
        expect(
            "wheel extraction rejects a path traversal entry",
            rejects(lambda: safe_extract_wheel(
                zip_traversal, temp / "zip-traversal-output"
            )),
        )

        download_bytes = b"pinned transport bytes"
        download_sha = hashlib.sha256(download_bytes).hexdigest()
        opener = lambda *_args, **_kwargs: io.BytesIO(download_bytes)
        correct_download = temp / "correct-download.bin"
        try:
            download(
                "https://example.invalid/correct",
                correct_download,
                download_sha,
                response_opener=opener,
            )
            correct_download_ok = correct_download.read_bytes() == download_bytes
        except ConformanceError:
            correct_download_ok = False
        expect(
            "download accepts bytes matching the pinned digest",
            correct_download_ok,
        )
        expect(
            "download rejects bytes differing from the pinned digest",
            rejects(lambda: download(
                "https://example.invalid/wrong",
                temp / "wrong-download.bin",
                "0" * 64,
                response_opener=opener,
            )),
        )

        synthetic_wheel = temp / EXPECTED_WHEELS["referencing"][1]
        with zipfile.ZipFile(synthetic_wheel, "w") as bundle:
            bundle.writestr(
                "referencing-0.37.0.dist-info/METADATA",
                "Metadata-Version: 2.4\n"
                "Name: referencing\n"
                "Version: 0.37.0\n"
                "Requires-Dist: attrs>=22.2.0\n"
                "Requires-Dist: rpds-py>=0.7.0\n"
                'Requires-Dist: typing-extensions>=4.4.0; python_version < "3.13"\n',
            )
        try:
            verify_wheel_metadata(synthetic_wheel, {
                "package": "referencing",
                "version": "0.37.0",
            })
            synthetic_metadata_ok = True
        except ConformanceError:
            synthetic_metadata_ok = False
        expect(
            "wheel metadata validation handles double-quoted PEP 508 markers",
            synthetic_metadata_ok,
        )
        malicious_wheel = temp / "malicious-attrs.whl"
        with zipfile.ZipFile(malicious_wheel, "w") as bundle:
            bundle.writestr(
                "attrs-26.1.0.dist-info/METADATA",
                "Metadata-Version: 2.4\n"
                "Name: attrs\n"
                "Version: 26.1.0\n"
                "Requires-Dist: evil>=1\n",
            )
        malicious_sha = sha256(malicious_wheel)
        malicious_entry = {
            "package": "attrs",
            "version": "26.1.0",
            "filename": EXPECTED_WHEELS["attrs"][1],
            "sha256": malicious_sha,
        }
        download_root = temp / "download-orchestration"
        extracted_site = temp / "download-site"
        download_root.mkdir()
        extracted_site.mkdir()
        def fake_metadata_loader(_url: str) -> Dict[str, Any]:
            return {"urls": [{
                "filename": malicious_entry["filename"],
                "digests": {"sha256": malicious_sha},
                "url": "https://example.invalid/malicious.whl",
            }]}
        def fake_downloader(_url: str, destination: Path, _expected: str) -> None:
            shutil.copyfile(malicious_wheel, destination)
        expect(
            "wheel download orchestration invokes dependency metadata verification",
            rejects(lambda: download_wheels(
                {"pythonWheels": [malicious_entry]},
                download_root,
                extracted_site,
                metadata_loader=fake_metadata_loader,
                downloader=fake_downloader,
            )),
        )

        # The index response chooses the URL, so it is untrusted input. Prove the fetch is
        # refused before the downloader ever sees it, for a foreign scheme and a foreign
        # https host, and prove the legitimate host is still accepted so this is not a
        # blanket rejection.
        reached: List[str] = []

        def recording_downloader(url: str, destination: Path, _expected: str) -> None:
            reached.append(url)
            shutil.copyfile(malicious_wheel, destination)

        def loader_returning(url: str) -> Callable[[str], Any]:
            def loader(_metadata_url: str) -> Any:
                return {"urls": [{
                    "filename": malicious_entry["filename"],
                    "digests": {"sha256": malicious_sha},
                    "url": url,
                }]}
            return loader

        for label, url in (
            ("file:// URL", f"file://{malicious_wheel}"),
            ("plain http URL", "http://files.pythonhosted.org/x.whl"),
            ("unexpected https host", "https://evil.invalid/x.whl"),
        ):
            before = len(reached)
            refused = rejects(lambda u=url: download_wheels(
                {"pythonWheels": [malicious_entry]},
                download_root,
                extracted_site,
                metadata_loader=loader_returning(u),
                downloader=recording_downloader,
            ))
            expect(
                f"an index-supplied {label} is refused before any fetch",
                refused and len(reached) == before,
            )
        expect(
            "the legitimate file host is still accepted, so the rule is not a blanket refusal",
            rejects(lambda: download_wheels(
                {"pythonWheels": [malicious_entry]},
                download_root,
                extracted_site,
                metadata_loader=loader_returning(
                    "https://files.pythonhosted.org/packages/x.whl"
                ),
                downloader=recording_downloader,
            )) and len(reached) > 0,
        )
        for target in ARTIFACT_TARGETS:
            path = temp / target / "z-harness-artifact.json"
            path.parent.mkdir(parents=True)
            path.write_text("{}\n", encoding="utf-8")
        artifact_calls: List[int] = []
        artifact_labels = validate_artifact_targets(
            temp,
            {},
            lambda _instance, _schema: artifact_calls.append(1),
        )
        expect(
            "artifact schema helper covers the exact target registry",
            len(artifact_calls) == len(ARTIFACT_TARGETS)
            and artifact_labels
            == [f"artifact-schema:{target}" for target in ARTIFACT_TARGETS],
        )
        validator_calls = 0
        def rejecting_artifact(_instance: Any, _schema: Dict[str, Any]) -> None:
            nonlocal validator_calls
            validator_calls += 1
            if validator_calls == 3:
                raise ConformanceError("planted artifact rejection")
        expect(
            "artifact schema helper propagates a validator rejection",
            rejects(lambda: validate_artifact_targets(temp, {}, rejecting_artifact)),
        )

        claude_lock = lock["claudeCode"]
        signed_manifest = temp / "claude-manifest.json"
        signed_manifest_value = {
            "version": claude_lock["version"],
            "commit": claude_lock["commit"],
            "platforms": {
                "linux-x64": {"checksum": claude_lock["binarySha256"]}
            },
        }
        signed_manifest.write_text(
            json.dumps(signed_manifest_value), encoding="utf-8"
        )
        signature = temp / "claude-manifest.json.sig"
        signing_key = temp / "claude-code.asc"
        signature.write_bytes(b"signature")
        signing_key.write_bytes(b"key")
        gpg_calls: List[List[str]] = []
        def fake_gpg_runner(
            argv: Sequence[str], **_kwargs: Any
        ) -> subprocess.CompletedProcess[str]:
            gpg_calls.append(list(argv))
            if "--fingerprint" in argv:
                stdout = f"fpr:::::::::{claude_lock['keyFingerprint']}:\n"
            elif "--verify" in argv:
                stdout = (
                    f"[GNUPG:] VALIDSIG {claude_lock['keyFingerprint']} "
                    "2026-08-08 1786151787 0 4 0 1 10 00 "
                    f"{claude_lock['keyFingerprint']}\n"
                )
            else:
                stdout = ""
            return subprocess.CompletedProcess(list(argv), 0, stdout=stdout, stderr="")
        for identity_field, replacement in (
            ("version", "0.0.0"),
            ("commit", "0" * 40),
            ("binary checksum", "0" * 64),
        ):
            wrong_manifest = temp / f"wrong-{identity_field.replace(' ', '-')}.json"
            wrong_value = json.loads(json.dumps(signed_manifest_value))
            if identity_field == "binary checksum":
                wrong_value["platforms"]["linux-x64"]["checksum"] = replacement
            else:
                wrong_value[identity_field] = replacement
            wrong_manifest.write_text(json.dumps(wrong_value), encoding="utf-8")
            expect(
                f"Claude signature helper binds signed manifest {identity_field}",
                rejects(lambda path=wrong_manifest: validate_claude_signature(
                    path,
                    signature,
                    signing_key,
                    claude_lock,
                    env={},
                    cwd=temp,
                    runner=fake_gpg_runner,
                )),
            )
        signature_labels = validate_claude_signature(
            signed_manifest,
            signature,
            signing_key,
            claude_lock,
            env={},
            cwd=temp,
            runner=fake_gpg_runner,
        )
        expect(
            "Claude signature helper invokes exact import fingerprint and verify calls",
            signature_labels == ["claude-signature"]
            and gpg_calls == [
                ["gpg", "--batch", "--import", str(signing_key)],
                [
                    "gpg", "--batch", "--with-colons", "--fingerprint",
                    "security@anthropic.com",
                ],
                [
                    "gpg", "--batch", "--status-fd", "1", "--verify",
                    str(signature), str(signed_manifest),
                ],
            ],
        )
        def rejecting_gpg_runner(
            argv: Sequence[str], **kwargs: Any
        ) -> subprocess.CompletedProcess[str]:
            if "--verify" in argv:
                raise ConformanceError("planted signature rejection")
            return fake_gpg_runner(argv, **kwargs)
        expect(
            "Claude signature helper propagates detached-signature failure",
            rejects(lambda: validate_claude_signature(
                signed_manifest,
                signature,
                signing_key,
                claude_lock,
                env={},
                cwd=temp,
                runner=rejecting_gpg_runner,
            )),
        )
        def wrong_fingerprint_runner(
            argv: Sequence[str], **_kwargs: Any
        ) -> subprocess.CompletedProcess[str]:
            stdout = "fpr:::::::::0000000000000000000000000000000000000000:\n" \
                if "--fingerprint" in argv else ""
            return subprocess.CompletedProcess(list(argv), 0, stdout=stdout, stderr="")
        expect(
            "Claude signature helper rejects the wrong signing fingerprint",
            rejects(lambda: validate_claude_signature(
                signed_manifest,
                signature,
                signing_key,
                claude_lock,
                env={},
                cwd=temp,
                runner=wrong_fingerprint_runner,
            )),
        )
        def wrong_manifest_signer_runner(
            argv: Sequence[str], **_kwargs: Any
        ) -> subprocess.CompletedProcess[str]:
            other = "0" * 40
            if "--fingerprint" in argv:
                stdout = f"fpr:::::::::{claude_lock['keyFingerprint']}:\n"
            elif "--verify" in argv:
                stdout = (
                    f"[GNUPG:] VALIDSIG {other} "
                    "2026-08-08 1786151787 0 4 0 1 10 00 "
                    f"{other}\n"
                )
            else:
                stdout = ""
            return subprocess.CompletedProcess(
                list(argv), 0, stdout=stdout, stderr=""
            )
        expect(
            "Claude signature helper binds the valid signature to the locked primary key",
            rejects(lambda: validate_claude_signature(
                signed_manifest,
                signature,
                signing_key,
                claude_lock,
                env={},
                cwd=temp,
                runner=wrong_manifest_signer_runner,
            )),
        )

        cli_calls: List[List[str]] = []
        def fake_cli_runner(argv: Sequence[str], **_kwargs: Any) -> subprocess.CompletedProcess[str]:
            cli_calls.append(list(argv))
            stdout = "2.1.226 (Claude Code)\n" if argv[-1] == "--version" else ""
            return subprocess.CompletedProcess(list(argv), 0, stdout=stdout, stderr="")
        cli_labels = validate_claude_cli(
            temp / "claude",
            temp / "render",
            "2.1.226",
            env={},
            cwd=temp,
            runner=fake_cli_runner,
        )
        expect(
            "Claude helper pins version and strict plugin-validation call sites",
            cli_labels == ["claude-version", "claude-plugin"]
            and cli_calls == [
                [str(temp / "claude"), "--version"],
                [
                    str(temp / "claude"), "plugin", "validate", "--strict",
                    str(temp / "render/claude"),
                ],
            ],
        )
        def rejecting_cli_runner(
            argv: Sequence[str], **_kwargs: Any
        ) -> subprocess.CompletedProcess[str]:
            if argv[-1] != "--version":
                raise ConformanceError("planted Claude validator rejection")
            return subprocess.CompletedProcess(
                list(argv), 0, stdout="2.1.226 (Claude Code)\n", stderr=""
            )
        expect(
            "Claude helper propagates strict plugin-validation failure",
            rejects(lambda: validate_claude_cli(
                temp / "claude",
                temp / "render",
                "2.1.226",
                env={},
                cwd=temp,
                runner=rejecting_cli_runner,
            )),
        )

        lock_bytes = LOCK_PATH.read_bytes()
        duplicate_top = temp / "duplicate-top.json"
        duplicate_top.write_bytes(lock_bytes.replace(
            b'  "schemaVersion": 1,\n',
            b'  "schemaVersion": 999,\n  "schemaVersion": 1,\n',
            1,
        ))
        expect(
            "lock loader rejects a duplicate top-level JSON key",
            rejects(lambda: load_lock(duplicate_top)),
        )
        duplicate_nested = temp / "duplicate-nested.json"
        duplicate_nested.write_bytes(lock_bytes.replace(
            b'      "package": "attrs",\n',
            b'      "package": "shadow",\n      "package": "attrs",\n',
            1,
        ))
        expect(
            "lock loader rejects a duplicate nested JSON key",
            rejects(lambda: load_lock(duplicate_nested)),
        )
        duplicate_wheel = json.loads(json.dumps(lock))
        duplicate_wheel["pythonWheels"].append(
            json.loads(json.dumps(duplicate_wheel["pythonWheels"][0]))
        )
        duplicate_wheel_path = temp / "duplicate-wheel.json"
        duplicate_wheel_path.write_text(
            json.dumps(duplicate_wheel), encoding="utf-8"
        )
        expect(
            "lock loader rejects duplicate wheel package and filename entries",
            rejects(lambda: load_lock(duplicate_wheel_path)),
        )
    # Failure classification. Every arm below was previously unreachable by any test: the
    # class existed, both `except` arms in conformance() had never executed, and four
    # failure modes were mislabelled. A verdict label nothing exercises is not a verdict.
    def classify(opener: Callable[..., Any], expected: type) -> bool:
        with tempfile.TemporaryDirectory() as raw:
            target = Path(raw) / "artifact"
            try:
                download("https://example.invalid/x", target, "0" * 64,
                         response_opener=opener)
            except expected as exc:  # noqa: B902
                return type(exc) is expected or isinstance(exc, expected)
            except Exception:
                return False
        return False

    class _Resp(io.BytesIO):
        def __enter__(self): return self
        def __exit__(self, *a): return False

    def _raise(exc: Exception) -> Callable[..., Any]:
        def opener(*_a: Any, **_k: Any) -> Any:
            raise exc
        return opener

    expect(
        "an unreachable host is transport, not a conformance verdict",
        classify(_raise(urllib.error.URLError("no route")), TransportError),
    )
    expect(
        "a timeout is transport",
        classify(_raise(TimeoutError("timed out")), TransportError),
    )
    expect(
        "a pinned artifact returning HTTP 404 is a conformance failure, not an outage",
        classify(
            _raise(urllib.error.HTTPError("u", 404, "Not Found", None, None)),
            ConformanceError,
        )
        and not classify(
            _raise(urllib.error.HTTPError("u", 404, "Not Found", None, None)),
            TransportError,
        ),
    )
    expect(
        "a digest mismatch stays a conformance failure",
        classify(lambda *_a, **_k: _Resp(b"payload"), ConformanceError)
        and not classify(lambda *_a, **_k: _Resp(b"payload"), TransportError),
    )
    expect(
        "a non-UTF8 metadata body is transport, not an unclassified crash",
        isinstance(
            _classification_of(lambda *_a, **_k: _Resp(b"\xff\xfe not utf8")),
            TransportError,
        ),
    )
    expect(
        "a non-JSON metadata body is transport, not a conformance verdict",
        isinstance(
            _classification_of(lambda *_a, **_k: _Resp(b"<html>proxy error</html>")),
            TransportError,
        ),
    )
    def local_write_failure() -> BaseException:
        # The destination is an existing directory, so open("wb") raises IsADirectoryError
        # (an OSError) AFTER the upstream was reached successfully. Reaching this arm via a
        # real local error is the point: the digest path would pass for the wrong reason.
        with tempfile.TemporaryDirectory() as raw:
            blocked = Path(raw) / "occupied"
            blocked.mkdir()
            try:
                download("https://example.invalid/x", blocked, "0" * 64,
                         response_opener=lambda *_a, **_k: _Resp(b"payload"))
            except BaseException as exc:  # noqa: BLE001
                return exc
        return RuntimeError("no exception raised")

    _local = local_write_failure()
    expect(
        "a local write failure is a conformance failure, not blamed on the upstream",
        isinstance(_local, ConformanceError) and not isinstance(_local, TransportError)
        and "cannot write" in str(_local),
    )

    print(f"SELFTEST-SUMMARY suite=portable-conformance checks={checks} failures={failures}")
    return 1 if failures else 0


def main(argv: Sequence[str]) -> int:
    if len(argv) == 2 and argv[1] == "--selftest":
        return selftest()
    if len(argv) == 2 and argv[1] in ("-h", "--help"):
        print(__doc__)
        return 0
    if len(argv) == 2 and argv[1] == "--version":
        print(f"portable-conformance {VERSION}")
        return 0
    if len(argv) != 1:
        print("usage: portable-conformance.py [--selftest|--version]", file=sys.stderr)
        return 2
    return conformance()


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
