"""Message widget for rendering chat messages in the TUI."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from textual.message import Message
from textual.reactive import reactive
from textual.widgets import Static

from meadows.tui.themes import get_theme


QUICK_EMOJIS = ["👍", "❤️", "😂", "🎉", "🤔", "👀", "🔥", "💯", "🚀"]


def _render_message(data: dict[str, Any], is_own: bool, theme: str) -> str:
    """Compute the Rich markup string for a message."""
    colors = get_theme(theme)
    message_type = data.get("type", "user")
    removed = data.get("removed", False)
    is_reaction = data.get("type") == "reaction"
    is_everyone = data.get("is_everyone", False)
    username = data.get("username", data.get("bot_name", data.get("user_id", "unknown")))
    content = data.get("content", "")
    timestamp = data.get("timestamp", "")

    try:
        dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        time_str = dt.strftime("%H:%M")
    except (ValueError, TypeError):
        time_str = timestamp[-8:-3] if len(timestamp) > 8 else ""

    if removed:
        return f"[{time_str}] {username}: [message removed]"

    if is_reaction:
        emoji = data.get("emoji", "")
        return f"  {emoji} reacted to a message"

    label = "bot" if message_type == "bot" else "you" if is_own else ""
    lines: list[str] = []

    if label:
        badge_style = "dim bold" if label == "bot" else "bold"
        lines.append(f"[{time_str}] [{badge_style}]{username}[/] [{colors['primary']}]({label})[/]")
    else:
        lines.append(f"[{time_str}] [{colors['text-accent']}]{username}[/]")

    quoted = data.get("quoted_message")
    if quoted:
        q_author = quoted.get("author", "")
        q_content = quoted.get("content", "")
        if q_author and q_content:
            quote = q_content[:60] + "..." if len(q_content) > 60 else q_content
            lines.append(f"  └─ [{colors['text-muted']}]re: {q_author}: {quote}[/]")

    if is_everyone:
        lines.append(f"  [{colors['warning']}]📢 @everyone[/]")

    body = content.replace("\n", "\n  ")
    lines.append(f"  {body}")

    return "\n".join(lines)


class MessageWidget(Static):
    message_id: reactive[str] = reactive("")
    group_id: reactive[str] = reactive("")
    username: reactive[str] = reactive("")
    content: reactive[str] = reactive("")
    timestamp: reactive[str] = reactive("")
    removed: reactive[bool] = reactive(False)
    is_own: reactive[bool] = reactive(False)
    message_type: reactive[str] = reactive("user")

    def __init__(self, data: dict[str, Any], is_own: bool = False, theme: str = "dark") -> None:
        self._data = data
        self._theme = theme
        super().__init__(_render_message(data, is_own, theme))
        self.message_id = data.get("id", "")
        self.group_id = data.get("group_id", "")
        self.username = data.get("username", data.get("bot_name", data.get("user_id", "unknown")))
        self.content = data.get("content", "")
        self.timestamp = data.get("timestamp", "")
        self.removed = data.get("removed", False)
        self.message_type = data.get("type", "user")
        self.is_own = is_own

    def _update_content(self) -> None:
        self.update(_render_message(self._data, self.is_own, self._theme))


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
