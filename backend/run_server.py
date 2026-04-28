"""Entry point used by PyInstaller for the Tauri sidecar build.

The Tauri shell spawns this binary as a sidecar with ``--port <port>`` (default
8765). We bind to 127.0.0.1 only — the desktop app is single-user and the
backend must never be exposed to the network.
"""

from __future__ import annotations

import argparse
import multiprocessing
import sys


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="super-aff-backend")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    return parser.parse_args(argv)


def main() -> None:
    # PyInstaller-bundled multiprocessing must be initialised explicitly so
    # uvicorn's reload/worker spawn helpers don't relaunch the bundle.
    multiprocessing.freeze_support()
    args = _parse_args(sys.argv[1:])

    # Imported lazily so PyInstaller's analysis still picks up the FastAPI app.
    import uvicorn

    from app.main import app

    uvicorn.run(
        app,
        host=args.host,
        port=args.port,
        log_level="info",
        access_log=False,
    )


if __name__ == "__main__":
    main()
