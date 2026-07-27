"""sentiment_cli — agent-native CLI over the Bond Yield / Sentiment Analysis backend.

This package wraps the running FastAPI backend ("Bond Yield Backend") as a
structured, machine-parseable command-line interface designed to be driven by
AI agents:

  * OpenAPI-driven  — every backend endpoint becomes a CLI command, auto-derived
                      from the backend's own /openapi.json (always in sync).
  * --json          — machine-readable JSON envelope on every command.
  * describe        — full self-description so an agent can discover capabilities
                      with zero external docs.
  * REPL            — interactive shell when invoked with no sub-command.
  * exit codes      — deterministic (0 ok / 2 usage / 3 gaps / 4 backend / 1 fail).

Zero third-party dependencies: standard library only, so it runs anywhere a
Python 3.8+ interpreter is available.
"""

__version__ = "0.1.0"
NAME = "sentiment"

__all__ = ["__version__", "NAME"]
