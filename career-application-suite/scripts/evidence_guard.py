#!/usr/bin/env python3
"""Validate resume claim-to-evidence mappings."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


VALID_SOURCE_TYPES = {"base", "overlay"}


def validate_mapping(data: dict[str, Any]) -> dict[str, Any]:
    claims = data.get("claims")
    if not isinstance(claims, list) or not claims:
        return {
            "passed": False,
            "errors": ["mapping must contain a non-empty claims list"],
            "claim_count": 0,
        }
    errors: list[str] = []
    warnings: list[str] = []
    seen_claims: set[str] = set()
    for index, item in enumerate(claims, start=1):
        prefix = f"claim[{index}]"
        claim = str(item.get("claim") or "").strip()
        source_type = str(item.get("source_type") or "").strip().lower()
        source_ref = str(item.get("source_ref") or "").strip()
        supported = item.get("supported")
        if not claim:
            errors.append(f"{prefix}: missing claim")
        if source_type not in VALID_SOURCE_TYPES:
            errors.append(f"{prefix}: source_type must be base or overlay")
        if not source_ref:
            errors.append(f"{prefix}: missing source_ref")
        if supported is not True:
            errors.append(f"{prefix}: claim is not explicitly supported")
        normalized = " ".join(claim.lower().split())
        if normalized in seen_claims:
            warnings.append(f"{prefix}: duplicate claim")
        seen_claims.add(normalized)
    return {
        "passed": not errors,
        "claim_count": len(claims),
        "errors": errors,
        "warnings": warnings,
    }


def validate_file(path: str | Path) -> dict[str, Any]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return validate_mapping(data)
