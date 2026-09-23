import asyncio
from anyio import CancelScope
from fastapi import WebSocket, WebSocketDisconnect

def register_routes(app, hub, mock_hub):
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
