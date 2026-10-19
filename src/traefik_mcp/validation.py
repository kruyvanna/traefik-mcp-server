import re
from pathlib import Path
from urllib.parse import urlparse

KEBAB_CASE_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
DOMAIN_RE = re.compile(r"^[a-z0-9]([a-z0-9-]*[a-z0-9])?(\.[a-z0-9]([a-z0-9-]*[a-z0-9])?)+$")
LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1", "0.0.0.0"}
KNOWN_DOMAIN_SUFFIXES = (".lumasystem.com",)


class ValidationError(Exception):
    pass


def validate_kebab_case(name: str) -> None:
    if not KEBAB_CASE_RE.match(name):
        raise ValidationError(
            f"'{name}' is not kebab-case (expected lowercase letters/digits separated by single hyphens)"
        )


def validate_domain(domain: str) -> list[str]:
    """Returns a list of soft warnings; raises ValidationError only on hard-invalid shapes."""
    if not DOMAIN_RE.match(domain):
        raise ValidationError(f"'{domain}' is not a valid hostname")
    warnings = []
    if not any(domain.endswith(suffix) for suffix in KNOWN_DOMAIN_SUFFIXES):
        warnings.append(
            f"'{domain}' does not end in a known suffix ({', '.join(KNOWN_DOMAIN_SUFFIXES)}) "
            "used by existing routes — double-check this is intentional"
        )
    return warnings


def validate_backend_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValidationError(f"backend_url '{url}' must use http or https")
    if not parsed.hostname:
        raise ValidationError(f"backend_url '{url}' has no host")
    if parsed.hostname in LOOPBACK_HOSTS:
        raise ValidationError(
            f"backend_url '{url}' targets a loopback address — this would create a routing loop"
        )


def safe_dynamic_filename(dynamic_dir: Path, filename: str) -> Path:
    """Resolve `filename` as a bare basename inside dynamic_dir, rejecting any traversal attempt."""
    if not filename or "/" in filename or "\\" in filename or filename in (".", ".."):
        raise ValidationError(f"'{filename}' is not a valid bare filename")
    resolved_dir = dynamic_dir.resolve()
    candidate = (resolved_dir / filename).resolve()
    if candidate.parent != resolved_dir:
        raise ValidationError(f"'{filename}' resolves outside the dynamic config directory")
    return candidate


HEALTH_CHECK_PATH_RE = re.compile(r"^/[A-Za-z0-9._~/-]*$")
DURATION_RE = re.compile(r"^[0-9]+(ms|s|m)$")


def validate_health_check(path: str, interval: str, timeout: str) -> None:
    if not HEALTH_CHECK_PATH_RE.match(path):
        raise ValidationError(f"health_check_path '{path}' must be an absolute URL path like '/healthz'")
    for name, value in (("health_check_interval", interval), ("health_check_timeout", timeout)):
        if not DURATION_RE.match(value):
            raise ValidationError(f"{name} '{value}' must be a duration like '3s' or '500ms'")
