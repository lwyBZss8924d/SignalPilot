"""Bare git repo management — init, delete, list branches via git CLI."""

import logging
import os
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)

REPOS_ROOT = Path(os.getenv("SP_REPOS_DIR", "/repos"))


def _run_git(*args: str, cwd: Path | str | None = None, timeout: int = 30) -> tuple[int, str, str]:
    result = subprocess.run(
        ["git", *args],
        cwd=str(cwd) if cwd else None,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    return result.returncode, result.stdout, result.stderr


def repo_path(project_id: str) -> Path:
    import re
    if not re.match(r"^[a-f0-9\-]{36}$", project_id):
        raise ValueError(f"Invalid project_id: must be a UUID")
    path = REPOS_ROOT / f"{project_id}.git"
    if not str(path.resolve()).startswith(str(REPOS_ROOT.resolve())):
        raise ValueError("Path traversal detected")
    return path


def repo_exists(project_id: str) -> bool:
    try:
        return repo_path(project_id).is_dir()
    except ValueError:
        return False


def init_bare_repo(project_id: str, default_branch: str = "main") -> Path:
    path = repo_path(project_id)
    if path.exists():
        logger.info("Bare repo already exists: %s", path)
        return path

    path.mkdir(parents=True, exist_ok=True)
    rc, out, err = _run_git("init", "--bare", "--initial-branch", default_branch, str(path))
    if rc != 0:
        raise RuntimeError(f"git init --bare failed: {err}")

    _run_git("config", "http.receivepack", "true", cwd=path)
    _run_git("config", "receive.denyCurrentBranch", "updateInstead", cwd=path)

    logger.info("Created bare repo: %s (default branch: %s)", path, default_branch)
    return path


def delete_repo(project_id: str) -> bool:
    path = repo_path(project_id)
    if not path.exists():
        return False

    import shutil
    shutil.rmtree(path)
    logger.info("Deleted bare repo: %s", path)
    return True


def clone_from_remote(project_id: str, clone_url: str) -> Path:
    path = repo_path(project_id)
    if path.exists():
        _run_git("fetch", "--all", cwd=path)
        return path

    rc, out, err = _run_git("clone", "--bare", clone_url, str(path), timeout=120)
    if rc != 0:
        raise RuntimeError(f"git clone --bare failed: {err}")

    _run_git("config", "http.receivepack", "true", cwd=path)
    logger.info("Cloned bare repo from %s", clone_url)
    return path


def list_branches(project_id: str) -> list[str]:
    path = repo_path(project_id)
    if not path.exists():
        return []

    rc, out, err = _run_git("branch", "--list", cwd=path)
    if rc != 0:
        return []

    branches = []
    for line in out.strip().split("\n"):
        name = line.strip().lstrip("* ")
        if name:
            branches.append(name)
    return branches


def materialize_local_branches(project_id: str, default_branch: str = "main") -> None:
    """Create local refs/heads/* from fetched refs/remotes/github/* and point
    HEAD at the default branch.

    A bare repo serves refs/heads/* to clients (the notebook pod clones these).
    But when the bare repo already exists (pre-created at project creation), the
    GitHub link does `git fetch` which only populates refs/remotes/github/* —
    leaving refs/heads/* empty, so the served repo looks empty (0 files). This
    mirrors the fetched remote-tracking refs into local heads.
    """
    path = repo_path(project_id)
    if not path.exists():
        return

    rc, out, _ = _run_git(
        "for-each-ref", "--format=%(refname)", "refs/remotes/github/", cwd=path
    )
    if rc != 0:
        return

    for ref in out.strip().splitlines():
        ref = ref.strip()
        if not ref:
            continue
        branch = ref.removeprefix("refs/remotes/github/")
        if not branch or branch == "HEAD":
            continue
        _run_git("update-ref", f"refs/heads/{branch}", ref, cwd=path)

    # Point HEAD at the default branch if it now exists.
    rc, _, _ = _run_git("rev-parse", "--verify", f"refs/heads/{default_branch}", cwd=path)
    if rc == 0:
        _run_git("symbolic-ref", "HEAD", f"refs/heads/{default_branch}", cwd=path)


def get_head_ref(project_id: str) -> str | None:
    path = repo_path(project_id)
    if not path.exists():
        return None

    rc, out, err = _run_git("symbolic-ref", "HEAD", cwd=path)
    if rc != 0:
        return None
    return out.strip().removeprefix("refs/heads/")


def ensure_repos_dir() -> None:
    REPOS_ROOT.mkdir(parents=True, exist_ok=True)
    logger.info("Git repos directory: %s", REPOS_ROOT)
