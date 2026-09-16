from pathlib import Path

import pytest

from traefik_mcp.validation import (
    ValidationError,
    safe_dynamic_filename,
    validate_backend_url,
    validate_domain,
    validate_kebab_case,
)


def test_kebab_case_valid():
    validate_kebab_case("woodpecker-mcp")


@pytest.mark.parametrize("name", ["Woodpecker", "wood_pecker", "wood--pecker", "-wood", "wood-", ""])
def test_kebab_case_invalid(name):
    with pytest.raises(ValidationError):
        validate_kebab_case(name)


def test_domain_known_suffix_no_warning():
    assert validate_domain("ci.apps2.lumasystem.com") == []


def test_domain_unknown_suffix_warns():
    warnings = validate_domain("example.other.com")
    assert len(warnings) == 1


def test_domain_invalid_shape_raises():
    with pytest.raises(ValidationError):
        validate_domain("not a domain")


def test_backend_url_valid():
    validate_backend_url("http://192.168.17.152:8000")


@pytest.mark.parametrize(
    "url", ["ftp://example.com", "http://", "http://127.0.0.1:8080", "http://localhost"]
)
def test_backend_url_invalid(url):
    with pytest.raises(ValidationError):
        validate_backend_url(url)


def test_safe_dynamic_filename_rejects_traversal(tmp_path: Path):
    with pytest.raises(ValidationError):
        safe_dynamic_filename(tmp_path, "../secrets.env")
    with pytest.raises(ValidationError):
        safe_dynamic_filename(tmp_path, "sub/dir.yml")
    with pytest.raises(ValidationError):
        safe_dynamic_filename(tmp_path, "")


def test_safe_dynamic_filename_accepts_basename(tmp_path: Path):
    result = safe_dynamic_filename(tmp_path, "woodpecker.yml")
    assert result == (tmp_path / "woodpecker.yml").resolve()
