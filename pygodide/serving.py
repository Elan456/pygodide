from __future__ import annotations

import http.server
import socketserver
from errno import EADDRINUSE
from functools import partial
from pathlib import Path


class NoCacheHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self) -> None:
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        super().end_headers()


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
