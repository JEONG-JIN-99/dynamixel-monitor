"""One server-owned experiment lifecycle shared by every browser."""
import asyncio
import csv
import json
import math
import os
import subprocess
import sys
from pathlib import Path
from .experiment.configuration import load_config, ExperimentConfig
from .file_lock import FileLock, is_locked
from .mock_source import MockSource
from .history_archive import MockArchive
from .run_repository import RunRepository, ACTIVE, now_iso


class ExperimentController:
    def __init__(self, settings, hub, app):
        self.settings, self.hub, self.app = settings, hub, app
        self.repository = RunRepository(settings)
        self.command_lock = asyncio.Lock()
        self.owner = FileLock(settings.control_root / "controller.lock")
        self.current = None
        self.task = self.process = self.source = None
        self.stop_requested = False
        self.fixture = False

    @property
    def active(self):
        return bool(self.task and not self.task.done()) or bool(self.current and self.current["status"] in ACTIVE)

    def external_active(self):
        return is_locked(self.settings.manifest_path.with_suffix(".lock")) is not False

    async def open(self):
        self.owner.acquire()
        try:
            try:
                manifest=json.loads(self.settings.manifest_path.read_text(encoding="utf-8"))
            except (OSError,ValueError):
                manifest={}
            for meta in self.repository.list(limit=1000000)["runs"]:
                if meta["status"] not in ACTIVE:
                    continue
                if meta["source"] == "real" and manifest.get("runId") == meta["runId"] and self.external_active():
                    self.current=meta
                    self.stop_requested=bool(meta.get("stopRequestedAt"))
                    self.task=asyncio.create_task(self.monitor_existing_real())
                else:
                    self.summarize(meta)
                    self.repository.update(meta["runId"],status="interrupted",endedAt=now_iso(),
                                           stopReason="server_interrupted",error="실행이 중단되었습니다")
        except BaseException:
            self.owner.release()
            raise

    async def monitor_existing_real(self):
        try:
            while self.external_active():
                await asyncio.sleep(.1)
            await asyncio.sleep(.1)
            directory=self.repository.directory(self.current["runId"])
            result_path=directory/"result.json"
            result=json.loads(result_path.read_text(encoding="utf-8")) if result_path.exists() else {}
            self.current=await asyncio.to_thread(self.summarize,self.current)
            code=result.get("code")
            self.current=await asyncio.to_thread(self.repository.update,self.current["runId"],
                status={0:"completed",130:"interrupted"}.get(code,"interrupted" if code is None else "failed"),
                endedAt=now_iso(),completedCycles=result.get("completedCycles",self.current["completedCycles"]),
                stopReason="requested" if self.stop_requested else "cycles_completed" if code==0 else "server_interrupted",
                error=None if code==0 else "실행이 중단되었습니다")
        except Exception as exc:
            self.current=self.repository.update(self.current["runId"],status="failed",endedAt=now_iso(),error=str(exc))

    def summarize(self, meta):
        directory = self.repository.directory(meta["runId"])
        count = seq = elapsed = cycles = 0
        path = directory / "telemetry.csv"
        if path.exists():
            with path.open(encoding="utf-8-sig", newline="") as handle:
                for row in csv.DictReader(handle):
                    try:
                        if meta["source"] == "mock":
                            json.loads(row["registers"]); json.loads(row["diagnosis"])
                            seq, elapsed = int(row["seq"]), int(row["elapsedMs"])
                        else:
                            seq += 1
                            elapsed = round(float(row["Elapsed Time [s]"])*1000)
                            cycles = max(cycles, int(row["Cycle"])-1)
                        count += 1
                    except (ValueError, TypeError, KeyError):
                        break
        if meta["source"] == "mock":
            c=meta["config"]
            cycles=int(elapsed/(2*c["profile_duration_ms"]+1000*(c["top_dwell_sec"]+c["bottom_dwell_sec"])))
        changes = dict(rowCount=count,lastSeq=seq,elapsedMs=elapsed,completedCycles=cycles)
        if meta["source"] == "real":
            raw_path = directory / "motor_metadata.json"
            raw = json.loads(raw_path.read_text(encoding="utf-8")) if raw_path.exists() else {}
            changes["metadata"] = [{"id":meta["motorId"],"model":meta["motorModel"],
                "modelNumber":raw.get("model_number"),"firmware":raw.get("firmware_version"),
                "settings":raw.get("settings", {}),"simulated":False,
                "limits":{"current":None,"temperature":None,"voltageMin":None,"voltageMax":None}}]
        return self.repository.update(meta["runId"], **changes)

    def state(self):
        return {"saved":self.repository.saved(), "defaults":load_config().snapshot(),
                "run":self.current,"active":self.active,
                "externalActive":self.external_active() if not self.active else False}

    async def save(self, source, config):
        async with self.command_lock:
            if self.active or self.external_active():
                raise RuntimeError("실험 종료 후 설정을 저장하세요")
            await asyncio.to_thread(self.repository.save_config, source, config)
            return self.state()

    async def start(self, config_id, prehistory=None):
        async with self.command_lock:
            if self.active or (prehistory is None and self.external_active()):
                raise RuntimeError("이미 진행 중인 실험이 있습니다")
            saved = self.repository.saved()
            if not saved or saved["id"] != config_id:
                raise RuntimeError("설정을 저장하거나 최신 설정을 확인하세요")
            self.current = await asyncio.to_thread(self.repository.create, saved, self.hub.snapshot["serverSessionId"])
            self.stop_requested = False
            self.source = self.process = None
            if saved["source"] == "mock":
                self.app.state.mock_archive = None
                self.app.state.archive_error = None
                empty={**self.hub.snapshot,"runId":self.current["runId"],"sourceSessionId":self.current["sourceSessionId"],
                    "history":[],"latest":None,"metadata":[],"events":[],"seq":0,
                    "experiment":{**self.current,"csvPath":None,"metadataPath":None,"flushEveryRows":1},
                    "system":{**self.hub.snapshot["system"],"validity":"waiting","experimentStatus":"preparing","error":None,"writerActive":False}}
                self.hub.publish(empty,[{"type":"reset",**empty}])
            self.fixture = prehistory is not None
            self.task = asyncio.create_task(self.execute(prehistory), name="dashboard-experiment")
            return self.state()

    async def stop(self, run_id):
        async with self.command_lock:
            if not self.current or self.current["runId"] != run_id:
                raise RuntimeError("실험이 변경되었습니다. 현재 실험을 확인하세요")
            if not self.active or self.stop_requested:
                return self.state()
            self.stop_requested = True
            if self.current["source"] == "real":
                (self.repository.directory(run_id)/"stop.request").touch()
            self.current = await asyncio.to_thread(self.repository.update, run_id,
                         status="finishing",stopRequestedAt=now_iso(),stopReason="requested")
            if self.process and self.process.returncode is None and self.process.stdin:
                try:
                    self.process.stdin.write(b"q\n")
                    await self.process.stdin.drain()
                except (BrokenPipeError, ConnectionResetError):
                    pass
            return self.state()

    async def execute(self, prehistory):
        error = None
        try:
            if self.current["source"] == "mock":
                await self.run_mock(prehistory)
            else:
                await self.run_real()
        except asyncio.CancelledError:
            error = "실행이 중단되었습니다"
            self.current = self.repository.update(self.current["runId"],status="interrupted",endedAt=now_iso(),error=error)
            raise
        except Exception as exc:
            error = str(exc)
            self.current = self.repository.update(self.current["runId"],status="failed",endedAt=now_iso(),error=error)
        finally:
            if self.current["source"] == "mock":
                archive = self.app.state.mock_archive
                if archive:
                    self.current = await asyncio.to_thread(self.repository.update,self.current["runId"],
                        rowCount=archive.seq,lastSeq=archive.seq,elapsedMs=archive.elapsed_ms)
                    try:
                        await asyncio.to_thread(archive.close, error)
                    except OSError as exc:
                        error=str(exc)
                        self.current=await asyncio.to_thread(self.repository.update,self.current["runId"],
                            status="failed",endedAt=now_iso(),error=error)
                if error:
                    self.app.state.archive_error = error
                self.publish_mock([], final=True)

    def publish_mock(self, messages, final=False):
        if self.source:
            self.source.status = self.current["status"]
        snapshot = self.hub.snapshot if self.app.state.archive_error or not self.source else self.source.snapshot()
        snapshot = {**snapshot, "experiment":dict(snapshot["experiment"]), "system":dict(snapshot["system"])}
        snapshot["experiment"].update({k:self.current[k] for k in ("status","endedAt","error")})
        snapshot["system"].update(error=self.current["error"],experimentStatus=self.current["status"],writerActive=self.current["status"] in ACTIVE)
        if self.current["error"]:
            snapshot["system"]["validity"] = "error"
        if final or snapshot["system"] != self.hub.snapshot["system"]:
            messages.append({"type":"system","system":snapshot["system"],
                             "experiment":snapshot["experiment"],"metadata":snapshot["metadata"]})
        self.hub.publish(snapshot, messages)

    async def run_mock(self, prehistory):
        config = ExperimentConfig(**self.current["config"])
        # Explicit legacy browser fixtures retain their scripted profile.
        self.source = MockSource(self.current["serverSessionId"], config=None if self.fixture else config,
                                 run_id=self.current["runId"])
        source = self.source
        cancelled_before_motion = self.stop_requested
        if cancelled_before_motion:
            source.finished = True
            source.seq = 0
            source.buffer.clear()
            source.buffer.append(source.sample(0))
        archive = await asyncio.to_thread(MockArchive, self.settings.mock_data_root, source,
                                         self.repository.directory(self.current["runId"]))
        self.app.state.mock_archive, self.app.state.archive_error = archive, None
        initial = [source.buffer.latest]
        if prehistory:
            for t in range(100, prehistory+1, 100):
                frame = source.sample(t)
                source.buffer.append(frame)
                initial.append(frame)
        await asyncio.to_thread(archive.append, initial)
        self.current = await asyncio.to_thread(self.repository.update, self.current["runId"],
                status="finishing" if self.stop_requested else "running",metadata=source.snapshot()["metadata"])
        snapshot = source.snapshot()
        self.publish_mock([{"type":"reset", **snapshot}])
        loop = asyncio.get_running_loop()
        started, tick, checkpoint = loop.time(), 0, 0
        cycle_ms = round(source.cycle_seconds * 1000)
        end = 0 if cancelled_before_motion else config.max_cycles * cycle_ms if config.max_cycles and not self.fixture else math.inf
        while True:
            if self.stop_requested:
                end = min(end, (int(source.buffer.latest["elapsedMs"] // cycle_ms)+1)*cycle_ms)
            elapsed = min((prehistory or 0) + round((loop.time()-started)*1000), end)
            source.finished = elapsed >= end
            _, messages = source.advance(elapsed)
            await asyncio.to_thread(archive.append, [s for m in messages for s in m.get("samples",[])])
            if elapsed >= checkpoint or source.finished:
                self.current = await asyncio.to_thread(self.repository.update, self.current["runId"],
                    rowCount=archive.seq,lastSeq=archive.seq,elapsedMs=archive.elapsed_ms,
                    completedCycles=int(elapsed//cycle_ms))
                checkpoint = elapsed + 1000
            self.publish_mock(messages)
            if source.finished:
                break
            tick += source.interval_sec
            await asyncio.sleep(max(.001, started+tick-loop.time()))
        self.current = await asyncio.to_thread(self.repository.update, self.current["runId"],
            status="completed",endedAt=now_iso(),stopReason="requested" if self.stop_requested else "cycles_completed")

    async def run_real(self):
        directory = self.repository.directory(self.current["runId"])
        worker = Path(__file__).with_name("control_worker.py")
        env = {**os.environ,"PYTHONPATH":os.pathsep.join(str(p) for p in sys.path if p),"PYTHONUNBUFFERED":"1"}
        with (directory/"runner.log").open("wb") as output:
            self.process = await asyncio.create_subprocess_exec(sys.executable,str(worker),
                "--config",str(directory/"config.toml"),"--directory",str(directory),
                "--run-id",self.current["runId"],"--manifest",str(self.settings.manifest_path),
                stdin=asyncio.subprocess.PIPE,stdout=output,stderr=asyncio.subprocess.STDOUT,env=env,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
            if self.stop_requested:
                self.process.stdin.write(b"q\n")
                await self.process.stdin.drain()
            while self.process.returncode is None:
                try:
                    manifest = json.loads(self.settings.manifest_path.read_text(encoding="utf-8"))
                    if manifest["runId"] == self.current["runId"] and manifest["status"] == "running" and self.current["status"] == "preparing":
                        self.current = await asyncio.to_thread(self.repository.update,self.current["runId"],status="running")
                except (OSError, ValueError, KeyError):
                    pass
                try:
                    await asyncio.wait_for(self.process.wait(), .1)
                except asyncio.TimeoutError:
                    pass
        code = self.process.returncode
        self.current = await asyncio.to_thread(self.summarize, self.current)
        result_path = directory/"result.json"
        result = json.loads(result_path.read_text(encoding="utf-8")) if result_path.exists() else {}
        self.current = await asyncio.to_thread(self.repository.update,self.current["runId"],
            status={0:"completed",130:"interrupted"}.get(code,"failed"),endedAt=now_iso(),
            completedCycles=result.get("completedCycles",self.current["completedCycles"]),
            stopReason="requested" if self.stop_requested else "cycles_completed" if code == 0 else "execution_error",
            error=None if code == 0 else "실험 실행 실패 · 연결과 설정을 확인하세요")
        if self.process.stdin:
            self.process.stdin.close()

    async def close(self):
        try:
            if self.task and not self.task.done():
                if self.fixture:
                    self.task.cancel()
                else:
                    await self.stop(self.current["runId"])
                await asyncio.gather(self.task, return_exceptions=True)
        finally:
            self.owner.release()
