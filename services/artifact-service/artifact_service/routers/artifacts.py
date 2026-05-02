"""Agent & Artifact CRUD + dependency/impact analysis endpoints (FR-A1~A4)."""
from __future__ import annotations

import uuid
from typing import Annotated

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared_types.models import Agent, AgentArtifact, ModelVariant
from shared_types.schemas import ArtifactCreate
from ..database import get_db
from ..analyzers.dependency_analyzer import ArtifactDependencyAnalyzer, CompatibilityLevel

router = APIRouter()
Db = Annotated[AsyncSession, Depends(get_db)]
_analyzer = ArtifactDependencyAnalyzer()

import os
MODEL_REGISTRY_URL = os.environ.get("MODEL_REGISTRY_URL", "http://localhost:8002")


# ── Agents ────────────────────────────────────────────────────────────────────

@router.post("/agents", status_code=status.HTTP_201_CREATED)
async def create_agent(body: dict, db: Db):
    agent = Agent(
        name=body["name"],
        description=body.get("description"),
        owner=body.get("owner", "unknown"),
    )
    db.add(agent)
    await db.commit()
    await db.refresh(agent)
    return {"data": _ser_agent(agent)}


@router.get("/agents")
async def list_agents(db: Db):
    rows = (await db.execute(select(Agent))).scalars().all()
    return {"data": [_ser_agent(r) for r in rows], "meta": {"total": len(rows)}}


@router.get("/agents/{agent_id}")
async def get_agent(agent_id: str, db: Db):
    a = await db.get(Agent, uuid.UUID(agent_id))
    if not a:
        raise HTTPException(404, "Agent not found")
    return {"data": _ser_agent(a)}


# ── Artifacts ─────────────────────────────────────────────────────────────────

@router.post("/agents/{agent_id}/artifacts", status_code=status.HTTP_201_CREATED)
async def register_artifact(agent_id: str, body: ArtifactCreate, db: Db):
    """Register an artifact and auto-analyze dependencies (FR-A1)."""
    a = await db.get(Agent, uuid.UUID(agent_id))
    if not a:
        raise HTTPException(404, "Agent not found")

    deps = _analyzer.analyze(body.type, body.content)

    artifact = AgentArtifact(
        agent_id=uuid.UUID(agent_id),
        type=body.type,
        content=body.content,
        model_requirements=[d.to_dict() for d in deps],
    )
    db.add(artifact)
    await db.commit()
    await db.refresh(artifact)
    return {"data": _ser_artifact(artifact)}


@router.get("/agents/{agent_id}/artifacts")
async def list_artifacts(agent_id: str, db: Db):
    stmt = select(AgentArtifact).where(AgentArtifact.agent_id == uuid.UUID(agent_id))
    rows = (await db.execute(stmt)).scalars().all()
    return {"data": [_ser_artifact(r) for r in rows]}


@router.get("/artifacts/{artifact_id}")
async def get_artifact(artifact_id: str, db: Db):
    art = await db.get(AgentArtifact, uuid.UUID(artifact_id))
    if not art:
        raise HTTPException(404, "Artifact not found")
    return {"data": _ser_artifact(art)}


@router.post("/artifacts/{artifact_id}/analyze")
async def analyze_artifact(artifact_id: str, db: Db):
    """Re-run dependency analysis on an existing artifact (FR-A2)."""
    art = await db.get(AgentArtifact, uuid.UUID(artifact_id))
    if not art:
        raise HTTPException(404, "Artifact not found")

    deps = _analyzer.analyze(art.type, art.content)
    art.model_requirements = [d.to_dict() for d in deps]
    await db.commit()
    return {"data": {"artifact_id": artifact_id, "dependencies": art.model_requirements}}


@router.get("/artifacts/{artifact_id}/impact")
async def impact_analysis(
    artifact_id: str,
    source_model_id: str,
    target_model_id: str,
    db: Db,
):
    """Model switch impact analysis (FR-A3)."""
    art = await db.get(AgentArtifact, uuid.UUID(artifact_id))
    if not art:
        raise HTTPException(404, "Artifact not found")

    # Fetch model capabilities from model-registry-service
    source_caps, target_caps = await _fetch_capabilities(
        [source_model_id, target_model_id]
    )

    from ..analyzers.dependency_analyzer import ModelDependency
    deps = [ModelDependency(**d) for d in (art.model_requirements or [])]

    source_compat = _analyzer.check_compatibility(deps, source_caps)
    target_compat = _analyzer.check_compatibility(deps, target_caps)

    # Identify features lost in the transition
    issues = []
    for dep in deps:
        src_ok = _has_feature(source_caps, dep.feature)
        tgt_ok = _has_feature(target_caps, dep.feature)
        if src_ok and not tgt_ok:
            issues.append({
                "feature": dep.feature,
                "required": dep.required,
                "description": dep.description,
                "severity": "critical" if dep.required else "warning",
                "recommendation": f"'{dep.feature}' 기능이 {target_model_id}에서 지원되지 않습니다. "
                                  "해당 기능 의존성을 제거하거나 대체 방법을 사용하세요.",
            })

    return {
        "data": {
            "artifact_id": artifact_id,
            "source_model": {"id": source_model_id, "compatibility": source_compat},
            "target_model": {"id": target_model_id, "compatibility": target_compat},
            "issues": issues,
            "safe_to_switch": len([i for i in issues if i["severity"] == "critical"]) == 0,
        }
    }


@router.post("/artifacts/{artifact_id}/variants", status_code=status.HTTP_201_CREATED)
async def create_variant(artifact_id: str, body: dict, db: Db):
    """Register a model-optimized variant of an artifact (FR-A4)."""
    art = await db.get(AgentArtifact, uuid.UUID(artifact_id))
    if not art:
        raise HTTPException(404, "Artifact not found")

    variant = ModelVariant(
        artifact_id=uuid.UUID(artifact_id),
        model_id=body["model_id"],
        content=body["content"],
        notes=body.get("notes"),
    )
    db.add(variant)
    await db.commit()
    await db.refresh(variant)
    return {
        "data": {
            "id": str(variant.id),
            "artifact_id": artifact_id,
            "model_id": variant.model_id,
            "notes": variant.notes,
            "created_at": variant.created_at.isoformat() if variant.created_at else None,
        }
    }


@router.get("/artifacts/{artifact_id}/variants")
async def list_variants(artifact_id: str, db: Db):
    stmt = select(ModelVariant).where(ModelVariant.artifact_id == uuid.UUID(artifact_id))
    rows = (await db.execute(stmt)).scalars().all()
    return {
        "data": [
            {"id": str(r.id), "model_id": r.model_id, "notes": r.notes,
             "created_at": r.created_at.isoformat() if r.created_at else None}
            for r in rows
        ]
    }


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _fetch_capabilities(model_ids: list[str]) -> list[dict]:
    async with httpx.AsyncClient(timeout=10.0) as client:
        caps = []
        for mid in model_ids:
            try:
                r = await client.get(f"{MODEL_REGISTRY_URL}/models/{mid}")
                r.raise_for_status()
                caps.append(r.json()["data"]["capabilities"])
            except Exception:
                caps.append({})
        return caps


def _has_feature(caps: dict, feature: str) -> bool:
    feature_map = {
        "tool_use": "tool_use",
        "tool_choice_required": "tool_use",
        "parallel_tool_calls": "parallel_tool_calls",
        "vision": "vision",
        "structured_output": "structured_output",
    }
    key = feature_map.get(feature)
    if not key:
        return True  # Unknown features assumed OK
    return bool(caps.get(key, False))


def _ser_agent(a: Agent) -> dict:
    return {
        "id": str(a.id), "name": a.name,
        "description": a.description, "owner": a.owner,
        "created_at": a.created_at.isoformat() if a.created_at else None,
    }


def _ser_artifact(art: AgentArtifact) -> dict:
    return {
        "id": str(art.id), "agent_id": str(art.agent_id),
        "type": art.type, "version": art.version,
        "content": art.content,
        "model_requirements": art.model_requirements or [],
        "created_at": art.created_at.isoformat() if art.created_at else None,
    }
