"""Message widget for rendering chat messages in the TUI."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from textual.message import Message
from textual.reactive import reactive
from textual.widgets import Static

from meadows.tui.themes import get_theme


QUICK_EMOJIS = ["👍", "❤️", "😂", "🎉", "🤔", "👀", "🔥", "💯", "🚀"]


class MessageWidget(Static):
    message_id: reactive[str] = reactive("")
    group_id: reactive[str] = reactive("")
    username: reactive[str] = reactive("")
    content: reactive[str] = reactive("")
    timestamp: reactive[str] = reactive("")
    removed: reactive[bool] = reactive(False)
    is_everyone: reactive[bool] = reactive(False)
    is_reaction: reactive[bool] = reactive(False)
    emoji: reactive[str | None] = reactive(None)
    target_message_id: reactive[str | None] = reactive(None)
    quoted_author: reactive[str | None] = reactive(None)
    quoted_content: reactive[str | None] = reactive(None)
    is_own: reactive[bool] = reactive(False)
    message_type: reactive[str] = reactive("user")

    def __init__(self, data: dict[str, Any], is_own: bool = False, theme: str = "dark") -> None:
        super().__init__("")
        self._data = data
        self._theme = theme
        self.message_id = data.get("id", "")
        self.group_id = data.get("group_id", "")
        self.username = data.get("username", data.get("bot_name", data.get("user_id", "unknown")))
        self.content = data.get("content", "")
        self.timestamp = data.get("timestamp", "")
        self.removed = data.get("removed", False)
        self.is_everyone = data.get("is_everyone", False)
        self.message_type = data.get("type", "user")
        self.is_own = is_own

        if data.get("type") == "reaction":
            self.is_reaction = True
            self.emoji = data.get("emoji", "")
            self.target_message_id = data.get("target_message_id", "")

        quoted = data.get("quoted_message")
        if quoted:
            self.quoted_author = quoted.get("author", "")
            self.quoted_content = quoted.get("content", "")

        self._update_content()

    def watch_theme(self, _theme: str) -> None:
        self._update_content()

    def _format_timestamp(self) -> str:
        try:
            dt = datetime.fromisoformat(self.timestamp.replace("Z", "+00:00"))
            return dt.strftime("%H:%M")
        except (ValueError, TypeError):
            return self.timestamp[-8:-3] if len(self.timestamp) > 8 else ""

    def _update_content(self) -> None:
        colors = get_theme(self._theme)
        time_str = self._format_timestamp()
        label = "bot" if self.message_type == "bot" else "you" if self.is_own else ""

        if self.removed:
            self.styles.text_style = "strike"
            self.update(f"[{time_str}] {self.username}: [message removed]")
            return

        if self.is_reaction:
            self.update(f"  {self.emoji} reacted to a message")
            return

        lines = []

        if label:
            badge_style = "dim bold" if label == "bot" else "bold"
            lines.append(f"[{time_str}] [{badge_style}]{self.username}[/] [{colors['primary']}]({label})[/]")
        else:
            lines.append(f"[{time_str}] [{colors['text-accent']}]{self.username}[/]")

        if self.quoted_author and self.quoted_content:
            quote = self.quoted_content[:60] + "..." if len(self.quoted_content) > 60 else self.quoted_content
            lines.append(f"  └─ [{colors['text-muted']}]re: {self.quoted_author}: {quote}[/]")

        if self.is_everyone:
            lines.append(f"  [{colors['warning']}]📢 @everyone[/]")

        body = self.content.replace("\n", "\n  ")
        lines.append(f"  {body}")

        self.update("\n".join(lines))


class ReactionsClicked(Message):
    def __init__(self, message_id: str, group_id: str) -> None:
        self.message_id = message_id
        self.group_id = group_id
        super().__init__()


class ReplyClicked(Message):
    def __init__(self, message_id: str, username: str, content: str) -> None:
        self.message_id = message_id
        self.username = username
        self.content = content
        super().__init__()


class CopyClicked(Message):
    def __init__(self, content: str) -> None:
        self.content = content
        super().__init__()


class RemoveClicked(Message):
    def __init__(self, message_id: str, group_id: str) -> None:
        self.message_id = message_id
        self.group_id = group_id
        super().__init__()
