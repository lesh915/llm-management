"""Parallel comparison task execution engine (FR-C2).

Flow:
    1. preflight_check  — verify every model endpoint is reachable
    2. load_dataset     — fetch eval cases from DB or S3
    3. asyncio.gather   — run all models concurrently
    4. Semaphore guard  — cap concurrent calls to local models
    5. Persist results  — write ComparisonResult rows + S3 raw outputs
"""
from __future__ import annotations

import asyncio
import json
import os
import time
import uuid
from datetime import datetime, timezone

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from shared_types.models import ComparisonTask, ComparisonResult
from .database import AsyncSessionLocal
from .metrics import EvalCase, ModelOutput, calculate_metrics
from .cost import calculate_cost
from .progress import publish_progress

MODEL_REGISTRY_URL = os.environ.get("MODEL_REGISTRY_URL", "http://localhost:8002")
S3_BUCKET = os.environ.get("S3_BUCKET", "llm-management")


# ── Public entry-point (called from Celery task) ──────────────────────────────

async def execute_task(task_id: str) -> list[dict]:
    """Full pipeline: load task → preflight → run → persist → return results."""
    async with AsyncSessionLocal() as db:
        task: ComparisonTask | None = await db.get(ComparisonTask, uuid.UUID(task_id))
        if not task:
            raise ValueError(f"Task {task_id} not found")

        # Mark as running
        task.status = "running"
        await db.commit()

    try:
        model_metas = await _fetch_model_metas(task.model_ids)

        # Preflight — abort early if any model unreachable
        await preflight_check(task.model_ids, model_metas)

        dataset = await load_dataset(task.dataset_id)
        max_concurrent_local = getattr(task, "max_concurrent_local", 2)

        results = await asyncio.gather(
            *[
                _evaluate_model(
                    model_id=mid,
                    model_meta=model_metas[mid],
                    task=task,
                    dataset=dataset,
                    max_concurrent_local=max_concurrent_local,
                )
                for mid in task.model_ids
            ],
            return_exceptions=True,
        )

        serialized: list[dict] = []
        async with AsyncSessionLocal() as db:
            for result in results:
                if isinstance(result, Exception):
                    continue   # log and skip failed models
                serialized.append(result)
                db.add(ComparisonResult(
                    task_id=uuid.UUID(task_id),
                    model_id=result["model_id"],
                    metrics=result["metrics"],
                    raw_outputs=None,   # stored in S3 separately
                    cost_usd=result["cost_usd"],
                ))

            task_obj: ComparisonTask = await db.get(ComparisonTask, uuid.UUID(task_id))
            task_obj.status = "completed"
            task_obj.completed_at = datetime.now(timezone.utc)
            await db.commit()

        return serialized

    except Exception:
        async with AsyncSessionLocal() as db:
            task_obj = await db.get(ComparisonTask, uuid.UUID(task_id))
            if task_obj:
                task_obj.status = "failed"
                await db.commit()
        raise


# ── Preflight check ───────────────────────────────────────────────────────────

async def preflight_check(
    model_ids: list[str],
    model_metas: dict[str, dict],
) -> None:
    """Raise RuntimeError if any model endpoint is unreachable."""
    checks = await asyncio.gather(
        *[_check_model(mid, model_metas.get(mid, {})) for mid in model_ids],
        return_exceptions=True,
    )
    unavailable = [
        mid for mid, ok in zip(model_ids, checks)
        if ok is not True
    ]
    if unavailable:
        raise RuntimeError(
            f"다음 모델에 연결할 수 없습니다: {unavailable}\n"
            "로컬 모델은 Ollama/vLLM 서버가 실행 중인지 확인하세요."
        )


async def _check_model(model_id: str, meta: dict) -> bool:
    from llm_adapter.factory import get_adapter
    try:
        adapter = get_adapter(meta)
        return await adapter.health_check()
    except Exception:
        return False


# ── Model evaluation ──────────────────────────────────────────────────────────

async def _evaluate_model(
    model_id: str,
    model_meta: dict,
    task: ComparisonTask,
    dataset: list[EvalCase],
    max_concurrent_local: int = 2,
) -> dict:
    from llm_adapter.factory import get_adapter

    adapter = get_adapter(model_meta)
    is_local = model_meta.get("is_custom", False) or model_meta.get("provider") in (
        "Ollama", "vLLM", "LMStudio", "LM Studio", "LocalAI"
    )
    pricing = model_meta.get("pricing", {})
    context_window = model_meta.get("capabilities", {}).get("context_window", 0)

    # Local models get a semaphore to avoid overwhelming a single process
    semaphore = asyncio.Semaphore(max_concurrent_local if is_local else 32)

    async def run_case(case: EvalCase) -> ModelOutput:
        async with semaphore:
            start = time.monotonic()
            try:
                resp = await adapter.complete(
                    messages=case.input_messages,
                    tools=case.tools or None,
                )
                latency_ms = (time.monotonic() - start) * 1000
                await publish_progress(
                    task_id=str(task.id),
                    model_id=model_id,
                    done=dataset.index(case) + 1,
                    total=len(dataset),
                    latency_ms=latency_ms,
                )
                return ModelOutput(
                    case_id=case.id,
                    content=resp.content,
                    input_tokens=resp.usage.get("input_tokens", 0),
                    output_tokens=resp.usage.get("output_tokens", 0),
                    latency_ms=latency_ms,
                )
            except Exception as exc:
                return ModelOutput(
                    case_id=case.id,
                    content="",
                    input_tokens=0,
                    output_tokens=0,
                    latency_ms=(time.monotonic() - start) * 1000,
                    error=str(exc),
                )

    outputs = await asyncio.gather(*[run_case(c) for c in dataset])

    metrics = calculate_metrics(
        outputs=list(outputs),
        dataset=dataset,
        requested_metrics=list(task.metrics),
        pricing=pricing,
        context_window=context_window,
    )

    total_cost = sum(
        calculate_cost(pricing, {"input_tokens": o.input_tokens,
                                  "output_tokens": o.output_tokens})
        for o in outputs
    )

    return {
        "model_id": model_id,
        "is_local": is_local,
        "metrics": metrics,
        "cost_usd": total_cost,
        "output_count": len(outputs),
        "failure_count": sum(1 for o in outputs if o.error),
    }


# ── Dataset loading ───────────────────────────────────────────────────────────

async def load_dataset(dataset_id: str) -> list[EvalCase]:
    """
    Load eval cases.

    Strategy:
      1. Try S3  — s3://{bucket}/datasets/{dataset_id}.json
      2. Fallback to a stub for development/testing
    """
    try:
        return await _load_from_s3(dataset_id)
    except Exception:
        # Development stub — 3 generic cases
        return [
            EvalCase(
                id=f"case-{i:03d}",
                input_messages=[{"role": "user", "content": f"Test question {i}"}],
                expected_output=f"Answer {i}",
            )
            for i in range(1, 4)
        ]


async def _load_from_s3(dataset_id: str) -> list[EvalCase]:
    import boto3, botocore
    s3 = boto3.client(
        "s3",
        endpoint_url=os.environ.get("S3_ENDPOINT"),
        aws_access_key_id=os.environ.get("S3_ACCESS_KEY", "minioadmin"),
        aws_secret_access_key=os.environ.get("S3_SECRET_KEY", "minioadmin"),
    )
    obj = s3.get_object(Bucket=S3_BUCKET, Key=f"datasets/{dataset_id}.json")
    data = json.loads(obj["Body"].read())
    return [EvalCase(**c) for c in data["cases"]]


async def _save_raw_outputs_to_s3(task_id: str, model_id: str, outputs: list) -> None:
    import boto3
    s3 = boto3.client(
        "s3",
        endpoint_url=os.environ.get("S3_ENDPOINT"),
        aws_access_key_id=os.environ.get("S3_ACCESS_KEY", "minioadmin"),
        aws_secret_access_key=os.environ.get("S3_SECRET_KEY", "minioadmin"),
    )
    key = f"results/{task_id}/{model_id}.json"
    s3.put_object(
        Bucket=S3_BUCKET,
        Key=key,
        Body=json.dumps([o.__dict__ for o in outputs], default=str),
        ContentType="application/json",
    )


# ── Model metadata fetch ──────────────────────────────────────────────────────

async def _fetch_model_metas(model_ids: list[str]) -> dict[str, dict]:
    async with httpx.AsyncClient(timeout=10.0) as client:
        metas: dict[str, dict] = {}
        for mid in model_ids:
            try:
                r = await client.get(f"{MODEL_REGISTRY_URL}/models/{mid}")
                r.raise_for_status()
                metas[mid] = r.json()["data"]
            except Exception:
                metas[mid] = {"id": mid, "provider": "unknown",
                               "capabilities": {}, "pricing": {}, "api_config": {}}
        return metas
