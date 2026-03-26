"""
Command router: maps WeChat messages to Cortex API calls.

Used by the OpenClaw agent to dispatch user inputs.
"""
from __future__ import annotations

import json
import re
import urllib.request
from dataclasses import dataclass
from typing import Optional


@dataclass
class CortexClient:
    """Minimal HTTP client for the Cortex API."""

    base_url: str = "http://127.0.0.1:8420/api/v1"
    workspace: str = "default"
    timeout: int = 15

    def _request(self, method: str, path: str, body: dict | None = None) -> dict:
        url = f"{self.base_url}{path}"
        data = json.dumps(body).encode() if body else None
        req = urllib.request.Request(
            url, data=data, method=method,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            return json.loads(resp.read())

    def ingest_url(self, url: str, annotation: str = "") -> dict:
        body: dict = {
            "url": url,
            "source": "wechat",
            "workspace_id": self.workspace,
        }
        if annotation:
            body["user_annotation"] = annotation
        return self._request("POST", "/events/ingest", body)

    def ingest_text(self, text: str) -> dict:
        return self._request("POST", "/events/ingest", {
            "content": text,
            "source": "wechat",
            "raw_input_type": "text",
            "workspace_id": self.workspace,
        })

    def get_notifications(self, status: str = "") -> list[dict]:
        qs = f"?status={status}" if status else ""
        return self._request("GET", f"/notifications{qs}")

    def notification_action(self, nid: str, action: str) -> dict:
        return self._request("POST", f"/notifications/{nid}/{action}")

    def signal_feedback(self, signal_id: str, verdict: str, note: str = "") -> dict:
        body: dict = {"verdict": verdict}
        if note:
            body["note"] = note
        return self._request("POST", f"/signals/{signal_id}/feedback", body)

    def health(self) -> dict:
        return self._request("GET", "/health")


# URL regex
_URL_RE = re.compile(r"https?://\S+")

# Command patterns
_COMMANDS = {
    "inbox": "inbox",
    "收件箱": "inbox",
    "通知": "inbox",
}

_ACTION_RE = re.compile(
    r"^(read|ack|dismiss|useful|not_useful|wrong|save_for_later)\s+(\S+)$",
    re.IGNORECASE,
)


@dataclass
class RouterResult:
    action: str
    data: dict
    summary: str


def route(text: str, client: CortexClient) -> RouterResult:
    """Route a user message to the appropriate Cortex API call."""
    text = text.strip()

    # Check command keywords
    lower = text.lower()
    if lower in _COMMANDS:
        notifications = client.get_notifications()
        count = len(notifications)
        if count == 0:
            return RouterResult("inbox", {}, "No pending notifications.")
        lines = []
        for n in notifications[:10]:
            status = n.get("status", "?")
            nid = n["id"][:8]
            lines.append(f"[{status}] {nid} | {n['title']}")
        summary = f"{count} notification(s):\n" + "\n".join(lines)
        return RouterResult("inbox", {"notifications": notifications}, summary)

    # Check action commands (read/ack/dismiss/feedback)
    m = _ACTION_RE.match(text)
    if m:
        action, target_id = m.group(1).lower(), m.group(2)
        if action in ("read", "ack", "dismiss"):
            result = client.notification_action(target_id, action)
            return RouterResult(
                action, result,
                f"Notification {target_id[:8]} marked as {action}.",
            )
        else:
            # Signal feedback
            result = client.signal_feedback(target_id, action)
            return RouterResult(
                "feedback", result,
                f"Feedback '{action}' submitted for signal {target_id[:8]}.",
            )

    # Check for URL
    url_match = _URL_RE.search(text)
    if url_match:
        url = url_match.group(0)
        annotation = text.replace(url, "").strip()
        result = client.ingest_url(url, annotation)
        return RouterResult(
            "ingest_url", result,
            f"Link ingested: {result.get('title', url[:40])}",
        )

    # Default: ingest as text note
    result = client.ingest_text(text)
    return RouterResult(
        "ingest_text", result,
        f"Note saved: {result.get('title', text[:30])}",
    )
