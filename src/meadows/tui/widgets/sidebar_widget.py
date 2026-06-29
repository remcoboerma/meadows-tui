"""Sidebar widget showing groups, users, and bots."""

from __future__ import annotations

from typing import Any

from textual.app import ComposeResult
from textual.containers import Vertical, VerticalScroll
from textual.message import Message
from textual.reactive import reactive
from textual.widgets import Static, Input
from textual.widget import Widget


class GroupSelected(Message):
    def __init__(self, group_id: str) -> None:
        self.group_id = group_id
        super().__init__()


class CreateGroup(Message):
    def __init__(self, group_id: str, name: str | None = None) -> None:
        self.group_id = group_id
        self.name = name
        super().__init__()


class LeaveGroup(Message):
    def __init__(self, group_id: str) -> None:
        self.group_id = group_id
        super().__init__()


class DeleteGroup(Message):
    def __init__(self, group_id: str) -> None:
        self.group_id = group_id
        super().__init__()


class Sidebar(Widget):
    theme: reactive[str] = reactive("dark")
    active_group: reactive[str] = reactive("general")

    def __init__(self, theme: str = "dark") -> None:
        super().__init__()
        self.theme = theme
        self._groups: dict[str, Any] = {}
        self._user_list: list[str] = []
        self._bot_list: list[dict[str, Any]] = []

    def compose(self) -> ComposeResult:
        with Vertical(classes="sidebar"):
            yield Static("Groups", classes="sidebar-header", id="groups-header")
            yield Input(placeholder="+ new group", id="new-group-input", classes="new-group-input")
            with VerticalScroll(id="groups-list", classes="groups-list"):
                yield Static("general", classes="group-item active-group", id="group-general")
            yield Static("Users", classes="sidebar-header", id="users-header")
            with VerticalScroll(id="users-list", classes="users-list"):
                pass
            yield Static("Bots", classes="sidebar-header", id="bots-header")
            with VerticalScroll(id="bots-list", classes="bots-list"):
                pass

    def set_groups(self, groups: list[dict[str, Any]]) -> None:
        self._groups = {g.get("id", g.get("group_id", "")): g for g in groups}
        self._refresh_groups()

    def add_group(self, group_data: dict[str, Any]) -> None:
        gid = group_data.get("id", group_data.get("group_id", ""))
        self._groups[gid] = group_data
        self._refresh_groups()

    def remove_group(self, group_id: str) -> None:
        self._groups.pop(group_id, None)
        self._refresh_groups()

    def _refresh_groups(self) -> None:
        container = self.query_one("#groups-list", VerticalScroll)
        container.remove_children()
        for gid, gdata in sorted(self._groups.items()):
            name = gdata.get("name", gid)
            count = gdata.get("member_count", "")
            label = f"{name} ({count})" if count else name
            cls = "group-item"
            if gid == self.active_group:
                cls += " active-group"
            widget = Static(label, classes=cls, id=f"group-{gid}")
            widget.data_id = gid
            container.mount(widget)

    def set_users(self, users: list[dict[str, Any]]) -> None:
        self._user_list = [u.get("username", u.get("user_id", "")) for u in users]
        self._refresh_users()

    def _refresh_users(self) -> None:
        container = self.query_one("#users-list", VerticalScroll)
        container.remove_children()
        for uname in self._user_list:
            container.mount(Static(uname, classes="user-item"))

    def set_bots(self, bots: list[dict[str, Any]]) -> None:
        self._bot_list = bots
        self._refresh_bots()

    def _refresh_bots(self) -> None:
        container = self.query_one("#bots-list", VerticalScroll)
        container.remove_children()
        for bot in self._bot_list:
            name = bot.get("name", "")
            desc = bot.get("description", "")
            label = f"{name}" + (f": {desc[:40]}..." if desc else "")
            container.mount(Static(label, classes="bot-item"))

    def on_static_clicked(self, event: Static.Clicked) -> None:
        widget = event.static
        if "group-item" in widget.classes:
            gid = getattr(widget, "data_id", None)
            if gid:
                self.active_group = gid
                self.post_message(GroupSelected(gid))

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "new-group-input":
            gid = event.value.strip().lower().replace(" ", "-")
            if gid:
                self.post_message(CreateGroup(gid))
                event.input.value = ""
