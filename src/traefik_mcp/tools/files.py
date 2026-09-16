from dataclasses import asdict

from .. import dynamic_files
from ..config import Settings


def list_dynamic_files(settings: Settings) -> dict:
    summaries = dynamic_files.list_files(settings.traefik_dynamic_dir, settings.protected_files)
    return {"files": [asdict(s) for s in summaries]}


def read_dynamic_file(settings: Settings, filename: str) -> dict:
    content = dynamic_files.read_file(
        settings.traefik_dynamic_dir, filename, settings.protected_files
    )
    return asdict(content)
