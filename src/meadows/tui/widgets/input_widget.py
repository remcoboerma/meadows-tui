"""Chat input widget for meadows-tui."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Input, Button, Static
from textual.widget import Widget
from textual.message import Message
from textual.reactive import reactive

from meadows.tui.themes import get_theme


class SendMessage(Message):
    def __init__(self, content: str, quoted_message_id: str | None = None) -> None:
        self.content = content
        self.quoted_message_id = quoted_message_id
        super().__init__()


class ChatInput(Widget):
    quoted_username: reactive[str | None] = reactive(None)
    quoted_content: reactive[str | None] = reactive(None)
    quoted_id: reactive[str | None] = reactive(None)
    theme: reactive[str] = reactive("dark")

    def __init__(self, theme: str = "dark") -> None:
        super().__init__()
        self.theme = theme

    def compose(self) -> ComposeResult:
        yield Static(id="quoted-preview", classes="quoted-preview")
        with Horizontal(classes="input-row"):
            yield Input(placeholder="Type a message... (Enter to send, Alt+Enter for newline)", id="chat-input")
            yield Button("Send", id="send-btn", variant="primary")

    def on_input_submitted(self, event: Input.Submitted) -> None:
        content = event.value.strip()
        if content:
            self.post_message(SendMessage(content=content, quoted_message_id=self.quoted_id))
            self.query_one("#chat-input", Input).value = ""
            self._clear_quote()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "send-btn":
            input_w = self.query_one("#chat-input", Input)
            content = input_w.value.strip()
            if content:
                self.post_message(SendMessage(content=content, quoted_message_id=self.quoted_id))
                input_w.value = ""
                self._clear_quote()

    def set_quote(self, message_id: str, username: str, content: str) -> None:
        self.quoted_id = message_id
        preview = self.query_one("#quoted-preview", Static)
        colors = get_theme(self.theme)
        short = content[:80] + "..." if len(content) > 80 else content
        preview.update(f"┌─ [{colors['text-accent']}]replying to {username}[/]\n│ {short}\n└─ press Esc to cancel")

    def _clear_quote(self) -> None:
        self.quoted_id = None
        self.quoted_username = None
        self.quoted_content = None
        preview = self.query_one("#quoted-preview", Static)
        preview.update("")

    def key_press(self, event) -> None:
        if event.key == "escape" and self.quoted_id:
            self._clear_quote()
            event.stop()
