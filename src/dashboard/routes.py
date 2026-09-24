import asyncio
from anyio import CancelScope
from fastapi import WebSocket, WebSocketDisconnect, HTTPException, Query, Request
from pathlib import Path
from urllib.parse import urlsplit
from .history_query import read_experiment_history
from fastapi.responses import JSONResponse

def register_routes(app, hub, mock_hub):
    controller = app.state.controller

    def check_origin(request):
        origin = request.headers.get("origin")
        if origin and urlsplit(origin).netloc != request.headers.get("host"):
            raise HTTPException(403, "다른 사이트에서 실행할 수 없습니다")

    @app.get("/api/control")
    async def control_state():
        return controller.state()

    @app.post("/api/control/config")
    async def save_config(request: Request):
        check_origin(request)
        try:
            body = await request.json()
            return await controller.save(body["source"],body["config"])
        except RuntimeError as exc:
            raise HTTPException(409,str(exc))
        except (ValueError,TypeError,KeyError) as exc:
            raise HTTPException(422,str(exc))

    @app.post("/api/control/start")
    async def start_run(request: Request):
        check_origin(request)
        try:
            body = await request.json()
            return await controller.start(body["configId"])
        except RuntimeError as exc:
            raise HTTPException(409,str(exc))
        except (ValueError,TypeError,KeyError) as exc:
            raise HTTPException(422,str(exc))

    @app.post("/api/control/stop")
    async def stop_run(request: Request):
        check_origin(request)
        try:
            body = await request.json()
            return await controller.stop(body["runId"])
        except RuntimeError as exc:
            raise HTTPException(409,str(exc))
        except (ValueError,TypeError,KeyError) as exc:
            raise HTTPException(422,str(exc))

    @app.get("/api/runs")
    async def runs(year: int | None = Query(None,ge=2000,le=9999),
                   month: int | None = Query(None,ge=1,le=12),day: int | None = Query(None,ge=1,le=31),
                   source: str | None = None,offset: int = Query(0,ge=0),limit: int = Query(100,ge=1,le=200)):
        if source and source not in {"mock","real"}:
            raise HTTPException(422,"실행 대상이 올바르지 않습니다")
        return await asyncio.to_thread(controller.repository.list,year,month,day,source,offset,limit)

    @app.get("/api/runs/{run_id}")
    async def run_detail(run_id: str):
        try:
            return await asyncio.to_thread(controller.repository.get,run_id)
        except KeyError:
            raise HTTPException(404,"실험 기록을 찾을 수 없습니다")

    @app.get("/api/runs/{run_id}/history")
    async def run_history(run_id: str,durationSec: int = 0):
        if durationSec not in {0,60,300,600,1800,3600}:
            raise HTTPException(422,"지원하지 않는 구간입니다")
        try:
            result = await asyncio.to_thread(controller.repository.history,run_id,durationSec)
            return await asyncio.to_thread(JSONResponse,result)
        except KeyError:
            raise HTTPException(404,"실험 기록을 찾을 수 없습니다")
        except (OSError,ValueError) as exc:
            raise HTTPException(409,"기록을 불러올 수 없습니다") from exc

    @app.get("/api/health")
    async def health():
        return {"ok": True, "schemaVersion": 1, "serverSessionId": hub.snapshot["serverSessionId"],
                **hub.snapshot["system"]}

    @app.get("/api/experiment")
    async def experiment():
        return {"experiment": hub.snapshot["experiment"], "system": hub.snapshot["system"]}

    @app.get("/api/motors")
    async def motors():
        return {"motors": hub.snapshot["metadata"]}

    @app.get("/api/history")
    async def history(runId: str, sourceSessionId: str, source: str = "csv",
                      durationSec: int = 60, afterSeq: int = Query(0, ge=0),
                      motorId: int | None = Query(None, ge=0, le=252), model: str | None = None):
        if source not in {"csv", "mock"} or durationSec not in {0, 60, 300, 600, 1800, 3600}:
            raise HTTPException(422, "Invalid source or duration")
        selected = mock_hub if source == "mock" else hub
        snapshot = selected.snapshot
        if runId != snapshot["runId"] or sourceSessionId != snapshot["sourceSessionId"]:
            raise HTTPException(409, "Experiment changed")
        try:
            if source == "mock":
                if not app.state.mock_archive or app.state.archive_error:
                    raise HTTPException(503, "History unavailable")
                result = await asyncio.to_thread(app.state.mock_archive.query, durationSec, afterSeq, motorId, model)
            else:
                if not snapshot["experiment"] or not snapshot["experiment"].get("csvPath"):
                    raise HTTPException(404, "No experiment history")
                manager = app.state.source_manager
                result = await asyncio.to_thread(read_experiment_history, snapshot, dict(manager.metadata),
                    (manager.settings.experiment_data_root if Path(snapshot["experiment"]["csvPath"]).is_relative_to(manager.settings.experiment_data_root) else manager.settings.data_root), durationSec, afterSeq, motorId, model,
                    manager.reader.identity if manager.reader else None)
        except FileNotFoundError:
            raise HTTPException(404, "History file not found")
        except (ValueError, OSError) as exc:
            raise HTTPException(409, "History changed or is unreadable") from exc
        if selected.snapshot["runId"] != runId or selected.snapshot["sourceSessionId"] != sourceSessionId:
            raise HTTPException(409, "Experiment changed")
        return await asyncio.to_thread(JSONResponse, result)

    @app.websocket("/ws/telemetry")
    async def telemetry(websocket: WebSocket):
        source = websocket.query_params.get("source", "csv")
        if source not in {"csv", "mock"}:
            await websocket.close(code=1008, reason="Unknown telemetry source")
            return
        selected_hub = mock_hub if source == "mock" else hub
        await websocket.accept()
        queue = selected_hub.subscribe()

        async def send():
            while True:
                await websocket.send_json(await queue.get())

        async def receive():
            # Observe disconnection even when there are no outgoing samples.
            while True:
                await websocket.receive_text()

        tasks = [asyncio.create_task(send()), asyncio.create_task(receive())]
        try:
            done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
            for task in done:
                task.result()
        except (WebSocketDisconnect, RuntimeError, asyncio.CancelledError):
            pass
        finally:
            selected_hub.unsubscribe(queue)
            for task in tasks:
                task.cancel()
            with CancelScope(shield=True):
                await asyncio.gather(*tasks, return_exceptions=True)
