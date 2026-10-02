"""Shared HTTP stub server and byte fixtures for unit tests."""

import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

# Minimal valid JPEG (1x1 white pixel)
JPEG_BYTES = bytes.fromhex(
    "ffd8ffe000104a464946000101000001000000010000"
    "00ffdb00430008060607060508070708090908080a0c"
    "0d0c0b0e0f0c0e0e0f1211111111111111111111111111"
    "1111111111111111111111111111111111110109090a0c"
    "0a0b0d0d0e0f121113131211121415151414151718191a"
    "1a1a191a1c1e2020201a1c1e2020202020202020202020"
    "ffc0000b08000100010101110000ffda000c0100021100"
    "003f00fbfa2e451101ffd9"
)

# Minimal valid PNG (1x1 transparent pixel)
PNG_BYTES = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000"
    "000108060000001f15c4890000000d49444154789c63"
    "00010000ff03000046e4a4180000000049454e44ae42"
    "6082"
)

# Non-image content (plain text — should be rejected by magic bytes)
TEXT_BYTES = b"This is not an image. Just some plain text data."


class StubHandler(BaseHTTPRequestHandler):
    """Serves JPEG or PNG based on path; supports configurable failures."""

    server: "StubServer"

    def do_GET(self):  # pylint: disable=invalid-name
        """Handle a GET request, tracking counts and honoring failure paths."""
        # Track request count per path
        self.server.request_counts[self.path] = (
            self.server.request_counts.get(self.path, 0) + 1
        )

        if self.server.fail_paths and self.path in self.server.fail_paths:
            self.send_response(500)
            self.end_headers()
            return

        # Serve custom content for specific paths
        if self.server.custom_content and self.path in self.server.custom_content:
            body = self.server.custom_content[self.path]
            ctype = "application/octet-stream"
        elif self.path.endswith(".jpeg") or self.path.endswith(".jpg"):
            body = JPEG_BYTES
            ctype = "image/jpeg"
        else:
            body = PNG_BYTES
            ctype = "image/png"

        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):  # pylint: disable=redefined-builtin
        """Suppress stderr noise from the HTTP server."""


class StubServer:
    """Threaded HTTP server for download tests."""

    fail_paths: set[str] = set()
    custom_content: dict[str, bytes] = {}
    request_counts: dict[str, int] = {}

    def __init__(self) -> None:
        """Initialize instance state (populated by :meth:`start`)."""
        self.httpd = None
        self.port = 0

    @classmethod
    def start(cls) -> "StubServer":
        """Start a server on a random localhost port and return it."""
        server = cls()
        httpd = HTTPServer(("127.0.0.1", 0), StubHandler)
        httpd.fail_paths = server.fail_paths
        httpd.custom_content = server.custom_content
        httpd.request_counts = server.request_counts
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        server.httpd = httpd
        server.port = httpd.server_address[1]
        return server

    @property
    def base_url(self) -> str:
        """Base URL for constructing test URLs."""
        return f"http://127.0.0.1:{self.port}"

    def stop(self) -> None:
        """Shut down the server thread."""
        self.httpd.shutdown()
