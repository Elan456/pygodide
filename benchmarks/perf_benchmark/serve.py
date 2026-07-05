from __future__ import annotations

import contextlib
import http.server
import socketserver
import threading
from collections.abc import Iterator
from functools import partial
from pathlib import Path


@contextlib.contextmanager
def serve_directory(directory: str | Path) -> Iterator[str]:
    resolved_directory = Path(directory).resolve()
    if not resolved_directory.is_dir():
        raise ValueError(f"{resolved_directory} is not a directory")

    handler = partial(
        http.server.SimpleHTTPRequestHandler,
        directory=str(resolved_directory),
    )
    with socketserver.TCPServer(("127.0.0.1", 0), handler) as httpd:
        host, port = httpd.server_address
        server_thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        server_thread.start()
        try:
            yield f"http://{host}:{port}"
        finally:
            httpd.shutdown()
            server_thread.join(timeout=5)
