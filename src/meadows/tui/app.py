"""MEADOWS TUI — curses-based terminal chat client."""

from __future__ import annotations

import asyncio
import curses
import logging
import os
import queue
import threading
from datetime import datetime
from typing import Any

from meadows.tui.client_bridge import ClientBridge, ConnectionFailedError
from meadows.tui.config import TUIConfig
from meadows.tui.themes import get_theme
import contextlib

logger = logging.getLogger(__name__)

COLOR_MAP = {
    "#58a6ff": curses.COLOR_BLUE,
    "#7ee787": curses.COLOR_GREEN,
    "#ffa657": curses.COLOR_YELLOW,
    "#c9d1d9": curses.COLOR_WHITE,
    "#8b949e": curses.COLOR_CYAN,
    "#f85149": curses.COLOR_RED,
    "#d29922": curses.COLOR_YELLOW,
    "#0969da": curses.COLOR_BLUE,
    "#1a7f37": curses.COLOR_GREEN,
    "#bf8700": curses.COLOR_YELLOW,
    "#1f2328": curses.COLOR_BLACK,
    "#656d76": curses.COLOR_CYAN,
    "#cf222e": curses.COLOR_RED,
    "#9a6700": curses.COLOR_YELLOW,
}


def hex_to_curses(hex_color: str, fallback: int = curses.COLOR_WHITE) -> int:
    return COLOR_MAP.get(hex_color, fallback)


class CursesApp:
    def __init__(self, config: TUIConfig) -> None:
        self._config = config
        self._event_queue: queue.Queue[tuple[str, dict[str, Any]]] = queue.Queue()
        self._bridge = ClientBridge(self._event_queue, config.server_url)
        self._async_loop: asyncio.AbstractEventLoop | None = None
        self._screen: str = "auth"
        self._running = True
        self._status_msg = ""
        self._status_expire: float = 0.0

        self._theme_name = config.theme
        if self._theme_name == "auto":
            term = os.environ.get("COLORFGBG", "")
            self._theme_name = "light" if "15;0" in term else "dark"

        self._theme = get_theme(self._theme_name)
        self._sidebar_width = 24
        self._sidebar_visible = True
        self._focus = "input"

        self._auth_token_input = ""
        self._auth_error = ""

        self._groups: dict[str, dict[str, Any]] = {}
        self._group_order: list[str] = []
        self._current_group = "general"
        self._selected_group_idx = 0
        self._users: list[str] = []
        self._bots: list[dict[str, Any]] = []
        self._messages: list[dict[str, Any]] = []
        self._msg_widgets: dict[str, dict[str, Any]] = {}
        self._typing_users: list[str] = []
        self._input_buf = ""
        self._input_cursor = 0
        self._scroll_offset = 0

    _colors_initialized: bool = False

    def _init_colors(self) -> None:
        curses.start_color()
        curses.use_default_colors()
        for i, (name, hex_c) in enumerate(self._theme.items(), start=1):
            fg = hex_to_curses(hex_c)
            curses.init_pair(i, fg, -1)
        self._colors_initialized = True

    def _color(self, name: str, attr: int = 0) -> int:
        if not self._colors_initialized:
            return attr
        keys = list(self._theme.keys())
        try:
            idx = keys.index(name) + 1
        except ValueError:
            return attr
        return curses.color_pair(idx) | attr

    def _run_async(self, coro: Any) -> Any:
        if self._async_loop:
            return asyncio.run_coroutine_threadsafe(coro, self._async_loop).result(timeout=30)
        return None

    def _start_async_loop(self) -> None:
        def _loop() -> None:
            self._async_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._async_loop)
            self._async_loop.run_forever()

        t = threading.Thread(target=_loop, daemon=True)
        t.start()

    def _connect(self, token: str | None = None, username: str | None = None, secret: str | None = None) -> None:
        try:
            if token:
                self._run_async(self._bridge.connect_with_token(token))
            elif username and secret:
                self._run_async(self._bridge.connect_with_secret(username, secret))
        except ConnectionFailedError as exc:
            self._auth_error = str(exc)
        except Exception as exc:
            self._auth_error = str(exc)

    def _set_status(self, msg: str, duration: float = 3.0) -> None:
        import time
        self._status_msg = msg
        self._status_expire = time.monotonic() + duration

    def run(self, stdscr: "curses.window") -> None:
        self._stdscr = stdscr
        curses.curs_set(1)
        stdscr.nodelay(True)
        stdscr.keypad(True)
        with contextlib.suppress(Exception):
            curses.mousemask(curses.ALL_MOUSE_EVENTS | curses.REPORT_MOUSE_POSITION)

        self._init_colors()
        self._start_async_loop()

        if self._config.token:
            self._screen = "connecting"
            self._connect(token=self._config.token)
        elif self._config.jwt_secret and self._config.username:
            self._screen = "connecting"
            self._connect(username=self._config.username, secret=self._config.jwt_secret)

        while self._running:
            try:
                self._handle_input()
                self._handle_events()
                self._draw()
            except KeyboardInterrupt:
                self._running = False
                break

    def _handle_input(self) -> None:
        try:
            ch = self._stdscr.getch()
        except curses.error:
            return

        if ch == -1:
            return

        if self._screen == "auth":
            self._handle_auth_input(ch)
        elif self._screen == "chat":
            self._handle_chat_input(ch)

    def _handle_auth_input(self, ch: int) -> None:
        if ch == 27:
            self._running = False
        elif ch in (curses.KEY_ENTER, 10, 13):
            if self._auth_token_input.strip():
                self._screen = "connecting"
                self._connect(token=self._auth_token_input.strip())
        elif ch in (curses.KEY_BACKSPACE, 127, 8):
            self._auth_token_input = self._auth_token_input[:-1]
        elif 32 <= ch <= 126:
            self._auth_token_input += chr(ch)

    def _handle_chat_input(self, ch: int) -> None:
        if self._focus == "input":
            self._handle_input_field(ch)
        elif self._focus == "groups":
            self._handle_group_nav(ch)

    def _handle_input_field(self, ch: int) -> None:  # noqa: C901
        if ch == 27:
            self._focus = "groups"
        elif ch == curses.KEY_F(10):
            self._running = False
        elif ch in (curses.KEY_ENTER, 10, 13):
            if self._input_buf.strip():
                self._run_async(self._bridge.send_message(self._input_buf.strip(), self._current_group))
                self._input_buf = ""
                self._input_cursor = 0
        elif ch in (curses.KEY_BACKSPACE, 127, 8):
            if self._input_cursor > 0:
                self._input_buf = self._input_buf[:self._input_cursor - 1] + self._input_buf[self._input_cursor:]
                self._input_cursor -= 1
        elif ch == curses.KEY_LEFT:
            self._input_cursor = max(0, self._input_cursor - 1)
        elif ch == curses.KEY_RIGHT:
            self._input_cursor = min(len(self._input_buf), self._input_cursor + 1)
        elif ch == curses.KEY_UP:
            self._scroll_offset = max(0, self._scroll_offset - 1)
        elif ch == curses.KEY_DOWN:
            max_scroll = max(0, len(self._messages) - 1)
            self._scroll_offset = min(max_scroll, self._scroll_offset + 1)
        elif ch == 9 or ch == curses.KEY_BTAB:
            self._focus = "groups"
        elif ch == 18:
            self._sidebar_visible = not self._sidebar_visible
        elif 32 <= ch <= 126:
            self._input_buf = self._input_buf[:self._input_cursor] + chr(ch) + self._input_buf[self._input_cursor:]
            self._input_cursor += 1

    def _handle_group_nav(self, ch: int) -> None:
        if ch == 27 or ch == 9 or ch == curses.KEY_BTAB:
            self._focus = "input"
        elif ch == curses.KEY_UP:
            self._selected_group_idx = max(0, self._selected_group_idx - 1)
        elif ch == curses.KEY_DOWN:
            self._selected_group_idx = min(len(self._group_order) - 1, self._selected_group_idx + 1)
        elif ch in (curses.KEY_ENTER, 10, 13):
            if self._group_order:
                gid = self._group_order[self._selected_group_idx]
                self._switch_group(gid)
        elif ch == 110:
            self._prompt_new_group()

    def _prompt_new_group(self) -> None:
        curses.echo()
        curses.curs_set(1)
        h, _w = self._stdscr.getmaxyx()
        prompt_y = h - 2
        self._stdscr.move(prompt_y, 2)
        self._stdscr.clrtoeol()
        self._stdscr.addstr(prompt_y, 2, "New group name: ", self._color("text-accent"))
        self._stdscr.refresh()
        try:
            curses.nocbreak()
            self._stdscr.keypad(True)
            name = self._stdscr.getstr(prompt_y, 18, 40).decode("utf-8", errors="replace").strip()
            curses.cbreak()
            self._stdscr.nodelay(True)
            if name:
                gid = name.lower().replace(" ", "-")
                self._run_async(self._bridge.create_group(gid, name=name))
                self._set_status(f"Creating group '{name}'...")
        except Exception:
            curses.cbreak()
            self._stdscr.nodelay(True)
        curses.noecho()
        curses.curs_set(1)

    def _switch_group(self, gid: str) -> None:
        if gid == self._current_group:
            return
        self._current_group = gid
        self._messages = []
        self._msg_widgets = {}
        self._scroll_offset = 0
        self._typing_users = []
        self._run_async(self._bridge.join_group(gid))

    def _handle_events(self) -> None:  # noqa: C901
        while True:
            try:
                event, data = self._event_queue.get_nowait()
            except queue.Empty:
                break

            if event == "authenticated":
                self._screen = "chat"
                self._handle_authenticated(data)
            elif event == "auth_error":
                self._screen = "auth"
                self._auth_error = data.get("error", str(data))
            elif event == "message":
                self._handle_message(data)
            elif event == "user_typing":
                self._handle_user_typing(data)
            elif event == "joined_group":
                self._handle_joined_group(data)
            elif event == "left_group":
                gid = data.get("group_id", "")
                self._groups.pop(gid, None)
                self._group_order = [g for g in self._group_order if g != gid]
            elif event == "members_updated":
                self._users = [m.get("username", m.get("user_id", "")) for m in data.get("members", [])]
            elif event == "group_created":
                gid = data.get("id", data.get("group_id", ""))
                self._groups[gid] = data
                if gid not in self._group_order:
                    self._group_order.append(gid)
            elif event == "group_deleted":
                gid = data.get("group_id", "")
                self._groups.pop(gid, None)
                self._group_order = [g for g in self._group_order if g != gid]
            elif event == "bot_list":
                self._bots = data.get("bots", [])
            elif event == "message_removed":
                mid = data.get("message_id", "")
                if mid in self._msg_widgets:
                    self._msg_widgets[mid]["removed"] = True
            elif event == "error":
                self._set_status(f"Error: {data.get('error', str(data))}", 5.0)

        if self._typing_users:
            self._typing_users = [u for u in self._typing_users if True]

    def _handle_authenticated(self, data: dict[str, Any]) -> None:
        self._screen = "chat"
        groups = data.get("groups", [])
        self._groups = {g.get("id", g.get("group_id", "")): g for g in groups}
        self._group_order = list(self._groups.keys())
        self._current_group = self._group_order[0] if self._group_order else ""
        self._selected_group_idx = 0
        self._users = []
        self._bots = data.get("bots", [])
        if self._current_group:
            self._run_async(self._bridge.join_group(self._current_group))

    def _handle_message(self, data: dict[str, Any]) -> None:
        gid = data.get("group_id", "")
        if gid != self._current_group:
            return
        self._messages.append(data)
        self._msg_widgets[data.get("id", "")] = data
        self._scroll_offset = max(0, len(self._messages) - 1)

    def _handle_user_typing(self, data: dict[str, Any]) -> None:
        gid = data.get("group_id", "")
        if gid != self._current_group:
            return
        uid = data.get("user_id", "")
        if uid not in self._typing_users:
            self._typing_users.append(uid)

    def _handle_joined_group(self, data: dict[str, Any]) -> None:
        gid = data.get("group_id", "")
        self._current_group = gid
        self._messages = []
        self._msg_widgets = {}
        self._scroll_offset = 0
        self._typing_users = []

        members = data.get("members", [])
        self._users = [m.get("username", m.get("user_id", "")) for m in members]

        thread = data.get("thread", [])
        for msg in thread:
            self._messages.append(msg)
            self._msg_widgets[msg.get("id", "")] = msg

    def _msg_height(self, data: dict[str, Any]) -> int:
        content = data.get("content", "")
        lines = 1
        if data.get("quoted_message"):
            lines += 1
        try:
            w = self._stdscr.getmaxyx()[1]
        except (AttributeError, curses.error):
            w = 80
        lines += max(1, (len(content) // max(1, w - self._sidebar_width - 10)) + 1)
        return lines

    def _draw(self) -> None:
        self._stdscr.erase()
        h, w = self._stdscr.getmaxyx()

        if self._screen == "auth":
            self._draw_auth(h, w)
        elif self._screen == "connecting":
            self._draw_connecting(h, w)
        elif self._screen == "chat":
            self._draw_chat(h, w)

        self._stdscr.noutrefresh()
        curses.doupdate()

    def _draw_auth(self, h: int, w: int) -> None:
        title = "MEADOWS Chat"
        self._stdscr.addstr(h // 2 - 3, (w - len(title)) // 2, title, self._color("primary") | curses.A_BOLD)

        prompt = "Paste your JWT token and press Enter:"
        self._stdscr.addstr(h // 2 - 1, (w - len(prompt)) // 2, prompt, self._color("text"))

        input_display = self._auth_token_input
        if len(input_display) > w - 4:
            input_display = "..." + input_display[-(w - 7):]
        self._stdscr.addstr(h // 2 + 1, 2, "> " + input_display, self._color("text-accent"))
        self._stdscr.move(h // 2 + 1, 4 + len(input_display))

        if self._auth_error:
            err = self._auth_error[:w - 4]
            self._stdscr.addstr(h // 2 + 3, (w - len(err)) // 2, err, self._color("error"))

        hint = "Esc to quit"
        self._stdscr.addstr(h - 1, (w - len(hint)) // 2, hint, self._color("text-muted"))

    def _draw_connecting(self, h: int, w: int) -> None:
        msg = "Connecting to server..."
        self._stdscr.addstr(h // 2, (w - len(msg)) // 2, msg, self._color("text-accent"))

    def _draw_chat(self, h: int, w: int) -> None:
        import time
        sidebar_w = self._sidebar_width if self._sidebar_visible else 0
        msg_x = sidebar_w + 1
        msg_w = w - sidebar_w - 2
        msg_h = h - 4

        if self._sidebar_visible:
            self._draw_sidebar(h, sidebar_w)

        self._draw_group_header(sidebar_w, w - sidebar_w)

        self._draw_messages(msg_x, 2, msg_w, msg_h)

        self._draw_input_line(h - 1, sidebar_w, w - sidebar_w)

        if self._status_msg and time.monotonic() < self._status_expire:
            status = self._status_msg[:w - 4]
            self._stdscr.addstr(h - 2, sidebar_w + 2, status, self._color("warning"))
        elif self._typing_users:
            names = ", ".join(self._typing_users[:3])
            txt = f"{names} typing..."
            self._stdscr.addstr(h - 2, sidebar_w + 2, txt[:msg_w - 2], self._color("text-muted"))

    def _draw_sidebar(self, h: int, w: int) -> None:  # noqa: C901
        y = 0
        self._stdscr.addstr(y, 1, "Groups", self._color("primary") | curses.A_BOLD)
        y += 1

        for i, gid in enumerate(self._group_order):
            if y >= h - 6:
                break
            gdata = self._groups.get(gid, {})
            name = gdata.get("name", gid)
            count = gdata.get("member_count", "")
            label = f" {name}"
            if count:
                label += f" ({count})"
            label = label[:w - 2]

            attr = self._color("text")
            if gid == self._current_group:
                attr = self._color("primary") | curses.A_BOLD
            if i == self._selected_group_idx and self._focus == "groups":
                attr |= curses.A_REVERSE

            with contextlib.suppress(curses.error):
                self._stdscr.addstr(y, 1, label, attr)
            y += 1

        y += 1
        self._stdscr.addstr(y, 1, "Users", self._color("primary") | curses.A_BOLD)
        y += 1
        for uname in self._users[:5]:
            if y >= h - 3:
                break
            with contextlib.suppress(curses.error):
                self._stdscr.addstr(y, 1, f" {uname}"[:w - 2], self._color("text"))
            y += 1

        y += 1
        self._stdscr.addstr(y, 1, "Bots", self._color("primary") | curses.A_BOLD)
        y += 1
        for bot in self._bots[:5]:
            if y >= h - 1:
                break
            bname = bot.get("name", "")
            with contextlib.suppress(curses.error):
                self._stdscr.addstr(y, 1, f" {bname}"[:w - 2], self._color("accent"))
            y += 1

        for x in range(h):
            with contextlib.suppress(curses.error):
                self._stdscr.addch(x, w, curses.ACS_VLINE, self._color("border"))

    def _draw_group_header(self, x: int, w: int) -> None:
        status = "connected" if self._bridge.connected else "disconnected"
        status_attr = self._color("success") if self._bridge.connected else self._color("warning")
        header = f" #{self._current_group} "
        try:
            self._stdscr.addstr(0, x + 1, header, self._color("primary") | curses.A_BOLD)
            self._stdscr.addstr(0, x + 1 + len(header), status, status_attr)
        except curses.error:
            pass
        try:
            for cx in range(x, x + w):
                self._stdscr.addch(1, cx, curses.ACS_HLINE, self._color("border"))
        except curses.error:
            pass

    def _draw_messages(self, x: int, y: int, w: int, h: int) -> None:
        auth = self._bridge.auth_data
        aid = auth.user_id if auth else ""

        lines: list[tuple[str, int]] = []
        for msg in self._messages:
            lines.extend(self._format_message(msg, w, aid))

        visible_start = max(0, len(lines) - h + self._scroll_offset)
        visible = lines[visible_start:visible_start + h]

        for i, (text, attr) in enumerate(visible):
            if y + i >= y + h:
                break
            with contextlib.suppress(curses.error):
                self._stdscr.addnstr(y + i, x, text, w - 1, attr)

    def _format_message(self, data: dict[str, Any], width: int, own_id: str) -> list[tuple[str, int]]:
        username = data.get("username", data.get("bot_name", data.get("user_id", "?")))
        content = data.get("content", "")
        timestamp = data.get("timestamp", "")
        msg_type = data.get("type", "user")
        removed = data.get("removed", False)
        is_own = data.get("user_id", "") == own_id

        try:
            dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
            ts = dt.strftime("%H:%M")
        except (ValueError, TypeError):
            ts = timestamp[-8:-3] if len(timestamp) > 8 else ""

        result: list[tuple[str, int]] = []

        if removed:
            line = f"[{ts}] {username}: [message removed]"
            result.append((line[:width], curses.A_DIM))
            return result

        badge = ""
        badge_attr = curses.A_NORMAL
        if msg_type == "bot":
            badge = " (bot)"
            badge_attr = curses.A_DIM | curses.A_BOLD
        elif is_own:
            badge = " (you)"
            badge_attr = curses.A_BOLD

        header = f"[{ts}] {username}{badge}"
        result.append((header[:width], self._color("text-accent") | badge_attr))

        quoted = data.get("quoted_message")
        if quoted:
            qa = quoted.get("author", "")
            qc = quoted.get("content", "")
            if qa and qc:
                qt = qc[:50] + "..." if len(qc) > 50 else qc
                result.append((f"  └─ re: {qa}: {qt}"[:width], self._color("text-muted")))

        body_lines = content.split("\n")
        for bl in body_lines:
            result.append((f"  {bl}"[:width], self._color("text")))

        return result

    def _draw_input_line(self, y: int, x: int, w: int) -> None:
        try:
            for cx in range(x, x + w):
                self._stdscr.addch(y - 1, cx, curses.ACS_HLINE, self._color("border"))
        except curses.error:
            pass

        prompt = "> "
        input_display = self._input_buf
        max_input = w - len(prompt) - 2
        if len(input_display) > max_input:
            input_display = input_display[-(max_input - 3):]

        attr = self._color("text")
        if self._focus == "input":
            attr |= curses.A_UNDERLINE

        try:
            self._stdscr.addstr(y, x + 1, prompt, self._color("primary") | curses.A_BOLD)
            self._stdscr.addstr(y, x + 1 + len(prompt), input_display, attr)
        except curses.error:
            pass

        if self._focus == "input":
            cursor_x = x + 1 + len(prompt) + min(self._input_cursor, max_input)
            with contextlib.suppress(curses.error):
                self._stdscr.move(y, cursor_x)

        hint = " Tab:switch pane | F10:quit | ^R:sidebar "
        with contextlib.suppress(curses.error):
            self._stdscr.addnstr(y, x + w - len(hint) - 1, hint, len(hint), self._color("text-muted"))


def run_app(config: TUIConfig) -> None:
    app = CursesApp(config)
    curses.wrapper(app.run)
