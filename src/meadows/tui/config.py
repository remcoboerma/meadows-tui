"""Configuration for meadows-tui."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass
class TUIConfig:
    server_url: str = "http://localhost:8080"
    token: str | None = None
    jwt_secret: str | None = None
    username: str | None = None
    theme: str = "auto"
    system_name: str = "MEADOWS Chat"
    debug: bool = False

    def __post_init__(self) -> None:
        self.system_name = os.environ.get("MEADOWS_SYSTEM_NAME", self.system_name)


def load_config(
    server_url: str = "http://localhost:8080",
    token: str | None = None,
    jwt_secret: str | None = None,
    username: str | None = None,
    theme: str = "auto",
    debug: bool = False,
) -> TUIConfig:
    return TUIConfig(
        server_url=server_url,
        token=token,
        jwt_secret=jwt_secret,
        username=username,
        theme=theme,
        debug=debug,
    )
