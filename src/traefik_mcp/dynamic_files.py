import os
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml

from .validation import safe_dynamic_filename


@dataclass
class HealthCheck:
    path: str
    interval: Optional[str] = None
    timeout: Optional[str] = None


@dataclass
class RouteEntry:
    router_name: str
    domain: str
    # The first backend; kept so single-backend callers can still pass/read one URL.
    backend_url: str = ""
    middlewares: list[str] = field(default_factory=list)
    entry_points: list[str] = field(default_factory=list)
    cert_resolver: Optional[str] = None
    # Every server of the service, in order (backend_url is backend_urls[0]).
    backend_urls: list[str] = field(default_factory=list)
    health_check: Optional[HealthCheck] = None

    def __post_init__(self) -> None:
        if not self.backend_urls and self.backend_url:
            self.backend_urls = [self.backend_url]
        self.backend_url = self.backend_urls[0] if self.backend_urls else ""


@dataclass
class FileSummary:
    name: str
    protected: bool
    router_names: list[str]
    size: int
    modified: float


@dataclass
class FileContent:
    name: str
    protected: bool
    raw: str
    parsed: Optional[dict]


class DynamicFileError(Exception):
    pass


def _yaml_files(dynamic_dir: Path) -> list[Path]:
    return sorted(
        p for p in dynamic_dir.iterdir() if p.is_file() and p.suffix in (".yml", ".yaml")
    )


def list_files(dynamic_dir: Path, protected_files: frozenset[str]) -> list[FileSummary]:
    summaries = []
    for path in _yaml_files(dynamic_dir):
        _, entries = load_entries(dynamic_dir, path.name)
        stat = path.stat()
        summaries.append(
            FileSummary(
                name=path.name,
                protected=path.name in protected_files,
                router_names=[e.router_name for e in entries],
                size=stat.st_size,
                modified=stat.st_mtime,
            )
        )
    return summaries


def read_file(dynamic_dir: Path, filename: str, protected_files: frozenset[str]) -> FileContent:
    path = safe_dynamic_filename(dynamic_dir, filename)
    raw = path.read_text() if path.exists() else ""
    parsed = yaml.safe_load(raw) if raw.strip() else None
    return FileContent(
        name=filename, protected=filename in protected_files, raw=raw, parsed=parsed
    )


def get_all_router_names(dynamic_dir: Path) -> dict[str, str]:
    """Map router_name -> filename, across every dynamic/*.yml file."""
    names: dict[str, str] = {}
    for path in _yaml_files(dynamic_dir):
        _, entries = load_entries(dynamic_dir, path.name)
        for entry in entries:
            names[entry.router_name] = path.name
    return names


def get_all_middleware_names(dynamic_dir: Path) -> set[str]:
    names: set[str] = set()
    for path in _yaml_files(dynamic_dir):
        try:
            data = yaml.safe_load(path.read_text()) or {}
        except yaml.YAMLError:
            continue
        middlewares = (data.get("http") or {}).get("middlewares") or {}
        names.update(middlewares.keys())
    return names


def _extract_domain(rule: str) -> str:
    # Rules in this repo are always exactly: Host(`<domain>`)
    start = rule.find("`")
    end = rule.rfind("`")
    if start == -1 or end == -1 or start == end:
        raise DynamicFileError(f"Could not parse domain out of rule: {rule!r}")
    return rule[start + 1 : end]


def _leading_comment(raw: str) -> Optional[str]:
    for line in raw.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("#"):
            return stripped[1:].strip()
        break
    return None


def load_entries(dynamic_dir: Path, filename: str) -> tuple[Optional[str], list[RouteEntry]]:
    """Returns (leading_comment, entries). Returns (None, []) if the file doesn't exist."""
    path = dynamic_dir / filename
    if not path.exists():
        return None, []

    raw = path.read_text()
    data = yaml.safe_load(raw) or {}
    comment = _leading_comment(raw)

    http = data.get("http") or {}
    routers = http.get("routers") or {}
    services = http.get("services") or {}

    entries: list[RouteEntry] = []
    for name, router in routers.items():
        service_name = router.get("service", name)
        service = services.get(service_name) or {}
        load_balancer = service.get("loadBalancer") or {}
        servers = load_balancer.get("servers") or []
        health = load_balancer.get("healthCheck") or {}
        tls = router.get("tls") or {}
        entries.append(
            RouteEntry(
                router_name=name,
                domain=_extract_domain(router.get("rule", "")),
                backend_urls=[s["url"] for s in servers if s.get("url")],
                middlewares=list(router.get("middlewares") or []),
                entry_points=list(router.get("entryPoints") or []),
                cert_resolver=tls.get("certResolver"),
                health_check=HealthCheck(
                    path=health["path"], interval=health.get("interval"), timeout=health.get("timeout")
                )
                if health.get("path")
                else None,
            )
        )
    return comment, entries


def render_file(comment: Optional[str], entries: list[RouteEntry]) -> str:
    lines: list[str] = []
    if comment:
        lines.append(f"# {comment}")
    lines.append("http:")
    lines.append("  routers:")
    for i, e in enumerate(entries):
        if i > 0:
            lines.append("")
        lines.append(f"    {e.router_name}:")
        lines.append(f'      rule: "Host(`{e.domain}`)"')
        lines.append("      entryPoints:")
        for ep in e.entry_points:
            lines.append(f"        - {ep}")
        lines.append(f"      service: {e.router_name}")
        if e.cert_resolver:
            lines.append("      tls:")
            lines.append(f"        certResolver: {e.cert_resolver}")
        if e.middlewares:
            lines.append("      middlewares:")
            for mw in e.middlewares:
                lines.append(f"        - {mw}")
    lines.append("")
    lines.append("  services:")
    for i, e in enumerate(entries):
        if i > 0:
            lines.append("")
        lines.append(f"    {e.router_name}:")
        lines.append("      loadBalancer:")
        lines.append("        servers:")
        for url in e.backend_urls:
            lines.append(f'          - url: "{url}"')
        if e.health_check:
            lines.append("        healthCheck:")
            lines.append(f"          path: {e.health_check.path}")
            if e.health_check.interval:
                lines.append(f"          interval: {e.health_check.interval}")
            if e.health_check.timeout:
                lines.append(f"          timeout: {e.health_check.timeout}")
    lines.append("")
    return "\n".join(lines)


def write_entries(dynamic_dir: Path, filename: str, comment: Optional[str], entries: list[RouteEntry]) -> Path:
    path = safe_dynamic_filename(dynamic_dir, filename)
    content = render_file(comment, entries)
    # Sanity round-trip: confirm what we just generated is valid YAML with the routers we intended.
    parsed = yaml.safe_load(content)
    parsed_names = set((parsed.get("http", {}).get("routers") or {}).keys())
    expected_names = {e.router_name for e in entries}
    if parsed_names != expected_names:
        raise DynamicFileError(
            f"Rendered YAML round-trip mismatch: expected routers {expected_names}, got {parsed_names}"
        )

    fd, tmp_path = tempfile.mkstemp(dir=dynamic_dir, prefix=f".{filename}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            f.write(content)
        os.replace(tmp_path, path)
    except BaseException:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        raise
    return path


def delete_file(dynamic_dir: Path, filename: str) -> Path:
    path = safe_dynamic_filename(dynamic_dir, filename)
    if path.exists():
        path.unlink()
    return path
