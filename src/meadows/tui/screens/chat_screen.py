"""Main chat screen for meadows-tui."""

from __future__ import annotations

import asyncio
from collections import defaultdict
from typing import Any

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.reactive import reactive
from textual.screen import Screen
from textual.widgets import Static, Header, Footer

from meadows.tui.client_bridge import (
    ClientBridge,
    Authenticated,
    ChatMessage,
    UserTyping,
    JoinedGroup,
    LeftGroup,
    UserJoined,
    UserLeft,
    MembersUpdated,
    GroupCreated,
    GroupDeleted,
    BotList,
    MessageRemoved,
    ReactionAdded,
    ReactionToggled,
)
from meadows.tui.widgets.message_widget import MessageWidget
from meadows.tui.widgets.input_widget import ChatInput, SendMessage
from meadows.tui.widgets.sidebar_widget import Sidebar, GroupSelected, CreateGroup, LeaveGroup, DeleteGroup
from meadows.tui.themes import get_theme
from meadows.tui.util import ignore_no_match


class ChatScreen(Screen):
    theme: reactive[str] = reactive("dark")
    current_group: reactive[str] = reactive("general")

    def __init__(
        self, bridge: ClientBridge, server_url: str, theme: str = "dark", system_name: str = "MEADOWS Chat"
    ) -> None:
        super().__init__()
        self._bridge = bridge
        self._server_url = server_url
        self.theme = theme
        self._system_name = system_name
        self._messages: list[dict[str, Any]] = []
        self._message_widgets: dict[str, Static] = {}
        self._current_group_messages: list[Static] = []
        self._typing_users: dict[str, list[str]] = defaultdict(list)
        self._sidebar_mode = "expanded"

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Header(show_clock=True)
            with Horizontal(classes="main-layout"):
                yield Sidebar(theme=self.theme, id="sidebar")
                with Vertical(classes="chat-area", id="chat-area"):
                    yield Static(id="group-header", classes="group-header")
                    with VerticalScroll(id="message-list", classes="message-list"):
                        yield Static("Connecting...", id="loading-msg")
                    yield ChatInput(theme=self.theme, id="chat-input-area")
            yield Footer()

    def on_mount(self) -> None:
        self._apply_theme()

    @ignore_no_match
    def _apply_theme(self) -> None:
        screen = self.screen
        mlist = self.query_one("#message-list", VerticalScroll)
        header = self.query_one(Header)
        footer = self.query_one(Footer)
        colors = get_theme(self.theme)
        border = colors["border"]

        screen.styles.background = colors["background"]
        mlist.styles.background = colors["surface"]
        header.styles.background = colors["surface-alt"]
        header.styles.color = colors["text"]
        header.styles.border_bottom = ("solid", border)
        footer.styles.background = colors["surface-alt"]
        footer.styles.color = colors["text"]

    def watch_theme(self, _old: str, _new: str) -> None:
        self._apply_theme()
        self.refresh()

    def handle_authenticated(self, event: Authenticated) -> None:
        data = event.data
        sidebar = self.query_one(Sidebar)
        sidebar.set_groups(data.get("groups", []))

        bots = data.get("bots", [])
        sidebar.set_bots(bots)

        gh = self.query_one("#group-header", Static)
        gh.update(f"  [{data.get('username', '')}] — connected")

        self._join_first_group(data.get("groups", []))
        loading = self.query_one("#loading-msg", Static)
        loading.remove()

    def _join_first_group(self, groups: list[dict[str, Any]]) -> None:
        for g in groups:
            gid = g.get("id", g.get("group_id", ""))
            if gid == "general":
                self.current_group = "general"
                sidebar = self.query_one(Sidebar)
                sidebar.active_group = "general"
                self._switch_group(gid)
                break

    def _switch_group(self, group_id: str) -> None:
        self.current_group = group_id
        mlist = self.query_one("#message-list", VerticalScroll)
        mlist.remove_children()
        self._current_group_messages = []

        gh = self.query_one("#group-header", Static)
        colors = get_theme(self.theme)
        gh.update(f"  [{colors['primary']}]#{group_id}[/]")

        loading = Static(f"Joined #{group_id}", id="loading-msg")
        mlist.mount(loading)

    def _add_message(self, data: dict[str, Any]) -> None:
        msg_group = data.get("group_id", "")
        if msg_group != self.current_group:
            return

        is_own = False
        if self._bridge.auth_data:
            aid = self._bridge.auth_data.user_id
            is_own = data.get("user_id", "") == aid

        mw = MessageWidget(data, is_own=is_own, theme=self.theme)

        mlist = self.query_one("#message-list", VerticalScroll)
        mlist.mount(mw)
        self._current_group_messages.append(mw)
        self._message_widgets[data.get("id", "")] = mw

        mlist.scroll_end(animate=False)

        loading = mlist.query("#loading-msg")
        if loading:
            loading[0].remove()

    def _remove_message(self, data: dict[str, Any]) -> None:
        mid = data.get("message_id", "")
        widget = self._message_widgets.get(mid)
        if widget:
            widget.removed = True
            widget._update_content()

    def handle_chat_message(self, event: ChatMessage) -> None:
        self._add_message(event.data)

    def handle_user_typing(self, event: UserTyping) -> None:
        data = event.data
        gid = data.get("group_id", "")
        if gid != self.current_group:
            return
        uid = data.get("user_id", "")
        if uid not in self._typing_users[gid]:
            self._typing_users[gid].append(uid)
        self._update_typing_indicator()

    def _update_typing_indicator(self) -> None:
        users = self._typing_users.get(self.current_group, [])
        gh = self.query_one("#group-header", Static)
        colors = get_theme(self.theme)
        typing_text = ""
        if users:
            names = ", ".join(users[:3])
            typing_text = f"  [{colors['text-muted']}]{names} typing...[/]"
        gh.update(f"  [{colors['primary']}]#{self.current_group}[/]{typing_text}")

    def _send_message(self, event: SendMessage) -> None:
        self._send_task = asyncio.ensure_future(
            self._bridge.send_message(
                content=event.content,
                group_id=self.current_group,
                quoted_message_id=event.quoted_message_id,
            )
        )

    def handle_group_selected(self, event: GroupSelected) -> None:
        self._switch_group(event.group_id)

    def handle_create_group(self, event: CreateGroup) -> None:
        asyncio.ensure_future(self._bridge.create_group(event.group_id, name=event.name))  # noqa: RUF006

    def handle_leave_group(self, event: LeaveGroup) -> None:
        asyncio.ensure_future(self._bridge.leave_group(event.group_id))  # noqa: RUF006

    def handle_delete_group(self, event: DeleteGroup) -> None:
        asyncio.ensure_future(self._bridge.delete_group(event.group_id))  # noqa: RUF006

    def handle_joined_group(self, event: JoinedGroup) -> None:
        data = event.data
        self._switch_group(data.get("group_id", ""))
        sidebar = self.query_one(Sidebar)
        if "members" in data:
            sidebar.set_users(data["members"])
        if "thread" in data:
            thread = data["thread"]
            for msg in thread:
                self._add_message(msg)

    def handle_left_group(self, event: LeftGroup) -> None:
        gid = event.data.get("group_id", "")
        sidebar = self.query_one(Sidebar)
        sidebar.remove_group(gid)

    def handle_user_joined(self, event: UserJoined) -> None:
        pass

    def handle_user_left(self, event: UserLeft) -> None:
        pass

    def handle_members_updated(self, event: MembersUpdated) -> None:
        data = event.data
        sidebar = self.query_one(Sidebar)
        sidebar.set_users(data.get("members", []))

    def handle_group_created(self, event: GroupCreated) -> None:
        sidebar = self.query_one(Sidebar)
        sidebar.add_group(event.data)

    def handle_group_deleted(self, event: GroupDeleted) -> None:
        gid = event.data.get("group_id", "")
        sidebar = self.query_one(Sidebar)
        sidebar.remove_group(gid)

    def handle_bot_list(self, event: BotList) -> None:
        sidebar = self.query_one(Sidebar)
        sidebar.set_bots(event.data.get("bots", []))

    def handle_message_removed(self, event: MessageRemoved) -> None:
        self._remove_message(event.data)

    def handle_reaction_added(self, event: ReactionAdded) -> None:
        pass

    def handle_reaction_toggled(self, event: ReactionToggled) -> None:
        pass

    def on_send_message(self, event: SendMessage) -> None:
        self._send_message(event)

    def on_group_selected(self, event: GroupSelected) -> None:
        self.handle_group_selected(event)

    def on_create_group(self, event: CreateGroup) -> None:
        self.handle_create_group(event)

    def on_leave_group(self, event: LeaveGroup) -> None:
        self.handle_leave_group(event)

    def on_delete_group(self, event: DeleteGroup) -> None:
        self.handle_delete_group(event)

    def toggle_theme(self) -> None:
        self.theme = "light" if self.theme == "dark" else "dark"

    def toggle_sidebar(self) -> None:
        sidebar = self.query_one("#sidebar")
        if self._sidebar_mode == "expanded":
            sidebar.display = False
            self._sidebar_mode = "collapsed"
        else:
            sidebar.display = True
            self._sidebar_mode = "expanded"
