"""Interactive REPL — the default mode when no sub-command is given."""
from __future__ import annotations

import shlex
import sys
from typing import List

from .client import Client, NetworkError
from .config import Config
from .skin import Skin
from .spec import Spec


def run_repl(config: Config, client: Client, spec: Spec, skin: Skin,
             no_banner: bool = False) -> int:
    # Import here to avoid a circular import at module load time.
    from .cli import dispatch

    reachable = None
    try:
        status, _ = client.health()
        reachable = 200 <= status < 300
    except Exception:
        reachable = False

    if not no_banner:
        skin.banner(config.base_url, spec.version, reachable)

    try:
        import readline  # noqa: F401  (enables history/editing on POSIX)
    except Exception:
        pass

    prompt = "sentiment> "
    while True:
        try:
            line = input(prompt)
        except EOFError:
            sys.stderr.write("\n")
            break
        except KeyboardInterrupt:
            sys.stderr.write("\n(^C — type 'exit' to quit)\n")
            continue

        line = line.strip()
        if not line:
            continue
        if line in ("exit", "quit", ":q"):
            break
        if line in ("clear", "cls"):
            sys.stderr.write("\033[2J\033[H")
            continue
        if line.startswith("use "):
            new_url = line[4:].strip()
            if new_url:
                config.base_url = new_url.rstrip("/")
                client.config.base_url = config.base_url
                skin.success(f"backend -> {config.base_url}")
            continue

        try:
            argv: List[str] = shlex.split(line)
        except ValueError as exc:
            skin.error(f"parse error: {exc}")
            continue

        try:
            dispatch(argv, config, client, spec, skin, force_json=False)
        except NetworkError as exc:
            skin.error(str(exc))
        except SystemExit:
            pass
        except Exception as exc:  # keep the REPL alive
            skin.error(f"{type(exc).__name__}: {exc}")

    skin.status("bye")
    return 0
