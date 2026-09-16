import subprocess
from pathlib import Path


class GitError(Exception):
    pass


class GitDirtyTreeError(GitError):
    def __init__(self, dirty_paths: list[str]):
        self.dirty_paths = dirty_paths
        super().__init__(
            "Refusing to auto-commit: repo has unrelated uncommitted changes: "
            + ", ".join(dirty_paths)
        )


def _run(repo_dir: Path, args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", str(repo_dir), *args],
        capture_output=True,
        text=True,
        check=False,
    )


def assert_clean(repo_dir: Path) -> None:
    result = _run(repo_dir, ["status", "--porcelain"])
    if result.returncode != 0:
        raise GitError(f"git status failed: {result.stderr.strip()}")
    dirty = [line[3:] for line in result.stdout.splitlines() if line.strip()]
    if dirty:
        raise GitDirtyTreeError(dirty)


def assert_branch(repo_dir: Path, expected_branch: str) -> None:
    if not expected_branch:
        return
    result = _run(repo_dir, ["rev-parse", "--abbrev-ref", "HEAD"])
    if result.returncode != 0:
        raise GitError(f"git rev-parse failed: {result.stderr.strip()}")
    current = result.stdout.strip()
    if current != expected_branch:
        raise GitError(
            f"Refusing to auto-commit: on branch '{current}', expected '{expected_branch}'"
        )


def commit_path(repo_dir: Path, relative_path: str, message: str) -> str:
    add_result = _run(repo_dir, ["add", "--", relative_path])
    if add_result.returncode != 0:
        raise GitError(f"git add failed: {add_result.stderr.strip()}")

    commit_result = _run(repo_dir, ["commit", "-m", message])
    if commit_result.returncode != 0:
        raise GitError(f"git commit failed: {commit_result.stderr.strip()}")

    sha_result = _run(repo_dir, ["rev-parse", "HEAD"])
    if sha_result.returncode != 0:
        raise GitError(f"git rev-parse HEAD failed: {sha_result.stderr.strip()}")
    return sha_result.stdout.strip()
