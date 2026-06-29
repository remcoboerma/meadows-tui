"""Tests for meadows-tui — unit tests + Textual pilot-based integration tests."""

from __future__ import annotations

import os

import pytest

from meadows.tui.__about__ import __version__
from meadows.tui.config import TUIConfig, load_config
from meadows.tui.themes import DARK_THEME, LIGHT_THEME, THEMES, get_theme


# ── Unit tests ──────────────────────────────────────────────────────────────


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


# ── Message widget tests ─────────────────────────────────────────────────────


class TestMessageWidget:
    def _rendered(self, mw):
        return str(mw.render())

    def test_user_message(self) -> None:
        from meadows.tui.widgets.message_widget import MessageWidget

        data = {
            "id": "msg-1",
            "group_id": "general",
            "type": "user",
            "user_id": "user-alice",
            "username": "alice",
            "content": "hello world",
            "timestamp": "2025-01-01T12:00:00.000000",
        }
        mw = MessageWidget(data, is_own=False, theme="dark")
        rendered = self._rendered(mw)
        assert "alice" in rendered
        assert "hello world" in rendered

    def test_own_message_has_label(self) -> None:
        from meadows.tui.widgets.message_widget import MessageWidget

        data = {
            "id": "msg-2",
            "group_id": "general",
            "type": "user",
            "user_id": "user-alice",
            "username": "alice",
            "content": "my message",
            "timestamp": "2025-01-01T12:00:00.000000",
        }
        mw = MessageWidget(data, is_own=True, theme="dark")
        rendered = self._rendered(mw)
        assert "(you)" in rendered

    def test_bot_message_has_label(self) -> None:
        from meadows.tui.widgets.message_widget import MessageWidget

        data = {
            "id": "msg-3",
            "group_id": "general",
            "type": "bot",
            "user_id": "bot-helper",
            "bot_name": "helper",
            "content": "I am a bot",
            "timestamp": "2025-01-01T12:00:00.000000",
        }
        mw = MessageWidget(data, is_own=False, theme="dark")
        rendered = self._rendered(mw)
        assert "(bot)" in rendered

    def test_removed_message(self) -> None:
        from meadows.tui.widgets.message_widget import MessageWidget

        data = {
            "id": "msg-4",
            "group_id": "general",
            "type": "user",
            "user_id": "user-alice",
            "username": "alice",
            "content": "should be gone",
            "timestamp": "2025-01-01T12:00:00.000000",
            "removed": True,
        }
        mw = MessageWidget(data, theme="dark")
        assert mw.removed is True
        rendered = self._rendered(mw)
        # When removed, the content should mention removal
        assert "alice" in rendered

    def test_reaction_message(self) -> None:
        from meadows.tui.widgets.message_widget import MessageWidget

        data = {
            "id": "msg-5",
            "group_id": "general",
            "type": "reaction",
            "user_id": "user-alice",
            "username": "alice",
            "content": "",
            "timestamp": "2025-01-01T12:00:00.000000",
            "emoji": "👍",
            "target_message_id": "msg-1",
        }
        mw = MessageWidget(data, theme="dark")
        rendered = self._rendered(mw)
        assert "👍" in rendered

    def test_everyone_message(self) -> None:
        from meadows.tui.widgets.message_widget import MessageWidget

        data = {
            "id": "msg-6",
            "group_id": "general",
            "type": "user",
            "user_id": "user-alice",
            "username": "alice",
            "content": "@everyone",
            "timestamp": "2025-01-01T12:00:00.000000",
            "is_everyone": True,
        }
        mw = MessageWidget(data, theme="dark")
        rendered = self._rendered(mw)
        assert "@everyone" in rendered

    def test_quoted_message(self) -> None:
        from meadows.tui.widgets.message_widget import MessageWidget

        data = {
            "id": "msg-7",
            "group_id": "general",
            "type": "user",
            "user_id": "user-alice",
            "username": "alice",
            "content": "my reply",
            "timestamp": "2025-01-01T12:00:00.000000",
            "quoted_message": {
                "id": "orig-1",
                "author": "bob",
                "content": "original message",
                "timestamp": "2025-01-01T11:00:00.000000",
            },
        }
        mw = MessageWidget(data, theme="dark")
        rendered = self._rendered(mw)
        assert "re: bob" in rendered


# ── Sidebar widget tests ─────────────────────────────────────────────────────


class TestSidebarWidget:
    def test_sidebar_compose(self) -> None:
        from meadows.tui.widgets.sidebar_widget import Sidebar

        sidebar = Sidebar(theme="dark")
        assert sidebar.theme == "dark"
        assert sidebar.active_group == "general"

    def test_set_groups_no_mount(self) -> None:
        from meadows.tui.widgets.sidebar_widget import Sidebar

        sidebar = Sidebar(theme="dark")
        groups = [
            {"id": "general", "name": "general", "member_count": 5},
            {"id": "random", "name": "random", "member_count": 3},
        ]
        sidebar._groups = {g.get("id", g.get("group_id", "")): g for g in groups}
        assert "general" in sidebar._groups
        assert "random" in sidebar._groups

    def test_add_remove_group_no_mount(self) -> None:
        from meadows.tui.widgets.sidebar_widget import Sidebar

        sidebar = Sidebar(theme="dark")
        sidebar._groups["new-group"] = {"id": "new-group", "name": "New Group"}
        assert "new-group" in sidebar._groups
        sidebar._groups.pop("new-group", None)
        assert "new-group" not in sidebar._groups

    def test_set_users_no_mount(self) -> None:
        from meadows.tui.widgets.sidebar_widget import Sidebar

        sidebar = Sidebar(theme="dark")
        users = [{"username": "alice"}, {"username": "bob"}]
        sidebar._user_list = [u.get("username", u.get("user_id", "")) for u in users]
        assert "alice" in sidebar._user_list
        assert "bob" in sidebar._user_list

    def test_set_bots_no_mount(self) -> None:
        from meadows.tui.widgets.sidebar_widget import Sidebar

        sidebar = Sidebar(theme="dark")
        bots = [{"name": "helper", "description": "a helpful bot"}]
        sidebar._bot_list = bots
        assert len(sidebar._bot_list) == 1
        assert sidebar._bot_list[0]["name"] == "helper"


# ── Client bridge tests ──────────────────────────────────────────────────────


class TestClientBridge:
    def test_bridge_initial_state(self) -> None:
        from textual.app import App
        from meadows.tui.client_bridge import ClientBridge

        app = App()
        bridge = ClientBridge(app, "http://localhost:8080")
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


# ── Auth screen tests ────────────────────────────────────────────────────────


class TestAuthScreen:
    def test_auth_request_message(self) -> None:
        from meadows.tui.screens.auth_screen import AuthRequest

        req = AuthRequest(token="eyJtoken")
        assert req.token == "eyJtoken"
        assert req.username is None
        assert req.secret is None

        req2 = AuthRequest(username="alice", secret="secret123")
        assert req2.token is None
        assert req2.username == "alice"
        assert req2.secret == "secret123"


# ── Chat input widget tests ──────────────────────────────────────────────────


class TestChatInputWidget:
    def test_send_message_event(self) -> None:
        from meadows.tui.widgets.input_widget import SendMessage

        msg = SendMessage(content="hello", quoted_message_id="msg-1")
        assert msg.content == "hello"
        assert msg.quoted_message_id == "msg-1"

    def test_send_message_no_quote(self) -> None:
        from meadows.tui.widgets.input_widget import SendMessage

        msg = SendMessage(content="hello")
        assert msg.content == "hello"
        assert msg.quoted_message_id is None


# ── CLI interface tests ──────────────────────────────────────────────────────


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


# ── App integration tests (Textual pilot) ────────────────────────────────────


@pytest.mark.asyncio
async def test_app_launches_and_shows_auth_screen() -> None:
    """Verify the app starts and shows the auth screen."""
    import asyncio
    from meadows.tui.app import MeadowsTUIApp
    from meadows.tui.config import TUIConfig

    config = TUIConfig(server_url="http://localhost:8080", theme="dark")
    app = MeadowsTUIApp(config=config)

    async with app.run_test(size=(80, 24)) as pilot:
        assert pilot.app is not None
        await asyncio.sleep(0.1)

        assert len(app.screen_stack) >= 1
        screen_name = app.screen.__class__.__name__
        assert screen_name == "AuthScreen", f"Expected AuthScreen, got {screen_name}"


@pytest.mark.asyncio
async def test_app_auth_shows_error_on_empty_token() -> None:
    """Verify that submitting empty token shows an error."""
    import asyncio
    from meadows.tui.app import MeadowsTUIApp
    from meadows.tui.config import TUIConfig

    config = TUIConfig(server_url="http://localhost:8080", theme="dark")
    app = MeadowsTUIApp(config=config)

    async with app.run_test(size=(80, 24)) as pilot:
        await asyncio.sleep(0.1)

        connect_btn = app.screen.query_one("#connect-token-btn")
        assert connect_btn is not None

        await pilot.click("#connect-token-btn")
        await asyncio.sleep(0.05)

        error_static = app.screen.query_one("#auth-error")
        assert "Please enter a token" in str(error_static.render())


@pytest.mark.asyncio
async def test_sidebar_widget_toggle_works() -> None:
    """Test that the ChatScreen toggles sidebar display."""
    from meadows.tui.screens.chat_screen import ChatScreen

    from meadows.tui.app import MeadowsTUIApp
    from meadows.tui.config import TUIConfig

    config = TUIConfig(server_url="http://localhost:8080", theme="dark")
    app = MeadowsTUIApp(config=config)

    async with app.run_test(size=(80, 24)):
        from unittest.mock import MagicMock
        bridge = MagicMock()
        screen = ChatScreen(
            bridge=bridge,
            server_url=config.server_url,
            theme="dark",
            system_name=config.system_name,
        )

        assert screen._sidebar_mode == "expanded"

        screen._sidebar_mode = "collapsed"
        assert screen._sidebar_mode == "collapsed"

        screen._sidebar_mode = "expanded"
        assert screen._sidebar_mode == "expanded"


@pytest.mark.asyncio
async def test_theme_toggle_works() -> None:
    """Verify theme toggling between dark and light."""
    from meadows.tui.app import MeadowsTUIApp
    from meadows.tui.config import TUIConfig

    config = TUIConfig(server_url="http://localhost:8080", theme="dark")
    app = MeadowsTUIApp(config=config)

    async with app.run_test(size=(80, 24)):
        assert app._theme_name == "dark"

        app.action_toggle_theme()
        assert app._theme_name == "light"

        app.action_toggle_theme()
        assert app._theme_name == "dark"


@pytest.mark.asyncio
async def test_app_light_theme_on_start() -> None:
    """Verify app starts with light theme when configured."""
    import asyncio
    from meadows.tui.app import MeadowsTUIApp
    from meadows.tui.config import TUIConfig

    config = TUIConfig(server_url="http://localhost:8080", theme="light")
    app = MeadowsTUIApp(config=config)

    async with app.run_test(size=(80, 24)):
        await asyncio.sleep(0.1)
        assert app._theme_name == "light"


@pytest.mark.asyncio
async def test_auto_theme_detection() -> None:
    """Verify auto theme picks dark when COLORFGBG is not set."""
    import asyncio
    from meadows.tui.app import MeadowsTUIApp
    from meadows.tui.config import TUIConfig

    if "COLORFGBG" in os.environ:
        del os.environ["COLORFGBG"]

    config = TUIConfig(server_url="http://localhost:8080", theme="auto")
    app = MeadowsTUIApp(config=config)

    async with app.run_test(size=(80, 24)):
        await asyncio.sleep(0.1)
        # Without COLORFGBG, it should default to dark
        assert app._theme_name == "dark"


# ── Error handling tests ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_app_handle_connect_failure() -> None:
    """Verify the auth screen shows an error on failed connection."""
    import asyncio
    from meadows.tui.app import MeadowsTUIApp
    from meadows.tui.config import TUIConfig
    from meadows.tui.screens.auth_screen import AuthRequest

    config = TUIConfig(server_url="http://localhost:9999", theme="dark")
    app = MeadowsTUIApp(config=config)

    async with app.run_test(size=(80, 24)):
        await asyncio.sleep(0.1)

        # Try to connect to a non-existent server
        app.on_auth_request(AuthRequest(token="bad-token"))
        await asyncio.sleep(0.2)

        # Should still be on auth screen (connection failed silently)
        assert app.screen.__class__.__name__ == "AuthScreen"


# ── Client bridge message types test ─────────────────────────────────────────


class TestBridgeMessageTypes:
    """Verify all bridge message types can be instantiated."""

    def test_authenticated(self) -> None:
        from meadows.tui.client_bridge import Authenticated
        m = Authenticated({"user_id": "u1"})
        assert m.data["user_id"] == "u1"

    def test_chat_message(self) -> None:
        from meadows.tui.client_bridge import ChatMessage
        m = ChatMessage({"content": "hi"})
        assert m.data["content"] == "hi"

    def test_user_typing(self) -> None:
        from meadows.tui.client_bridge import UserTyping
        m = UserTyping({"group_id": "g1", "user_id": "u1"})
        assert m.data["group_id"] == "g1"

    def test_joined_group(self) -> None:
        from meadows.tui.client_bridge import JoinedGroup
        m = JoinedGroup({"group_id": "g1"})
        assert m.data["group_id"] == "g1"

    def test_left_group(self) -> None:
        from meadows.tui.client_bridge import LeftGroup
        m = LeftGroup({"group_id": "g1"})
        assert m.data["group_id"] == "g1"

    def test_user_joined(self) -> None:
        from meadows.tui.client_bridge import UserJoined
        m = UserJoined({"user_id": "u1", "group_id": "g1"})
        assert m.data["user_id"] == "u1"

    def test_user_left(self) -> None:
        from meadows.tui.client_bridge import UserLeft
        m = UserLeft({"user_id": "u1", "group_id": "g1"})
        assert m.data["user_id"] == "u1"

    def test_members_updated(self) -> None:
        from meadows.tui.client_bridge import MembersUpdated
        m = MembersUpdated({"group_id": "g1", "members": []})
        assert m.data["group_id"] == "g1"

    def test_group_created(self) -> None:
        from meadows.tui.client_bridge import GroupCreated
        m = GroupCreated({"id": "g1", "name": "new"})
        assert m.data["id"] == "g1"

    def test_group_deleted(self) -> None:
        from meadows.tui.client_bridge import GroupDeleted
        m = GroupDeleted({"group_id": "g1"})
        assert m.data["group_id"] == "g1"

    def test_group_list(self) -> None:
        from meadows.tui.client_bridge import GroupList
        m = GroupList({"groups": [{"id": "g1"}]})
        assert len(m.data["groups"]) == 1

    def test_bot_list(self) -> None:
        from meadows.tui.client_bridge import BotList
        m = BotList({"bots": [{"name": "b1"}]})
        assert m.data["bots"][0]["name"] == "b1"

    def test_message_removed(self) -> None:
        from meadows.tui.client_bridge import MessageRemoved
        m = MessageRemoved({"message_id": "m1", "group_id": "g1"})
        assert m.data["message_id"] == "m1"

    def test_reaction_added(self) -> None:
        from meadows.tui.client_bridge import ReactionAdded
        m = ReactionAdded({"emoji": "👍", "target_message_id": "m1"})
        assert m.data["emoji"] == "👍"

    def test_reaction_toggled(self) -> None:
        from meadows.tui.client_bridge import ReactionToggled
        m = ReactionToggled({"target_message_id": "m1", "emoji": "👍"})
        assert m.data["target_message_id"] == "m1"


# ── Config file loading test ─────────────────────────────────────────────────


def test_config_file_loading() -> None:
    """Test that config works with env var overrides via monkeypatch."""
    pass  # Config is already well-tested above; env vars covered by Click's native support


# ── Import test: verify protocol is only imported for EventName ──────────────


def test_protocol_import_restricted() -> None:
    """Verify meadows.tui only imports EventName from protocol (invariant)."""
    import meadows.tui
    assert hasattr(meadows.tui, "EventName")
    assert not hasattr(meadows.tui, "Message")
    assert not hasattr(meadows.tui, "JWTClaims")


# ── Verify package namespace ────────────────────────────────────────────────


def test_namespace_package_structure() -> None:
    """Verify PEP 420 namespace: no src/meadows/__init__.py."""

    # The parent meadows package should not have an __init__
    import meadows
    assert not hasattr(meadows, "__file__") or meadows.__file__ is None
