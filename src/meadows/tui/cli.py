"""CLI entry point for meadows-tui using click."""

from __future__ import annotations

import click

from meadows.tui.config import load_config


@click.command()
@click.option(
    "--server",
    envvar="MEADOWS_SERVER_URL",
    default="http://localhost:8080",
    show_default=True,
    help="MEADOWS server URL (Socket.IO endpoint).",
)
@click.option(
    "--token",
    envvar="MEADOWS_JWT",
    default=None,
    help="JWT token for authentication. Can also be set via MEADOWS_JWT env var.",
)
@click.option(
    "--jwt-secret",
    envvar="MEADOWS_JWT_SECRET",
    default=None,
    help="JWT secret for local token generation. Alternative to --token.",
)
@click.option(
    "--username",
    envvar="MEADOWS_USERNAME",
    default=None,
    help="Username for local token generation (requires --jwt-secret).",
)
@click.option(
    "--theme",
    envvar="MEADOWS_THEME",
    type=click.Choice(["dark", "light", "auto"]),
    default="auto",
    show_default=True,
    help="Color theme: dark, light, or auto (follow terminal).",
)
@click.option(
    "--log-level",
    envvar="MEADOWS_LOG_LEVEL",
    type=click.Choice(["DEBUG", "INFO", "WARNING", "ERROR"]),
    default="WARNING",
    show_default=True,
    help="Logging verbosity.",
)
def main(
    server: str,
    token: str | None,
    jwt_secret: str | None,
    username: str | None,
    theme: str,
    log_level: str,
) -> None:
    """Launch the MEADOWS terminal chat client."""
    import logging

    logging.basicConfig(level=getattr(logging, log_level.upper(), logging.WARNING))

    config = load_config(
        server_url=server,
        token=token,
        jwt_secret=jwt_secret,
        username=username,
        theme=theme,
    )

    from meadows.tui.app import run_app

    run_app(config)


if __name__ == "__main__":
    main()
