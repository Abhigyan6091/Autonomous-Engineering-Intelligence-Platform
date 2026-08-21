"""
Repository checkout management.

Tools read code from a local directory, so a repository registered by URL has
to be cloned before an investigation can inspect it.
"""
from __future__ import annotations

import asyncio
import re
from pathlib import Path

import structlog

from app.core.config import PROJECT_ROOT, settings

logger = structlog.get_logger(__name__)

# Only plain http(s) clone URLs. Excludes scp-style and ssh:// forms, whose
# hostnames are ambiguous, and any URL carrying embedded credentials.
_URL_RE = re.compile(r"^https?://[A-Za-z0-9.\-]+(?::\d+)?/[\w.\-/]+$")


class RepositoryError(RuntimeError):
    """Raised when a repository cannot be made available locally."""


def _workspace_root() -> Path:
    root = Path(settings.GIT_WORKSPACE_PATH)
    if not root.is_absolute():
        root = PROJECT_ROOT / root
    return root


def is_supported_clone_url(url: str) -> bool:
    """Reject anything that is not a plain http(s) URL without credentials."""
    if not url or "@" in url:
        return False
    # ".." would let a crafted URL walk outside the intended remote path.
    if ".." in url:
        return False
    return bool(_URL_RE.match(url.rstrip("/")))


def checkout_dir_for(repo_id: str) -> Path:
    return _workspace_root() / repo_id


def _clone_or_update(url: str, dest: Path, branch: str) -> None:
    """Blocking git work; run via a worker thread."""
    import git

    if (dest / ".git").exists():
        repo = git.Repo(dest)
        try:
            repo.remotes.origin.fetch(prune=True)
            repo.git.checkout(branch)
            repo.remotes.origin.pull(branch)
        except Exception as exc:
            # A stale checkout is still usable for analysis.
            logger.warning("Could not update checkout", dest=str(dest), error=str(exc))
        return

    dest.parent.mkdir(parents=True, exist_ok=True)
    # depth=1: investigations analyse the current tree, not the full history.
    try:
        git.Repo.clone_from(url, dest, branch=branch, depth=1)
    except Exception:
        # The requested branch may not exist; fall back to the default one.
        git.Repo.clone_from(url, dest, depth=1)


async def ensure_local_checkout(
    repo_id: str, url: str, branch: str = "main", timeout: int = 300
) -> str:
    """
    Return a local path containing the repository, cloning it if needed.

    Raises RepositoryError if the URL is unsupported or the clone fails.
    """
    if not is_supported_clone_url(url):
        raise RepositoryError(f"Unsupported clone URL: {url!r}")

    dest = checkout_dir_for(repo_id)

    logger.info("Preparing checkout", repo_id=repo_id, url=url, dest=str(dest))
    try:
        await asyncio.wait_for(
            asyncio.to_thread(_clone_or_update, url, dest, branch or "main"),
            timeout=timeout,
        )
    except TimeoutError as exc:
        raise RepositoryError(f"Timed out cloning {url}") from exc
    except Exception as exc:
        raise RepositoryError(f"Could not clone {url}: {exc}") from exc

    if not dest.exists():
        raise RepositoryError(f"Checkout directory missing after clone: {dest}")

    logger.info("Checkout ready", repo_id=repo_id, path=str(dest))
    return str(dest)
