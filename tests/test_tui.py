"""Tests for meadows-tui — curses-based TUI."""

from __future__ import annotations

import os
import queue
from typing import Any


from meadows.tui.__about__ import __version__
from meadows.tui.config import TUIConfig, load_config
from meadows.tui.themes import DARK_THEME, LIGHT_THEME, THEMES, get_theme


class TestVersion:
    def test_version(self) -> None:
        assert __version__ == "0.1.0"


class TestConfig:
    def test_load_config_defaults(self) -> None:
        cfg = load_config()
        assert cfg.server_url == "http://localhost:8080"
        assert cfg.theme == "auto"
        assert cfg.token is None
        assert cfg.jwt_secret is None
        assert cfg.username is None

    def test_load_config_explicit(self) -> None:
        cfg = load_config(
            server_url="http://example.com:9090",
            token="eyJtoken",
            jwt_secret="secret123",
            username="alice",
            theme="dark",
        )
        assert cfg.server_url == "http://example.com:9090"
        assert cfg.token == "eyJtoken"
        assert cfg.jwt_secret == "secret123"
        assert cfg.username == "alice"
        assert cfg.theme == "dark"

    def test_tuiconfig_defaults(self) -> None:
        cfg = TUIConfig()
        assert cfg.server_url == "http://localhost:8080"
        assert cfg.theme == "auto"
        assert cfg.system_name == "MEADOWS Chat"

    def test_tuiconfig_system_name_from_env(self, monkeypatch) -> None:
        monkeypatch.setenv("MEADOWS_SYSTEM_NAME", "Custom Chat")
        cfg = TUIConfig()
        assert cfg.system_name == "Custom Chat"


class TestThemes:
    def test_dark_theme_has_required_keys(self) -> None:
        required = {"primary", "background", "surface", "text", "text-muted", "border", "error"}
        assert required.issubset(DARK_THEME.keys())

    def test_light_theme_has_required_keys(self) -> None:
        required = {"primary", "background", "surface", "text", "text-muted", "border", "error"}
        assert required.issubset(LIGHT_THEME.keys())

    def test_get_theme_returns_dark_for_unknown(self) -> None:
        assert get_theme("nonexistent") == DARK_THEME

    def test_get_theme_returns_correct(self) -> None:
        assert get_theme("dark") == DARK_THEME
        assert get_theme("light") == LIGHT_THEME

    def test_themes_are_different(self) -> None:
        assert DARK_THEME["background"] != LIGHT_THEME["background"]

    def test_theme_registry(self) -> None:
        assert set(THEMES.keys()) == {"dark", "light"}


class TestClientBridge:
    def test_bridge_initial_state(self) -> None:
        from meadows.tui.client_bridge import ClientBridge

        q: queue.Queue[tuple[str, dict[str, Any]]] = queue.Queue()
        bridge = ClientBridge(q, "http://localhost:8080")
        assert bridge.connected is False
        assert bridge.authenticated is False
        assert bridge.auth_data is None

    def test_bridge_auth_data(self) -> None:
        from meadows.tui.client_bridge import AuthData

        data = {
            "user_id": "user-alice",
            "username": "alice",
            "groups": [{"id": "general"}],
            "bots": [],
            "permissions": ["mention-all"],
            "available_permissions": ["mention-all", "user-invite"],
        }
        ad = AuthData(data)
        assert ad.user_id == "user-alice"
        assert ad.username == "alice"
        assert ad.groups == [{"id": "general"}]
        assert "mention-all" in ad.permissions

    def test_bridge_emit_puts_on_queue(self) -> None:
        from meadows.tui.client_bridge import ClientBridge

        q: queue.Queue[tuple[str, dict[str, Any]]] = queue.Queue()
        bridge = ClientBridge(q, "http://localhost:8080")
        bridge._emit("test_event", {"key": "value"})
        event, data = q.get_nowait()
        assert event == "test_event"
        assert data == {"key": "value"}


class TestCLI:
    def test_cli_help(self) -> None:
        from click.testing import CliRunner
        from meadows.tui.cli import main

        runner = CliRunner()
        result = runner.invoke(main, ["--help"])
        assert result.exit_code == 0
        assert "--server" in result.output
        assert "--token" in result.output
        assert "--theme" in result.output

    def test_cli_defaults(self) -> None:
        from click.testing import CliRunner
        from meadows.tui.cli import main

        runner = CliRunner()
        result = runner.invoke(main, ["--help"])
        assert "http://localhost:8080" in result.output
        assert "dark" in result.output or "auto" in result.output

    def test_cli_invalid_theme(self) -> None:
        from click.testing import CliRunner
        from meadows.tui.cli import main

        runner = CliRunner()
        result = runner.invoke(main, ["--theme", "pink"])
        assert result.exit_code != 0


class TestCursesApp:
    def test_app_init(self) -> None:
        from meadows.tui.app import CursesApp

        config = TUIConfig(server_url="http://localhost:8080", theme="dark")
        app = CursesApp(config)
        assert app._screen == "auth"
        assert app._theme_name == "dark"
        assert app._sidebar_visible is True
        assert app._focus == "input"

    def test_app_auto_theme(self) -> None:
        from meadows.tui.app import CursesApp

        if "COLORFGBG" in os.environ:
            del os.environ["COLORFGBG"]

        config = TUIConfig(server_url="http://localhost:8080", theme="auto")
        app = CursesApp(config)
        assert app._theme_name == "dark"

    def test_app_light_theme(self) -> None:
        from meadows.tui.app import CursesApp

        config = TUIConfig(server_url="http://localhost:8080", theme="light")
        app = CursesApp(config)
        assert app._theme_name == "light"

    def test_format_message_user(self) -> None:
        from meadows.tui.app import CursesApp

        config = TUIConfig(theme="dark")
        app = CursesApp(config)
        app._stdscr = None

        data = {
            "id": "msg-1",
            "group_id": "general",
            "type": "user",
            "user_id": "user-alice",
            "username": "alice",
            "content": "hello world",
            "timestamp": "2025-01-01T12:00:00.000000",
        }
        lines = app._format_message(data, 80, "user-alice")
        text = " ".join(t for t, _ in lines)
        assert "alice" in text
        assert "hello world" in text
        assert "(you)" in text

    def test_format_message_bot(self) -> None:
        from meadows.tui.app import CursesApp

        config = TUIConfig(theme="dark")
        app = CursesApp(config)
        app._stdscr = None

        data = {
            "id": "msg-2",
            "group_id": "general",
            "type": "bot",
            "user_id": "bot-helper",
            "bot_name": "helper",
            "content": "I am a bot",
            "timestamp": "2025-01-01T12:00:00.000000",
        }
        lines = app._format_message(data, 80, "user-alice")
        text = " ".join(t for t, _ in lines)
        assert "helper" in text
        assert "(bot)" in text

    def test_format_message_removed(self) -> None:
        from meadows.tui.app import CursesApp

        config = TUIConfig(theme="dark")
        app = CursesApp(config)
        app._stdscr = None

        data = {
            "id": "msg-3",
            "group_id": "general",
            "type": "user",
            "user_id": "user-alice",
            "username": "alice",
            "content": "gone",
            "timestamp": "2025-01-01T12:00:00.000000",
            "removed": True,
        }
        lines = app._format_message(data, 80, "")
        text = " ".join(t for t, _ in lines)
        assert "removed" in text

    def test_format_message_quoted(self) -> None:
        from meadows.tui.app import CursesApp

        config = TUIConfig(theme="dark")
        app = CursesApp(config)
        app._stdscr = None

        data = {
            "id": "msg-4",
            "group_id": "general",
            "type": "user",
            "user_id": "user-alice",
            "username": "alice",
            "content": "my reply",
            "timestamp": "2025-01-01T12:00:00.000000",
            "quoted_message": {
                "author": "bob",
                "content": "original message",
            },
        }
        lines = app._format_message(data, 80, "")
        text = " ".join(t for t, _ in lines)
        assert "re: bob" in text

    def test_handle_authenticated_sets_groups(self) -> None:
        from meadows.tui.app import CursesApp

        config = TUIConfig(theme="dark")
        app = CursesApp(config)

        data = {
            "user_id": "user-alice",
            "username": "alice",
            "groups": [
                {"id": "general", "name": "general"},
                {"id": "random", "name": "random"},
            ],
            "bots": [{"name": "echo"}],
        }
        app._handle_authenticated(data)
        assert app._screen == "chat"
        assert "general" in app._groups
        assert "random" in app._groups
        assert app._current_group == "general"
        assert len(app._bots) == 1

    def test_handle_message_adds_to_current_group(self) -> None:
        from meadows.tui.app import CursesApp

        config = TUIConfig(theme="dark")
        app = CursesApp(config)
        app._current_group = "general"

        data = {
            "id": "m1", "group_id": "general", "content": "hi",
            "username": "alice", "timestamp": "", "type": "user",
        }
        app._handle_message(data)
        assert len(app._messages) == 1

    def test_handle_message_ignores_other_group(self) -> None:
        from meadows.tui.app import CursesApp

        config = TUIConfig(theme="dark")
        app = CursesApp(config)
        app._current_group = "general"

        data = {"id": "m1", "group_id": "random", "content": "hi", "username": "alice", "timestamp": "", "type": "user"}
        app._handle_message(data)
        assert len(app._messages) == 0

    def test_switch_group_clears_messages(self) -> None:
        from meadows.tui.app import CursesApp

        config = TUIConfig(theme="dark")
        app = CursesApp(config)
        app._current_group = "general"
        app._messages = [{"id": "m1"}]
        app._run_async = lambda _coro: None

        app._switch_group("random")
        assert app._current_group == "random"
        assert len(app._messages) == 0


def test_protocol_import_restricted() -> None:
    import meadows.tui
    assert hasattr(meadows.tui, "EventName")
    assert not hasattr(meadows.tui, "Message")
    assert not hasattr(meadows.tui, "JWTClaims")


def test_namespace_package_structure() -> None:
    import meadows
    assert not hasattr(meadows, "__file__") or meadows.__file__ is None
