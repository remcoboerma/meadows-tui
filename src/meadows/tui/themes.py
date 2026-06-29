"""Theme definitions for meadows-tui (dark and light modes)."""

from __future__ import annotations

DARK_THEME = {
    "primary": "#58a6ff",
    "secondary": "#7ee787",
    "accent": "#ffa657",
    "background": "#0d1117",
    "surface": "#161b22",
    "surface-alt": "#21262d",
    "text": "#c9d1d9",
    "text-muted": "#8b949e",
    "text-accent": "#58a6ff",
    "border": "#30363d",
    "error": "#f85149",
    "success": "#7ee787",
    "warning": "#d29922",
    "mention": "#ffa657",
    "link": "#58a6ff",
    "code-bg": "#1c2128",
}

LIGHT_THEME = {
    "primary": "#0969da",
    "secondary": "#1a7f37",
    "accent": "#bf8700",
    "background": "#ffffff",
    "surface": "#f6f8fa",
    "surface-alt": "#eaeef2",
    "text": "#1f2328",
    "text-muted": "#656d76",
    "text-accent": "#0969da",
    "border": "#d0d7de",
    "error": "#cf222e",
    "success": "#1a7f37",
    "warning": "#9a6700",
    "mention": "#bf8700",
    "link": "#0969da",
    "code-bg": "#f1f4f7",
}

THEMES = {
    "dark": DARK_THEME,
    "light": LIGHT_THEME,
}


def get_theme(name: str) -> dict[str, str]:
    return THEMES.get(name, DARK_THEME)
