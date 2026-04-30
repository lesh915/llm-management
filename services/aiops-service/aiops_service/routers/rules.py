"""Automation rule CRUD endpoints (FR-D4)."""
from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..rules import DEFAULT_RULES

router = APIRouter()
Db = Annotated[AsyncSession, Depends(get_db)]

# In-memory store for demo; production should use a DB table
_custom_rules: list[dict] = []


@router.get("")
async def list_rules():
    """등록된 자동화 규칙 목록 (기본 + 커스텀)."""
    all_rules = [*DEFAULT_RULES, *_custom_rules]
    return {"data": all_rules, "meta": {"total": len(all_rules)}}


@router.post("", status_code=201)
async def create_rule(body: dict):
    """커스텀 자동화 규칙 등록 (FR-D4)."""
    required = {"name", "condition", "action"}
    if not required.issubset(body.keys()):
        raise HTTPException(422, f"Missing fields: {required - body.keys()}")

    rule = {
        "id": str(uuid.uuid4()),
        "enabled": body.get("enabled", True),
        "requires_approval": body.get("requires_approval", True),
        **{k: body[k] for k in ("name", "condition", "action")},
    }
    _custom_rules.append(rule)
    return {"data": rule}


@router.patch("/{rule_id}")
async def update_rule(rule_id: str, body: dict):
    """규칙 활성화/비활성화 또는 설정 변경."""
    rule = next((r for r in _custom_rules if r["id"] == rule_id), None)
    # Allow patching default rules' enabled flag
    default = next((r for r in DEFAULT_RULES if r["id"] == rule_id), None)
    target = rule or default
    if not target:
        raise HTTPException(404, f"Rule '{rule_id}' not found")

    for k in ("enabled", "requires_approval", "action", "condition", "name"):
        if k in body:
            target[k] = body[k]

    return {"data": target}


@router.delete("/{rule_id}", status_code=204)
async def delete_rule(rule_id: str):
    """커스텀 규칙만 삭제 가능 (기본 규칙은 비활성화 권장)."""
    idx = next((i for i, r in enumerate(_custom_rules) if r["id"] == rule_id), None)
    if idx is None:
        raise HTTPException(404, "Custom rule not found (default rules cannot be deleted)")
    _custom_rules.pop(idx)
