"""Opt-in network blocker for unit-test runs."""

from __future__ import annotations

import os
import socket
from typing import Any


class NetworkBlockedError(RuntimeError):
    """Raised when code tries to open a network connection in no-network mode."""


_INSTALLED = False
_ORIGINAL_CONNECT = socket.socket.connect
_ORIGINAL_CREATE_CONNECTION = socket.create_connection


def install_no_network_guard() -> None:
    """Block outbound sockets for deterministic unit tests."""
    global _INSTALLED
    if _INSTALLED:
        return

    def blocked_connect(self: socket.socket, address: Any) -> None:
        raise NetworkBlockedError(f"Network access is disabled for unit tests: {address!r}")

    def blocked_create_connection(address: Any, *args: Any, **kwargs: Any) -> socket.socket:
        raise NetworkBlockedError(f"Network access is disabled for unit tests: {address!r}")

    socket.socket.connect = blocked_connect
    socket.create_connection = blocked_create_connection
    _INSTALLED = True


def uninstall_no_network_guard() -> None:
    """Restore socket functions. Intended for focused helper tests only."""
    global _INSTALLED
    if not _INSTALLED:
        return
    socket.socket.connect = _ORIGINAL_CONNECT
    socket.create_connection = _ORIGINAL_CREATE_CONNECTION
    _INSTALLED = False


def install_from_env() -> None:
    if os.getenv("GEOSPOILER_NO_NETWORK", "").lower() in {"1", "true", "yes"}:
        install_no_network_guard()
