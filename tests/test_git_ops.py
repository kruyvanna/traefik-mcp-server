from pathlib import Path

import pytest

from traefik_mcp import git_ops


def test_assert_clean_passes_on_clean_repo(repo_dir: Path):
    git_ops.assert_clean(repo_dir)


def test_assert_clean_raises_on_dirty_repo(repo_dir: Path):
    (repo_dir / "dynamic" / "dynamic.yml").write_text("# hand edit\n")
    with pytest.raises(git_ops.GitDirtyTreeError) as exc_info:
        git_ops.assert_clean(repo_dir)
    assert "dynamic/dynamic.yml" in exc_info.value.dirty_paths


def test_assert_branch_passes_on_main(repo_dir: Path):
    git_ops.assert_branch(repo_dir, "main")


def test_assert_branch_raises_on_mismatch(repo_dir: Path):
    with pytest.raises(git_ops.GitError):
        git_ops.assert_branch(repo_dir, "production")


def test_commit_path_creates_commit_and_returns_sha(repo_dir: Path):
    target = repo_dir / "dynamic" / "gitea.yml"
    target.write_text("http:\n  routers: {}\n")

    sha = git_ops.commit_path(repo_dir, "dynamic/gitea.yml", "Add configuration for gitea")

    assert len(sha) == 40
    git_ops.assert_clean(repo_dir)  # committed, tree clean again


def test_commit_path_stages_deletion(repo_dir: Path):
    (repo_dir / "dynamic" / "sample-test.yml").unlink()
    sha = git_ops.commit_path(repo_dir, "dynamic/sample-test.yml", "Remove configuration for whoami-file-test")
    assert len(sha) == 40
    git_ops.assert_clean(repo_dir)
