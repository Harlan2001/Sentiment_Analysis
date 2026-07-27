"""Terminal skin: branded banner + styled status lines.

All decoration is written to stderr so that stdout stays clean for machine
consumption. Colour is disabled automatically for non-TTY output or when the
NO_COLOR environment variable is set.
"""
from __future__ import annotations

import os
import sys
from typing import Optional


class Skin:
    def __init__(self, stream=None, color: Optional[bool] = None):
        self.stream = stream or sys.stderr
        if color is None:
            color = self.stream.isatty() and os.environ.get("NO_COLOR") is None
        self.color = color

    def _c(self, code: str, text: str) -> str:
        if not self.color:
            return text
        return f"\033[{code}m{text}\033[0m"

    def _emit(self, text: str) -> None:
        self.stream.write(text + "\n")
        self.stream.flush()

    # ---- status helpers ------------------------------------------------------
    def success(self, msg: str) -> None:
        self._emit(self._c("32", "OK  ") + msg)

    def error(self, msg: str) -> None:
        self._emit(self._c("31", "ERR ") + msg)

    def warning(self, msg: str) -> None:
        self._emit(self._c("33", "!   ") + msg)

    def info(self, msg: str) -> None:
        self._emit(self._c("36", "i   ") + msg)

    def status(self, msg: str) -> None:
        self._emit(self._c("90", msg))

    def label(self, tag: str, msg: str) -> None:
        color = {
            "not_implemented": "33",   # yellow
            "out_of_scope": "90",       # grey
        }.get(tag, "36")
        self._emit(self._c(color, f"[{tag}] ") + msg)

    def banner(self, base_url: str, version: str, reachable: Optional[bool] = None) -> None:
        title = self._c("1;36", "sentiment")
        sub = self._c("90", f"agent-native CLI · Bond Yield Backend · v{version}")
        line = self._c("90", "─" * 54)
        self._emit("")
        self._emit(f"  {title}   {sub}")
        self._emit(f"  {line}")
        self._emit(self._c("90", f"  backend  {base_url}"))
        if reachable is not None:
            dot = self._c("32", "● online") if reachable else self._c("31", "● offline")
            self._emit(f"  status   {dot}")
        self._emit(self._c("90", "  type 'help' for commands · 'exit' to quit"))
        self._emit("")
