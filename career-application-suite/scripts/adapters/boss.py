#!/usr/bin/env python3
"""Read-only BOSS CLI adapter."""

from __future__ import annotations

import json
import subprocess
from typing import Any


def authenticated() -> bool:
    completed = subprocess.run(
        ["boss", "status", "--json"],
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        return False
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError:
        return False
    return bool(payload.get("authenticated") or payload.get("data", {}).get("authenticated"))


def search(keyword: str, extra_args: list[str] | None = None) -> list[dict[str, Any]]:
    if not authenticated():
        raise RuntimeError("BOSS authentication is required; run `boss login` locally")
    command = ["boss", "search", keyword, "--json", *(extra_args or [])]
    completed = subprocess.run(command, check=True, capture_output=True, text=True)
    payload = json.loads(completed.stdout)
    data = payload.get("data", payload)
    return data.get("jobList") or data.get("jobs") or []


def applied(page: int = 1) -> list[dict[str, Any]]:
    if not authenticated():
        raise RuntimeError("BOSS authentication is required; run `boss login` locally")
    completed = subprocess.run(
        ["boss", "applied", "-p", str(page), "--json"],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(completed.stdout)
    data = payload.get("data", payload)
    return data.get("jobList") or data.get("jobs") or []
