"""Run the read-only CSV dashboard. This module never imports the motor SDK."""
import argparse
import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
import sys

if not __package__:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from src.dashboard.settings import Settings, DEFAULT_CONFIG, ROOT
    from src.dashboard.source_manager import SourceManager
    from src.dashboard.stream import TelemetryHub
    from src.dashboard.routes import register_routes
    from src.dashboard.mock_source import MockSource
else:
    from .settings import Settings, DEFAULT_CONFIG, ROOT
    from .source_manager import SourceManager
    from .stream import TelemetryHub
    from .routes import register_routes
    from .mock_source import MockSource

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse


def create_app(settings=None, dist=None):
    settings = settings or Settings.load()
    manager = SourceManager(settings)
    hub = TelemetryHub(manager.snapshot(), settings.subscriber_queue_size)

    mock_source = MockSource(hub.snapshot["serverSessionId"])
    mock_hub = TelemetryHub(mock_source.snapshot(), settings.subscriber_queue_size)

    @asynccontextmanager
    async def lifespan(app):
        stop = asyncio.Event()

        async def watch():
            while not stop.is_set():
                snapshot, messages = await asyncio.to_thread(manager.tick)
                hub.publish(snapshot, messages)
                try:
                    await asyncio.wait_for(stop.wait(), timeout=settings.poll_interval_sec)
                except asyncio.TimeoutError:
                    pass

        async def simulate():
            loop = asyncio.get_running_loop()
            started = loop.time()
            while not stop.is_set():
                snapshot, messages = mock_source.advance(60000 + round((loop.time() - started) * 1000))
                mock_hub.publish(snapshot, messages)
                try:
                    await asyncio.wait_for(stop.wait(), timeout=mock_source.interval_sec)
                except asyncio.TimeoutError:
                    pass

        workers = [asyncio.create_task(watch()), asyncio.create_task(simulate())]
        try:
            yield
        finally:
            stop.set()
            await asyncio.gather(*workers)

    app = FastAPI(title="Motor CSV Dashboard", lifespan=lifespan)
    app.state.hub = hub
    app.state.manager = manager
    app.state.mock_hub = mock_hub
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
        if path and path not in {"overview", "motors", "trends", "alerts", "logs", "settings"}:
            raise HTTPException(404)
        index = dist_path / "index.html"
        if index.exists():
            return FileResponse(index)
        return HTMLResponse("<h1>Motor CSV Dashboard</h1><p>Frontend build required: cd frontend &amp;&amp; npm install &amp;&amp; npm run build</p><p>API: <a href='/api/health'>/api/health</a></p>", status_code=503)

    return app


if __name__ == "__main__":
    import uvicorn
    parser = argparse.ArgumentParser(description="Read-only motor CSV dashboard")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    args = parser.parse_args()
    configuration = Settings.load(args.config)
    uvicorn.run(create_app(configuration), host=configuration.host, port=configuration.port, workers=1)
