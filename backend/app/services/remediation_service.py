"""
Remediation application and verification.

A patch is applied on a dedicated branch so the working branch is never
modified, and the change is always reversible by deleting that branch.
"""
from __future__ import annotations

import asyncio
import subprocess
import tempfile
from pathlib import Path
from typing import Any

import structlog

logger = structlog.get_logger(__name__)

BRANCH_PREFIX = "aeip/remediation"


class RemediationError(RuntimeError):
    """Raised when a patch cannot be applied or verified."""


def _run(cmd: list[str], cwd: str, timeout: int = 120) -> subprocess.CompletedProcess:
    return subprocess.run(  # noqa: S603 - fixed argv, no shell
        cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout
    )


def _apply_patch_sync(workspace: str, patch: str, branch: str) -> dict[str, Any]:
    """Create the branch, apply the patch, and report what happened."""
    root = Path(workspace)
    if not (root / ".git").exists():
        raise RemediationError(f"Not a git repository: {workspace}")

    original = _run(["git", "rev-parse", "--abbrev-ref", "HEAD"], workspace)
    original_branch = original.stdout.strip() or "HEAD"

    created = _run(["git", "checkout", "-b", branch], workspace)
    if created.returncode != 0:
        raise RemediationError(f"Could not create branch {branch}: {created.stderr.strip()}")

    def _restore() -> None:
        _run(["git", "checkout", "--force", original_branch], workspace)
        _run(["git", "branch", "-D", branch], workspace)

    with tempfile.NamedTemporaryFile("w", suffix=".patch", delete=False) as fh:
        fh.write(patch if patch.endswith("\n") else patch + "\n")
        patch_file = fh.name

    try:
        # Dry run first so a malformed patch never half-applies.
        check = _run(["git", "apply", "--check", patch_file], workspace)
        if check.returncode != 0:
            _restore()
            return {
                "applied": False,
                "branch": None,
                "original_branch": original_branch,
                "error": f"Patch does not apply cleanly: {check.stderr.strip()[:500]}",
            }

        applied = _run(["git", "apply", patch_file], workspace)
        if applied.returncode != 0:
            _restore()
            return {
                "applied": False,
                "branch": None,
                "original_branch": original_branch,
                "error": f"git apply failed: {applied.stderr.strip()[:500]}",
            }

        # Exclude build artefacts a test run may have produced; commit only
        # what the patch actually changed.
        _run([
            "git", "add", "-A", "--",
            ".", ":(exclude)**/__pycache__/**", ":(exclude)*.pyc",
            ":(exclude).pytest_cache/**",
        ], workspace)
        _run(
            ["git", "-c", "user.email=aeip@local", "-c", "user.name=AEIP",
             "commit", "-m", f"AEIP remediation on {branch}"],
            workspace,
        )
        changed = _run(["git", "diff", "--name-only", f"{original_branch}...HEAD"], workspace)
        return {
            "applied": True,
            "branch": branch,
            "original_branch": original_branch,
            "files_changed": [f for f in changed.stdout.splitlines() if f],
            "error": None,
        }
    finally:
        Path(patch_file).unlink(missing_ok=True)


def _run_tests_sync(workspace: str, timeout: int) -> dict[str, Any]:
    """Run the workspace test suite and summarise the outcome."""
    try:
        res = _run(["python", "-m", "pytest", "-q", "--tb=short"], workspace, timeout=timeout)
    except subprocess.TimeoutExpired:
        return {"ran": False, "passed": False, "summary": "Test run timed out", "output": ""}

    output = (res.stdout + res.stderr)[-8000:]
    # returncode 5 == pytest collected no tests; that is not a failure of the patch.
    if res.returncode == 5:
        return {"ran": False, "passed": False, "summary": "No tests collected", "output": output}
    return {
        "ran": True,
        "passed": res.returncode == 0,
        "summary": "Tests passed" if res.returncode == 0 else "Tests failed",
        "output": output,
    }


def _restore_branch_sync(workspace: str, branch: str, original_branch: str) -> None:
    _run(["git", "checkout", "--force", original_branch], workspace)
    _run(["git", "branch", "-D", branch], workspace)


async def apply_remediation(
    workspace: str, patch: str, investigation_id: str
) -> dict[str, Any]:
    """Apply a patch on an isolated branch. Never touches the current branch."""
    if not patch or not patch.strip():
        return {"applied": False, "branch": None, "error": "Empty patch"}

    branch = f"{BRANCH_PREFIX}/{investigation_id[:8]}"
    try:
        return await asyncio.to_thread(_apply_patch_sync, workspace, patch, branch)
    except RemediationError as exc:
        return {"applied": False, "branch": None, "error": str(exc)}
    except Exception as exc:  # noqa: BLE001 - surfaced to the investigation
        logger.error("Patch application failed", error=str(exc), exc_info=True)
        return {"applied": False, "branch": None, "error": str(exc)}


async def verify_remediation(workspace: str, timeout: int = 300) -> dict[str, Any]:
    """Run the test suite against the applied patch."""
    try:
        return await asyncio.to_thread(_run_tests_sync, workspace, timeout)
    except Exception as exc:  # noqa: BLE001
        logger.error("Verification failed", error=str(exc), exc_info=True)
        return {"ran": False, "passed": False, "summary": str(exc), "output": ""}


async def rollback_remediation(workspace: str, branch: str, original_branch: str) -> None:
    """Discard the remediation branch and return to where we started."""
    try:
        await asyncio.to_thread(_restore_branch_sync, workspace, branch, original_branch)
        logger.info("Remediation rolled back", branch=branch)
    except Exception as exc:  # noqa: BLE001
        logger.error("Rollback failed", branch=branch, error=str(exc))
