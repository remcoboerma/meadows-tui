"""MEADOWS terminal UI client.

Textual-based TUI chat client connecting to MEADOWS server via
meadows-client. Uses click for CLI argument parsing.

This package imports only EventName from meadows.protocol for protocol
constants, and relies on meadows-client for transport.
"""

from meadows.protocol import EventName

__all__ = ["EventName"]
