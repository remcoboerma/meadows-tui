"""Authentication screen for meadows-tui."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical, Center
from textual.message import Message
from textual.screen import Screen
from textual.widgets import Static, Input, Button, Header, Footer


class AuthRequest(Message):
    def __init__(self, token: str | None = None, username: str | None = None, secret: str | None = None) -> None:
        self.token = token
        self.username = username
        self.secret = secret
        super().__init__()


class AuthScreen(Screen):
    def __init__(self, server_url: str, theme: str = "dark") -> None:
        super().__init__()
        self._server_url = server_url
        self._theme = theme

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(classes="auth-container"):
            yield Static(f"MEADOWS Chat — {self._server_url}", classes="auth-title")
            yield Static("", classes="spacer")
            yield Static("Paste your JWT token", classes="auth-label")
            yield Input(placeholder="eyJ...", id="token-input", password=False, classes="auth-input")
            with Center():
                yield Button("Connect with Token", id="connect-token-btn", variant="primary")
            yield Static("─ or generate locally ─", classes="auth-divider")
            yield Static("Username (for local token gen)", classes="auth-label")
            yield Input(placeholder="your-name", id="username-input", classes="auth-input")
            yield Static("JWT Secret", classes="auth-label")
            yield Input(placeholder="shared secret", id="secret-input", password=True, classes="auth-input")
            with Center():
                yield Button("Connect with Secret", id="connect-secret-btn", variant="default")
            yield Static("", id="auth-error", classes="auth-error")
        yield Footer()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "token-input":
            self._connect_with_token()
        elif event.input.id in ("username-input", "secret-input"):
            self._connect_with_secret()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "connect-token-btn":
            self._connect_with_token()
        elif event.button.id == "connect-secret-btn":
            self._connect_with_secret()

    def _connect_with_token(self) -> None:
        token = self.query_one("#token-input", Input).value.strip()
        if token:
            self.post_message(AuthRequest(token=token))
        else:
            self.query_one("#auth-error", Static).update("Please enter a token.")

    def _connect_with_secret(self) -> None:
        username = self.query_one("#username-input", Input).value.strip()
        secret = self.query_one("#secret-input", Input).value.strip()
        if username and secret:
            self.post_message(AuthRequest(username=username, secret=secret))
        else:
            self.query_one("#auth-error", Static).update("Please enter both username and secret.")

    def show_error(self, error: str) -> None:
        self.query_one("#auth-error", Static).update(f"Error: {error}")

    def on_mount(self) -> None:
        self.query_one("#token-input", Input).focus()
