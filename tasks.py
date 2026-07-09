from __future__ import annotations

import os
import pathlib
import subprocess

from invoke import Context, task

try:
    from edwh import tasks as edwh_tasks
    from edwh import task as edwh_task
except ImportError:  # pragma: no cover
    edwh_tasks = None
    edwh_task = task

TUI_DIR = pathlib.Path(__file__).resolve().parent
SERVER_DIR = TUI_DIR.parent / "meadows-server"


def _check_env(key: str, default: str = "", comment: str = "") -> str:
    if edwh_tasks is not None:
        return edwh_tasks.check_env(key, default=default, comment=comment)
    import os

    val = os.environ.get(key, default)
    print(f"[check_env fallback] {key}={val!r}  # {comment}")
    return val


@task
def setup(c: Context) -> None:
    """Configure environment for meadows-tui."""

    _check_env(
        "MEADOWS_SERVER_URL",
        default="http://127.0.0.1:8080",
        comment="URL of the meadows-server to connect to",
    )
    _check_env(
        "MEADOWS_JWT_SECRET",
        default="./shared_keys/jwt.key",
        comment="Path to the JWT secret for local token generation",
    )
    _check_env(
        "MEADOWS_USERNAME",
        default="",
        comment="Username used with JWT secret for local token generation",
    )
    _check_env(
        "MEADOWS_THEME",
        default="auto",
        comment="Color theme: dark, light, or auto",
    )
    _check_env(
        "MEADOWS_SYSTEM_NAME",
        default="MEADOWS Chat",
        comment="Display name shown in the TUI title bar",
    )


@task
def test(c: Context) -> None:
    c.run("uv run pytest -q")


@task
def lint(c: Context) -> None:
    c.run("uv run ruff check src tests")


@task
def fmt(c: Context) -> None:
    c.run("uv run ruff format src tests")
    c.run("uv run ruff check --fix src tests")


# ── Git helpers ──────────────────────────────────────────────────────────

def _is_git_repo() -> bool:
    """Check whether TUI_DIR is inside a git repository."""
    result = subprocess.run(
        ["git", "rev-parse", "--is-inside-work-tree"],
        cwd=str(TUI_DIR),
        capture_output=True,
        text=True,
    )
    return result.returncode == 0


def _get_branches() -> list[str]:
    """Return list of local git branches."""
    result = subprocess.run(
        ["git", "branch", "--format=%(refname:short)"],
        cwd=str(TUI_DIR),
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print("ERROR listing git branches:")
        print(result.stderr)
        raise SystemExit(1)
    return [b.strip() for b in result.stdout.strip().splitlines() if b.strip()]


def _get_current_branch() -> str:
    """Return the current git branch name."""
    result = subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
        cwd=str(TUI_DIR),
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _select_branch(branch: str) -> str | None:
    """Resolve branch selection. Returns branch name or None to keep current.

    If ``branch`` is given, validates it exists.
    Otherwise prints a numbered list and prompts the user.
    Returns None if not in a git repo or if current branch is kept.
    """
    if not _is_git_repo():
        if branch:
            print("WARNING: Not a git repository, ignoring --branch.")
        return None

    branches = _get_branches()
    if not branches:
        print("No git branches found.")
        raise SystemExit(1)

    current = _get_current_branch()

    if branch:
        if branch not in branches:
            print(f"Branch '{branch}' not found. Available branches:")
            for b in branches:
                marker = " *" if b == current else ""
                print(f"  {b}{marker}")
            raise SystemExit(1)
        return branch if branch != current else None

    # Interactive selection
    print(f"Current branch: {current}\n")
    print("Available branches:")
    for i, b in enumerate(branches, 1):
        marker = " (current)" if b == current else ""
        print(f"  {i}. {b}{marker}")

    while True:
        try:
            choice = input("\nSelect branch (number, or Enter to keep current): ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            raise SystemExit(0)
        if not choice:
            return None
        try:
            idx = int(choice)
            if 1 <= idx <= len(branches):
                selected = branches[idx - 1]
                return selected if selected != current else None
        except ValueError:
            pass
        print(f"Invalid choice. Enter 1-{len(branches)} or press Enter to keep current.")


def _checkout_branch(branch: str) -> None:
    """Switch to the given git branch."""
    print(f"Switching to branch '{branch}' ...")
    result = subprocess.run(
        ["git", "checkout", branch],
        cwd=str(TUI_DIR),
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(f"ERROR switching to branch '{branch}':")
        print(result.stderr)
        raise SystemExit(1)
    print(result.stdout.strip())


# ── JWT helper ───────────────────────────────────────────────────────────

def _generate_user_token(username: str) -> str:
    """Generate a user JWT by calling the server's inv user-jwt task."""
    result = subprocess.run(
        ["uv", "run", "invoke", "user-jwt", f"--name={username}"],
        cwd=str(SERVER_DIR),
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(f"ERROR generating JWT for user '{username}':")
        print(result.stderr)
        raise SystemExit(1)
    return result.stdout.strip()


# ── Tasks ────────────────────────────────────────────────────────────────

@task(optional=["branch", "username", "debug"])
def tui(c: Context, branch: str = "", username: str = "", debug: bool = False) -> None:
    """Launch the TUI client. Optionally switch git branch first.

    Usage:
        inv tui                            # interactive branch select, then TUI
        inv tui --branch=main              # skip branch prompt
        inv tui --branch=feat/foo --username=alice
        inv tui --debug                    # enable debug logging + diagnostics
    """
    selected = _select_branch(branch)
    if selected:
        _checkout_branch(selected)

    user = username or os.environ.get("USER", "meadows-user")
    print(f"Generating JWT for user '{user}' ...")
    token = _generate_user_token(user)

    server_url = os.environ.get("MEADOWS_SERVER_URL", "http://127.0.0.1:8080")

    cmd = f"uv run python -m meadows.tui.cli --server {server_url} --token {token}"
    if debug:
        cmd += " --debug"

    print(f"Launching TUI (server={server_url}) ...")
    result = c.run(cmd, pty=True)


__all__ = ["setup", "test", "lint", "fmt", "tui"]
