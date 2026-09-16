from pathlib import Path

from .. import dynamic_files, git_ops
from ..config import Settings
from ..route_model import RouteMode, RouteSpec
from ..traefik_client import TraefikClient
from ..validation import ValidationError, validate_backend_url, validate_domain, validate_kebab_case


class RouteToolError(Exception):
    pass


def _relative_to_repo(settings: Settings, path: Path) -> str:
    return str(path.resolve().relative_to(settings.traefik_repo_dir.resolve()))


async def create_or_update_route(settings: Settings, spec: RouteSpec) -> dict:
    dynamic_dir = settings.traefik_dynamic_dir
    repo_dir = settings.traefik_repo_dir

    try:
        validate_kebab_case(spec.router_name)
        domain_warnings = validate_domain(spec.domain)
        validate_backend_url(spec.backend_url)
    except ValidationError as e:
        raise RouteToolError(str(e)) from e

    filename = spec.filename or f"{spec.router_name}.yml"
    if filename in settings.protected_files:
        raise RouteToolError(f"'{filename}' is a protected file and cannot be managed by this tool")

    all_router_names = dynamic_files.get_all_router_names(dynamic_dir)
    existing_filename = all_router_names.get(spec.router_name)

    if spec.mode == RouteMode.CREATE:
        if existing_filename is not None:
            raise RouteToolError(
                f"Router '{spec.router_name}' already exists in '{existing_filename}' — use mode=update"
            )
    else:
        if existing_filename is None:
            raise RouteToolError(f"Router '{spec.router_name}' does not exist — use mode=create")
        if existing_filename != filename:
            raise RouteToolError(
                f"Router '{spec.router_name}' exists in '{existing_filename}', not '{filename}' — "
                "this tool does not move routers between files"
            )

    middlewares = spec.middlewares or settings.default_middlewares
    entry_points = spec.entry_points or settings.default_entry_points
    cert_resolver = spec.cert_resolver or settings.default_cert_resolver

    known_middlewares = dynamic_files.get_all_middleware_names(dynamic_dir)
    unknown = [m for m in middlewares if m not in known_middlewares]
    if unknown:
        raise RouteToolError(f"Unknown middleware(s): {', '.join(unknown)}")

    git_ops.assert_branch(repo_dir, settings.require_branch)
    git_ops.assert_clean(repo_dir)

    comment, entries = dynamic_files.load_entries(dynamic_dir, filename)
    entries = [e for e in entries if e.router_name != spec.router_name]
    entries.append(
        dynamic_files.RouteEntry(
            router_name=spec.router_name,
            domain=spec.domain,
            backend_url=spec.backend_url,
            middlewares=middlewares,
            entry_points=entry_points,
            cert_resolver=cert_resolver,
        )
    )
    if comment is None and spec.comment:
        comment = spec.comment

    written_path = dynamic_files.write_entries(dynamic_dir, filename, comment, entries)
    relative_path = _relative_to_repo(settings, written_path)

    verb = "Add" if spec.mode == RouteMode.CREATE else "Update"
    suffix = f" ({spec.domain})" if spec.mode == RouteMode.CREATE else ""
    message = f"{verb} configuration for {spec.router_name}{suffix} with secure routing\n\nManaged-by: traefik-mcp"

    try:
        commit_sha = git_ops.commit_path(repo_dir, relative_path, message)
    except git_ops.GitError as e:
        return {
            "success": True,
            "file_written": True,
            "committed": False,
            "git_error": str(e),
            "filename": filename,
            "router_name": spec.router_name,
            "domain_warnings": domain_warnings,
        }

    client = TraefikClient(settings.traefik_api_base_url, settings.api_timeout_seconds)
    poll_result = await client.poll_router_status(
        f"{spec.router_name}@file", settings.reload_poll_delays_seconds
    )
    traefik_status = "not_observed"
    if poll_result["observed"]:
        traefik_status = poll_result["router"].get("status", "unknown")

    return {
        "success": True,
        "file_written": True,
        "committed": True,
        "commit_sha": commit_sha,
        "filename": filename,
        "router_name": spec.router_name,
        "traefik_status": traefik_status,
        "poll_detail": poll_result,
        "domain_warnings": domain_warnings,
    }


async def delete_route(settings: Settings, router_name: str, filename: str) -> dict:
    dynamic_dir = settings.traefik_dynamic_dir
    repo_dir = settings.traefik_repo_dir

    if filename in settings.protected_files:
        raise RouteToolError(f"'{filename}' is a protected file and cannot be managed by this tool")

    comment, entries = dynamic_files.load_entries(dynamic_dir, filename)
    if not any(e.router_name == router_name for e in entries):
        raise RouteToolError(f"Router '{router_name}' not found in '{filename}'")

    git_ops.assert_branch(repo_dir, settings.require_branch)
    git_ops.assert_clean(repo_dir)

    remaining = [e for e in entries if e.router_name != router_name]
    if remaining:
        written_path = dynamic_files.write_entries(dynamic_dir, filename, comment, remaining)
    else:
        written_path = dynamic_files.delete_file(dynamic_dir, filename)

    relative_path = _relative_to_repo(settings, written_path)
    message = f"Remove configuration for {router_name} routing\n\nManaged-by: traefik-mcp"

    try:
        commit_sha = git_ops.commit_path(repo_dir, relative_path, message)
    except git_ops.GitError as e:
        return {
            "success": True,
            "file_removed_or_updated": True,
            "committed": False,
            "git_error": str(e),
            "router_name": router_name,
            "filename": filename,
        }

    client = TraefikClient(settings.traefik_api_base_url, settings.api_timeout_seconds)
    poll_result = await client.poll_router_absent(
        f"{router_name}@file", settings.reload_poll_delays_seconds
    )

    return {
        "success": True,
        "file_removed_or_updated": True,
        "committed": True,
        "commit_sha": commit_sha,
        "router_name": router_name,
        "filename": filename,
        "traefik_removed": poll_result["removed"],
        "poll_detail": poll_result,
    }
