# meadows-tui

> MEADOWS terminal UI client: a Textual-based TUI chat client for MEADOWS.
> Uses click for CLI argument parsing and Textual for the terminal interface.
> Connects directly to meadows-server via Socket.IO using meadows-client.

## What this package contains

- `cli.py` — Click entry point with env-var support
- `app.py` — Textual `App` with dark/light theme, keybindings, auth flow
- `screens/auth_screen.py` — JWT token paste or local secret auth
- `screens/chat_screen.py` — Main chat: messages, sidebar, input
- `widgets/message_widget.py` — Message rendering with quotes, reactions
- `widgets/input_widget.py` — Chat input with reply quote preview
- `widgets/sidebar_widget.py` — Groups, users, and bots panels
- `client_bridge.py` — Adapts MeadowClient events to Textual messages
- `themes.py` — Dark and light color definitions
- `config.py` — Configuration dataclass

## Install

```bash
uv pip install -e ".[dev]"
```

## Run

```bash
# With a JWT token
MEADOWS_JWT=eyJ... meadows-tui

# Or with a shared secret
MEADOWS_JWT_SECRET=secret MEADOWS_USERNAME=alice meadows-tui

# Or specify server explicitly
meadows-tui --server http://chat.example.com:8080 --token eyJ...
```

## CLI Options

| Option | Env Var | Default | Description |
|--------|---------|---------|-------------|
| `--server` | `MEADOWS_SERVER_URL` | `http://localhost:8080` | Socket.IO server URL |
| `--token` | `MEADOWS_JWT` | — | JWT token (pasted) |
| `--jwt-secret` | `MEADOWS_JWT_SECRET` | — | Secret for local token gen |
| `--username` | `MEADOWS_USERNAME` | — | Username for local token gen |
| `--theme` | `MEADOWS_THEME` | `auto` | `dark`, `light`, or `auto` |
| `--log-level` | `MEADOWS_LOG_LEVEL` | `WARNING` | `DEBUG`, `INFO`, `WARNING`, `ERROR` |

## Keybindings

| Key | Action |
|-----|--------|
| `Ctrl+t` | Toggle dark/light theme |
| `Ctrl+b` | Toggle sidebar |
| `Ctrl+n` | Focus input |
| `Ctrl+g` | Focus groups list |
| `Ctrl+q` | Quit |

## Architecture invariants

1. **Protocol constants only.** The only import from `meadows.protocol` is `EventName` (in `__init__.py`).
2. **Transport via meadows-client.** No raw Socket.IO usage; all transport goes through `MeadowClient`.
3. **Event bridge.** Socket.IO events from the server are translated to Textual `Message` subclasses in `client_bridge.py`.
4. **Theme support.** Dark/light modes with terminal-appropriate colors, toggleable at runtime.
5. **PEP 420 namespace.** `src/meadows/tui/__init__.py` exists; there is NO `src/meadows/__init__.py`.

## Configuration (env vars)

| variable | default | purpose |
|----------|---------|---------|
| `MEADOWS_SERVER_URL` | `http://localhost:8080` | server URL for Socket.IO |
| `MEADOWS_JWT` | — | pre-encoded JWT token |
| `MEADOWS_JWT_SECRET` | — | JWT secret for local token generation |
| `MEADOWS_USERNAME` | — | username when using JWT secret |
| `MEADOWS_THEME` | `auto` | color theme choice |
| `MEADOWS_LOG_LEVEL` | `WARNING` | logging verbosity |
| `MEADOWS_SYSTEM_NAME` | `MEADOWS Chat` | display name |

## Features

- Multi-group chat with sidebar navigation
- Message send/receive with typing indicators
- Dark and light color themes (toggle at runtime)
- Collapsible sidebar
- Emoji reactions (quick pick from 9 emojis)
- Reply to messages (quote preview)
- Message removal
- User and bot lists per group
- JWT authentication (pasted token or local secret)
- Auto-connect via env vars