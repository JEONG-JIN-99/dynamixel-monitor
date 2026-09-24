"""Dashboard server. Motor SDK access is isolated in an explicitly started worker."""
import argparse
import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
import sys

if not __package__:
    from bootstrap import load_package
    __package__ = load_package()
from .settings import Settings, DEFAULT_CONFIG, ROOT
from .source_manager import SourceManager
from .stream import TelemetryHub
from .routes import register_routes

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from starlette.middleware.gzip import GZipMiddleware


def create_app(settings=None, dist=None, mock_prehistory_ms=None):
    settings = settings or Settings.load()
    manager = SourceManager(settings)
    hub = TelemetryHub(manager.snapshot(), settings.subscriber_queue_size)

    idle = manager.snapshot()
    idle["system"] = {**idle["system"], "sourceMode":"mock"}
    mock_hub = TelemetryHub(idle, settings.subscriber_queue_size)

    @asynccontextmanager
    async def lifespan(app):
        stop = asyncio.Event()
        controller = app.state.controller
        await controller.open()
        async def watch():
            while not stop.is_set():
                snapshot, messages = await asyncio.to_thread(manager.tick)
                hub.publish(snapshot, messages)
                try:
                    await asyncio.wait_for(stop.wait(), settings.poll_interval_sec)
                except asyncio.TimeoutError:
                    pass
        worker = asyncio.create_task(watch())
        try:
            if mock_prehistory_ms is not None:
                from .experiment.configuration import load_config
                await asyncio.to_thread(controller.repository.save_config, "mock", load_config().snapshot())
                await controller.start(controller.repository.saved()["id"], prehistory=mock_prehistory_ms)
                while app.state.mock_archive is None or not mock_hub.snapshot["latest"]:
                    if controller.task.done():
                        raise RuntimeError(controller.current.get("error"))
                    await asyncio.sleep(.01)
            yield
        finally:
            await controller.close()
            stop.set()
            await worker

    app = FastAPI(title="Motor Dashboard", lifespan=lifespan)
    app.add_middleware(GZipMiddleware, minimum_size=4096, compresslevel=1)
    app.state.hub = hub
    app.state.manager = manager
    app.state.mock_hub = mock_hub
    app.state.source_manager = manager
    app.state.mock_archive = None
    app.state.archive_error = None
    from .control import ExperimentController
    app.state.controller = ExperimentController(settings, mock_hub, app)
    register_routes(app, hub, mock_hub)
    dist_path = Path(dist) if dist else ROOT / "frontend" / "dist"

    @app.get("/{path:path}", include_in_schema=False)
    async def frontend(path: str):
        if path.startswith(("api/", "ws/")) or path in {"api", "ws"}:
            raise HTTPException(404)
        target = (dist_path / path).resolve()
        if not target.is_relative_to(dist_path.resolve()):
            raise HTTPException(404)
        if target.is_file():
            return FileResponse(target)
        if path and not path.startswith("logs/") and path not in {"overview", "control", "motors", "trends", "alerts", "logs", "settings"}:
            raise HTTPException(404)
        index = dist_path / "index.html"
        if index.exists():
            return FileResponse(index)
        return HTMLResponse("<h1>Motor CSV Dashboard</h1><p>Frontend build required: cd frontend &amp;&amp; npm install &amp;&amp; npm run build</p><p>API: <a href='/api/health'>/api/health</a></p>", status_code=503)

    return app


if __name__ == "__main__":
    import uvicorn
    parser = argparse.ArgumentParser(description="Motor dashboard and experiment control")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    args = parser.parse_args()
    configuration = Settings.load(args.config)
    uvicorn.run(create_app(configuration), host=configuration.host, port=configuration.port, workers=1)
