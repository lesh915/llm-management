"""comparison-engine 프록시 라우터."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response, WebSocket

from ..auth import get_current_user
from ..config import COMPARISON_ENGINE_URL
from ..proxy import reverse_proxy

router = APIRouter()
_auth = Depends(get_current_user)


@router.api_route("/tasks", methods=["GET", "POST"])
@router.api_route("/tasks/{path:path}", methods=["GET", "POST", "PATCH", "DELETE"])
async def proxy_tasks(request: Request, path: str = "", _: dict = _auth) -> Response:
    prefix = "tasks"
    full_path = f"{prefix}/{path}" if path else prefix
    return await reverse_proxy(request, COMPARISON_ENGINE_URL, full_path)


@router.api_route("/datasets", methods=["GET", "POST"])
@router.api_route("/datasets/{path:path}", methods=["GET", "POST", "PATCH", "DELETE"])
async def proxy_datasets(request: Request, path: str = "", _: dict = _auth) -> Response:
    prefix = "datasets"
    full_path = f"{prefix}/{path}" if path else prefix
    return await reverse_proxy(request, COMPARISON_ENGINE_URL, full_path)


@router.websocket("/ws/tasks/{task_id}/progress")
async def ws_proxy_tasks_progress(websocket: WebSocket, task_id: str):
    import websockets
    from websockets.exceptions import ConnectionClosed
    
    await websocket.accept()
    
    # http://... -> ws://...
    ws_url = COMPARISON_ENGINE_URL.replace("http://", "ws://").replace("https://", "wss://")
    target_url = f"{ws_url}/ws/tasks/{task_id}/progress"
    
    try:
        async with websockets.connect(target_url) as remote_ws:
            # We only need one-way proxy (backend -> frontend) for progress
            while True:
                message = await remote_ws.recv()
                await websocket.send_text(message)
    except ConnectionClosed:
        pass
    except Exception as e:
        try:
            await websocket.send_json({"type": "error", "detail": str(e)})
        except Exception:
            pass
    finally:
        try:
            await websocket.close()
        except Exception:
            pass
