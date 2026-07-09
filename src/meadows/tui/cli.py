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
@click.option(
    "--debug/--no-debug",
    envvar="MEADOWS_DEBUG",
    default=False,
    show_default=True,
    help="Enable debug mode: sets log level to DEBUG and dumps connection diagnostics.",
)
def main(
    server: str,
    token: str | None,
    jwt_secret: str | None,
    username: str | None,
    theme: str,
    log_level: str,
    debug: bool,
) -> None:
    """Launch the MEADOWS terminal chat client."""
    import logging
    import sys

    if debug:
        log_level = "DEBUG"

    logging.basicConfig(level=getattr(logging, log_level.upper(), logging.WARNING))

    config = load_config(
        server_url=server,
        token=token,
        jwt_secret=jwt_secret,
        username=username,
        theme=theme,
        debug=debug,
    )

    if debug:
        import jwt as pyjwt

        print("=== MEADOWS TUI DEBUG ===", file=sys.stderr)
        print(f"  server_url : {config.server_url}", file=sys.stderr)
        print(f"  theme      : {config.theme}", file=sys.stderr)
        print(f"  system_name: {config.system_name}", file=sys.stderr)
        if config.token:
            try:
                claims = pyjwt.decode(config.token, options={"verify_signature": False})
                print(f"  token sub  : {claims.get('sub', '?')}", file=sys.stderr)
                print(f"  token role : {claims.get('role', '?')}", file=sys.stderr)
                print(f"  token exp  : {claims.get('exp', '?')}", file=sys.stderr)
            except Exception as exc:
                print(f"  token decode error: {exc}", file=sys.stderr)
            print(f"  token (raw): {config.token[:60]}...", file=sys.stderr)
        elif config.jwt_secret and config.username:
            print(f"  jwt_secret : {config.jwt_secret}", file=sys.stderr)
            print(f"  username   : {config.username}", file=sys.stderr)
        else:
            print("  auth       : (none — will show auth screen)", file=sys.stderr)
        print("=========================", file=sys.stderr)

    from meadows.tui.app import run_app

    run_app(config)


if __name__ == "__main__":
    main()
