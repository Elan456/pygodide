from __future__ import annotations

import contextlib
import http.server
import socketserver
import threading
from collections.abc import Iterator
from errno import EADDRINUSE
from functools import partial
from pathlib import Path


class NoCacheHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self) -> None:
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        super().end_headers()


class QuietNoCacheHTTPRequestHandler(NoCacheHTTPRequestHandler):
    """Same as NoCacheHTTPRequestHandler but suppresses request logging."""

    def log_message(self, format: str, *args) -> None:
        return


class ReusableTCPServer(socketserver.TCPServer):
    allow_reuse_address = True


def serve_directory_forever(directory: Path, port: int = 8000) -> None:
    handler = partial(NoCacheHTTPRequestHandler, directory=str(directory))

    try:
        with ReusableTCPServer(("", port), handler) as httpd:
            print(f"Serving {directory} at http://localhost:{port}")
            try:
                httpd.serve_forever()
            except KeyboardInterrupt:
                print("Shutting down server...")
    except OSError as exc:
        if exc.errno == EADDRINUSE:
            raise RuntimeError(
                f"Port {port} is already in use. Stop the other server or choose a "
                "different port."
            ) from exc
        raise

    print("Server stopped.")


@contextlib.contextmanager
def serve_directory(
    directory: str | Path,
    *,
    quiet: bool = True,
) -> Iterator[str]:
    """Serve a directory on an ephemeral local port for the duration of the block."""
    resolved_directory = Path(directory).resolve()
    if not resolved_directory.is_dir():
        raise ValueError(f"{resolved_directory} is not a directory")

    handler_cls = QuietNoCacheHTTPRequestHandler if quiet else NoCacheHTTPRequestHandler
    handler = partial(handler_cls, directory=str(resolved_directory))
    with ReusableTCPServer(("127.0.0.1", 0), handler) as httpd:
        host, port = httpd.server_address
        server_thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        server_thread.start()
        try:
            yield f"http://{host}:{port}"
        finally:
            httpd.shutdown()
            server_thread.join(timeout=5)
