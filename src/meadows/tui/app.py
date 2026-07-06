"""MEADOWS TUI Application — main Textual App."""

from __future__ import annotations

import asyncio
import logging
import os
import signal
import sys
import time
from typing import ClassVar

from textual.app import App
from textual.binding import Binding

from meadows.tui.config import TUIConfig
from meadows.tui.themes import get_theme
from meadows.tui.client_bridge import (
    ClientBridge,
    ConnectionFailedError,
    Authenticated,
    AuthFailed,
    ServerError,
    ChatMessage,
    UserTyping,
    JoinedGroup,
    LeftGroup,
    UserJoined,
    UserLeft,
    MembersUpdated,
    GroupCreated,
    GroupDeleted,
    GroupList,
    BotList,
    MessageRemoved,
    ReactionAdded,
    ReactionToggled,
)
from meadows.tui.screens.auth_screen import AuthScreen, AuthRequest
from meadows.tui.screens.chat_screen import ChatScreen
from meadows.tui.util import ignore_no_match

logger = logging.getLogger(__name__)


class MeadowsTUIApp(App):
    """MEADOWS terminal chat client.

    Keybindings:
        Ctrl+t — toggle dark/light theme
        Ctrl+b — toggle sidebar
        Ctrl+q / Ctrl+c — quit
        Ctrl+n — focus input
    """

    CSS = """
    Screen {
        background: $background;
    }

    .auth-container {
        align: center middle;
        padding: 2 4;
        width: 60;
        height: auto;
    }

    .auth-title {
        text-align: center;
        text-style: bold;
        padding: 1;
    }

    .auth-label {
        padding: 0 1;
        text-style: bold;
        margin-top: 1;
    }

    .auth-input {
        margin: 0 1 1 1;
        width: 100%;
    }

    .auth-divider {
        text-align: center;
        color: $foreground;
        padding: 1;
    }

    .auth-error {
        color: $error;
        text-align: center;
        padding: 1;
    }

    .main-layout {
        height: 1fr;
    }

    #sidebar {
        width: 24;
        height: 100%;
    }

    .sidebar {
        width: 100%;
        height: 100%;
        background: $surface;
        overflow-y: auto;
        padding: 0 1;
    }

    .sidebar-header {
        text-style: bold;
        color: $accent;
        padding: 1 0 0 0;
        border-bottom: solid $primary;
        margin-bottom: 1;
    }

    .groups-list, .users-list, .bots-list {
        height: auto;
        max-height: 10;
        margin-bottom: 1;
    }

    .group-item {
        padding: 0 1;
        color: $foreground;
    }

    .group-item:hover {
        background: $boost;
    }

    .group-item.active-group {
        color: $primary;
        text-style: bold;
    }

    .new-group-input {
        margin: 0 0 1 0;
    }

    .user-item, .bot-item {
        padding: 0 1;
        color: $foreground;
    }

    .chat-area {
        height: 100%;
        width: 1fr;
    }

    .group-header {
        padding: 0 2;
        height: 1;
        background: $boost;
        border-bottom: solid $primary;
        color: $foreground;
    }

    .message-list {
        height: 1fr;
        padding: 0 1;
        overflow-y: scroll;
    }

    .message-list > Static {
        padding: 0 1;
    }

    .quoted-preview {
        padding: 0 2;
        color: $foreground;
        height: auto;
        background: $boost;
        border-top: solid $primary;
    }

    .input-row {
        height: auto;
        padding: 0 1 1 1;
    }

    .input-row > Input {
        width: 1fr;
    }

    .input-row > Button {
        width: 10;
        margin-left: 1;
    }

    #chat-input {
        min-height: 1;
    }

    .spacer {
        height: 1;
    }

    .emoji-btn {
        width: 4;
        height: 3;
        margin: 0;
    }
    """

    BINDINGS: ClassVar[list[Binding]] = [
        Binding("ctrl+t", "toggle_theme", "Toggle theme"),
        Binding("ctrl+b", "toggle_sidebar", "Toggle sidebar"),
        Binding("ctrl+q", "quit", "Quit"),
        Binding("ctrl+c", "quit", "Quit"),
        Binding("ctrl+n", "focus_input", "Focus input"),
        Binding("ctrl+g", "focus_groups", "Focus groups"),
    ]

    def __init__(self, config: TUIConfig) -> None:
        super().__init__()
        self._config = config
        self._bridge = ClientBridge(self, config.server_url)
        self._last_sigint: float = 0.0

        signal.signal(signal.SIGINT, self._handle_sigint)

        theme_name = config.theme
        if theme_name == "auto":
            term = os.environ.get("COLORFGBG", "")
            theme_name = "light" if "15;0" in term else "dark"
        self._theme_name = theme_name

    TERM_RESET = "\033[?1049l\033[?25h\033[?1000l\033[?1003l\033[?1015l\033[?1006l"

    def _restore_terminal(self) -> None:
        sys.stderr.write(self.TERM_RESET)
        sys.stderr.flush()

    def _handle_sigint(self, _sig: int, _frame) -> None:
        now = time.monotonic()
        if now - self._last_sigint < 1.0:
            self._restore_terminal()
            os._exit(1)
        self._last_sigint = now
        self.call_from_thread(self.action_quit)

    def get_theme_colors(self) -> dict[str, str]:
        return get_theme(self._theme_name)

    def on_mount(self) -> None:
        if self._config.token:
            logger.info("token provided via config, auto-connecting")
            self.post_message(AuthRequest(token=self._config.token))
        elif self._config.jwt_secret and self._config.username:
            logger.info("jwt_secret + username provided, auto-connecting")
            self.post_message(AuthRequest(username=self._config.username, secret=self._config.jwt_secret))
        self.push_screen(AuthScreen(self._config.server_url, theme=self._theme_name))

    def on_auth_request(self, event: AuthRequest) -> None:
        async def _connect() -> None:
            try:
                if event.token:
                    logger.info("auth request: connecting with token")
                    await self._bridge.connect_with_token(event.token)
                elif event.username and event.secret:
                    logger.info("auth request: connecting with secret as %s", event.username)
                    await self._bridge.connect_with_secret(event.username, event.secret)
                else:
                    return

                current = self.screen
                if isinstance(current, AuthScreen):
                    logger.info("auth succeeded, switching to chat screen")
                    self.switch_screen(
                        ChatScreen(
                            bridge=self._bridge,
                            server_url=self._config.server_url,
                            theme=self._theme_name,
                            system_name=self._config.system_name,
                        )
                    )
            except ConnectionFailedError as exc:
                logger.error("connection failed: %s", exc)
                current = self.screen
                if isinstance(current, AuthScreen):
                    current.show_error(str(exc))
            except Exception as exc:
                logger.exception("unexpected error during connect")
                current = self.screen
                if isinstance(current, AuthScreen):
                    current.show_error(str(exc))

        self._connect_task = asyncio.create_task(_connect())

    async def on_auth_failed(self, event: AuthFailed) -> None:
        error = event.data.get("error", str(event.data))
        logger.error("auth_failed from server: %s", error)
        current = self.screen
        if isinstance(current, AuthScreen):
            current.show_error(f"Auth failed: {error}")

    async def on_server_error(self, event: ServerError) -> None:
        logger.warning("server error event: %s", event.data)

    async def _forward_to_chat(self, _cls: type, method: str, event) -> None:
        screen = self.screen
        if isinstance(screen, ChatScreen):
            handler = getattr(screen, method, None)
            if handler:
                handler(event) if not hasattr(handler, "__await__") else await handler(event)

    async def on_authenticated(self, event: Authenticated) -> None:
        await self._forward_to_chat(Authenticated, "handle_authenticated", event)

    async def on_chat_message(self, event: ChatMessage) -> None:
        await self._forward_to_chat(ChatMessage, "handle_chat_message", event)

    async def on_user_typing(self, event: UserTyping) -> None:
        await self._forward_to_chat(UserTyping, "handle_user_typing", event)

    async def on_joined_group(self, event: JoinedGroup) -> None:
        await self._forward_to_chat(JoinedGroup, "handle_joined_group", event)

    async def on_left_group(self, event: LeftGroup) -> None:
        await self._forward_to_chat(LeftGroup, "handle_left_group", event)

    async def on_user_joined(self, event: UserJoined) -> None:
        await self._forward_to_chat(UserJoined, "handle_user_joined", event)

    async def on_user_left(self, event: UserLeft) -> None:
        await self._forward_to_chat(UserLeft, "handle_user_left", event)

    async def on_members_updated(self, event: MembersUpdated) -> None:
        await self._forward_to_chat(MembersUpdated, "handle_members_updated", event)

    async def on_group_created(self, event: GroupCreated) -> None:
        await self._forward_to_chat(GroupCreated, "handle_group_created", event)

    async def on_group_deleted(self, event: GroupDeleted) -> None:
        await self._forward_to_chat(GroupDeleted, "handle_group_deleted", event)

    async def on_group_list(self, event: GroupList) -> None:
        pass

    async def on_bot_list(self, event: BotList) -> None:
        await self._forward_to_chat(BotList, "handle_bot_list", event)

    async def on_message_removed(self, event: MessageRemoved) -> None:
        await self._forward_to_chat(MessageRemoved, "handle_message_removed", event)

    async def on_reaction_added(self, event: ReactionAdded) -> None:
        await self._forward_to_chat(ReactionAdded, "handle_reaction_added", event)

    async def on_reaction_toggled(self, event: ReactionToggled) -> None:
        await self._forward_to_chat(ReactionToggled, "handle_reaction_toggled", event)

    def action_toggle_theme(self) -> None:
        self._theme_name = "light" if self._theme_name == "dark" else "dark"
        screen = self.screen
        if isinstance(screen, ChatScreen):
            screen.theme = self._theme_name

    def action_toggle_sidebar(self) -> None:
        screen = self.screen
        if isinstance(screen, ChatScreen):
            screen.toggle_sidebar()

    def action_focus_input(self) -> None:
        screen = self.screen
        if isinstance(screen, ChatScreen):
            self._focus_widget(screen, "#chat-input")

    def action_focus_groups(self) -> None:
        screen = self.screen
        if isinstance(screen, ChatScreen):
            self._focus_widget(screen, "#groups-list")

    @ignore_no_match
    def _focus_widget(self, screen: ChatScreen, selector: str) -> None:
        screen.query_one(selector).focus()

    def action_quit(self) -> None:
        now = time.monotonic()
        if now - self._last_sigint < 1.0:
            self._restore_terminal()
            os._exit(1)
        self._last_sigint = now
        self._quit_task = asyncio.create_task(self._bridge.disconnect())
        super().action_quit()
