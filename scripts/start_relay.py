#!/usr/bin/env python3
"""
Local webhook relay: receives Cortex webhooks and forwards to OpenClaw sink.

Listens on RELAY_PORT (default 8421), forwards to OpenClaw ingress.
"""
from __future__ import annotations

import json
import os
import sys
from http.server import HTTPServer, BaseHTTPRequestHandler

from openclaw_sink import OpenClawSink

RELAY_PORT = int(os.environ.get("RELAY_PORT", "8421"))


class RelayHandler(BaseHTTPRequestHandler):
    """Handle incoming Cortex webhook POSTs."""

    sink: OpenClawSink  # set by factory

    def do_GET(self):
        if self.path == "/health":
            self._json_response(200, {"status": "ok", "relay": True})
        else:
            self._json_response(404, {"error": "not found"})

    def do_POST(self):
        if self.path != "/webhook":
            self._json_response(404, {"error": "not found"})
            return

        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)

        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            self._json_response(400, {"error": "invalid JSON"})
            return

        # Forward to OpenClaw sink
        ok, detail = self.sink.send(payload)
        if ok:
            self._json_response(200, {"forwarded": True})
        else:
            self._json_response(502, {"forwarded": False, "detail": detail})

    def _json_response(self, status: int, data: dict):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def log_message(self, format, *args):
        # Compact logging
        print(f"[relay] {args[0]} {args[1]}")


def main():
    ingress_url = os.environ.get("OPENCLAW_INGRESS_URL", "")

    sink = OpenClawSink(ingress_url=ingress_url)
    RelayHandler.sink = sink

    server = HTTPServer(("127.0.0.1", RELAY_PORT), RelayHandler)
    print(f"Relay listening on 127.0.0.1:{RELAY_PORT}")
    print(f"OpenClaw sink: {ingress_url or '(disabled, logging only)'}")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nRelay stopped.")
        server.server_close()


if __name__ == "__main__":
    main()
