"""WebSocket endpoint for real-time task progress (FR-C2)."""
from __future__ import annotations

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from ..progress import subscribe_progress

router = APIRouter()


@router.websocket("/ws/tasks/{task_id}/progress")
async def task_progress_ws(websocket: WebSocket, task_id: str):
    """
    Subscribe to real-time progress events for a comparison task.

    Messages pushed to the client:
        {"task_id": str, "model_id": str, "done": int,
         "total": int, "pct": float, "latency_ms": float}

    Connection closes automatically when all models finish.
    """
    await websocket.accept()
    try:
        async for event in subscribe_progress(task_id):
            await websocket.send_json(event)
            # All models done: close cleanly
            all_done = event.get("done") == event.get("total") and event.get("total", 0) > 0
            if all_done:
                await websocket.send_json({"type": "done", "task_id": task_id})
                break
    except WebSocketDisconnect:
        pass
    except Exception as exc:
        try:
            await websocket.send_json({"type": "error", "detail": str(exc)})
        except Exception:
            pass
    finally:
        try:
            await websocket.close()
        except Exception:
            pass
