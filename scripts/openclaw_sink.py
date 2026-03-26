"""
OpenClaw sink adapter: single module responsible for delivering messages
to OpenClaw / iLink downstream.

Default implementation: HTTP POST to OPENCLAW_INGRESS_URL.
If URL is empty, logs payload to stdout (dry-run mode).

When the actual iLink protocol is confirmed, only this module needs to change.
"""
from __future__ import annotations

import json
import urllib.request


class OpenClawSink:

    def __init__(self, ingress_url: str = "", timeout: int = 10):
        self._url = ingress_url
        self._timeout = timeout

    def send(self, payload: dict) -> tuple[bool, str]:
        """
        Forward a notification payload downstream.

        Returns (success: bool, detail: str).
        """
        if not self._url:
            # Dry-run: log to stdout
            print(f"[sink/dry-run] {json.dumps(payload, ensure_ascii=False)}")
            return True, "dry-run"

        try:
            data = json.dumps(payload).encode()
            req = urllib.request.Request(
                self._url,
                data=data,
                method="POST",
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                status = resp.status
                if 200 <= status < 300:
                    return True, f"status={status}"
                return False, f"status={status}"
        except Exception as e:
            return False, str(e)
