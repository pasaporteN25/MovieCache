#!/usr/bin/env python3
"""Smoke-test an installed wheel without relying on the repository source tree."""

from __future__ import annotations

import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

from movie_inbox.domain.catalog import normalize_item
from movie_inbox.infrastructure.json_repository import JsonCatalogRepository
from movie_inbox.web.assets import (
    render_html,
    render_login_html,
    render_password_change_html,
    static_asset,
)


def main() -> int:
    assert "Movie Inbox wheel smoke" in render_html("Movie Inbox wheel smoke", "token")
    assert "Movie Inbox wheel smoke" in render_login_html("Movie Inbox wheel smoke", "token")
    assert "Movie Inbox wheel smoke" in render_password_change_html("Movie Inbox wheel smoke", "token")
    assert static_asset("style.css") is not None
    assert static_asset("app.js") is not None
    assert static_asset("login.js") is not None
    assert static_asset("password-change.js") is not None

    with tempfile.TemporaryDirectory() as temporary:
        catalog = Path(temporary) / "catalog.json"
        JsonCatalogRepository(catalog, normalize_item).write(
            [normalize_item({"id": "wheel-smoke", "title": "Wheel Smoke", "kind": "pelicula"})]
        )
        password_file = Path(temporary) / "owner-password.txt"
        password_file.write_text("a-long-local-password\n", encoding="utf-8")
        port = available_port()
        process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "movie_inbox.cli.main",
                "serve",
                str(catalog),
                "--port",
                str(port),
                "--no-open",
                "--no-image-cache",
                "--owner-password-file",
                str(password_file),
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        try:
            payload = wait_for_health(port, process)
            if payload != b'{"status":"ok"}':
                raise RuntimeError(f"Unexpected health response: {payload!r}")
        finally:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
    print("Installed wheel smoke test passed")
    return 0


def available_port() -> int:
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


def wait_for_health(port: int, process: subprocess.Popen[str]) -> bytes:
    url = f"http://127.0.0.1:{port}/healthz"
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        if process.poll() is not None:
            output = process.stdout.read() if process.stdout else ""
            raise RuntimeError(f"Installed server exited before healthcheck:\n{output}")
        try:
            with urlopen(url, timeout=1) as response:
                if response.status == 200:
                    return response.read()
        except (OSError, URLError):
            time.sleep(0.2)
    raise RuntimeError("Installed server did not become healthy")


if __name__ == "__main__":
    raise SystemExit(main())
