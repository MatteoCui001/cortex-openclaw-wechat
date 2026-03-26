#!/usr/bin/env python3
"""
Health check for local Cortex + relay stack.

Exit 0 = all healthy, exit 1 = something wrong.
"""
from __future__ import annotations

import json
import sys
import urllib.request
from pathlib import Path

SKILL_CONFIG_PATH = Path.home() / ".cortex" / "skill_config.yaml"


def _load_config() -> dict:
    """Load skill config (simple YAML-like parser for flat keys)."""
    if not SKILL_CONFIG_PATH.exists():
        return {}
    import re
    config = {}
    current_section = ""
    for line in SKILL_CONFIG_PATH.read_text().splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if not line.startswith(" ") and stripped.endswith(":"):
            current_section = stripped[:-1]
            continue
        m = re.match(r"\s+(\w+):\s*(.*)", line)
        if m:
            key = f"{current_section}.{m.group(1)}" if current_section else m.group(1)
            val = m.group(2).strip().strip('"').strip("'")
            config[key] = val
    return config


def _check_url(url: str, label: str, timeout: int = 5) -> bool:
    """GET a URL and check for 200."""
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read())
            print(f"  [ok] {label}: {data}")
            return True
    except Exception as e:
        print(f"  [!!] {label}: {e}")
        return False


def main() -> int:
    print("Cortex Doctor")
    print("=" * 40)

    config = _load_config()
    if not config:
        print(f"  [!!] No skill config at {SKILL_CONFIG_PATH}")
        print("  Run bootstrap first.")
        return 1

    base_url = config.get("cortex.base_url", "http://127.0.0.1:8420/api/v1")
    relay_port = config.get("relay.port", "8421")
    relay_enabled = config.get("relay.enabled", "false").lower() == "true"

    all_ok = True

    # Check Cortex health
    print("\n--- Cortex API ---")
    if not _check_url(f"{base_url}/health", "Health"):
        all_ok = False
    if not _check_url(f"{base_url}/ready", "Ready"):
        all_ok = False

    # Check relay if enabled
    if relay_enabled:
        print("\n--- Relay ---")
        if not _check_url(f"http://127.0.0.1:{relay_port}/health", "Relay"):
            all_ok = False
    else:
        print("\n--- Relay ---")
        print("  [--] Relay disabled in config")

    if all_ok:
        print("\nAll checks passed.")
        return 0
    else:
        print("\nSome checks failed.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
