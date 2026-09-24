import csv
import json
import time
from dataclasses import replace
from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient
from motor_dashboard.main import create_app
from motor_dashboard.settings import Settings
from motor_dashboard.experiment.configuration import load_config
from motor_dashboard.run_repository import RunRepository


def settings(tmp_path):
    return Settings(manifest_path=tmp_path/"current.json",data_root=tmp_path/"original",mock_data_root=tmp_path/"mock_runs")


def config(**values):
    return replace(load_config(), profile_duration_ms=150,acceleration_ms=50,top_dwell_sec=.02,
                   bottom_dwell_sec=.02,sample_interval_sec=.02,flush_every_rows=1,**values).snapshot()


def save(client, **values):
    response=client.post("/api/control/config",json={"source":"mock","config":config(**values)})
    assert response.status_code==200,response.text
    return response.json()["saved"]


def wait_done(client):
    deadline=time.monotonic()+5
    while time.monotonic()<deadline:
        state=client.get("/api/control").json()
        if not state["active"]: return state["run"]
        time.sleep(.02)
    raise AssertionError("experiment did not finish")


def test_idle_save_start_stop_archive_restart(tmp_path):
    cfg=settings(tmp_path)
    app=create_app(cfg)
    with TestClient(app) as client:
        assert not client.get("/api/control").json()["active"]
        assert not list(tmp_path.rglob("telemetry.csv"))
        saved=save(client,motor_name="XM430-W350",motor_id=3,turns=.25,direction=-1)
        saved_path=cfg.control_root/"configurations"/(saved["id"]+".toml")
        assert load_config(saved_path).motor_id==3
        assert not list(tmp_path.rglob("telemetry.csv"))
        state=client.post("/api/control/start",json={"configId":saved["id"]}).json()
        run_id=state["run"]["runId"]
        assert client.post("/api/control/start",json={"configId":saved["id"]}).status_code==409
        assert client.post("/api/control/config",json={"source":"mock","config":config()}).status_code==409
        assert client.post("/api/control/stop",json={"runId":"stale"}).status_code==409
        time.sleep(.07)
        state=client.post("/api/control/stop",json={"runId":run_id}).json()
        assert state["run"]["status"]=="finishing"
        completed=wait_done(client)
        assert completed["status"]=="completed" and completed["completedCycles"]==1
        assert completed["elapsedMs"]==340
        assert completed["config"]["torque_off_on_normal_exit"] is False
        history=client.get(f"/api/runs/{run_id}/history").json()["samples"]
        assert history[0]["elapsedMs"]==0 and history[-1]["elapsedMs"]==340
        assert all(s["model"]=="XM430-W350" and s["id"]==3 for s in history)
        assert history[-1]["registers"]["122"]["raw"]==0
        assert history[-1]["registers"]["140"]["raw"]==100
        assert history[2]["registers"]["116"]["raw"]==100-1024
        assert history[-1]["registers"]["64"]["raw"]==1
        old_csv=app.state.controller.repository.directory(run_id)/"telemetry.csv"
        before=old_csv.read_bytes()
        time.sleep(.08)
        assert old_csv.read_bytes()==before
        listing=client.get("/api/runs").json()
        assert listing["total"]==1 and listing["dates"]==[completed["date"]]
        assert old_csv.parent.parent.name==completed["date"][8:10]
        saved2=save(client,max_cycles=1)
        second=client.post("/api/control/start",json={"configId":saved2["id"]}).json()["run"]
        assert second["runId"]!=run_id
        assert wait_done(client)["completedCycles"]==1
        assert old_csv.read_bytes()==before
    with TestClient(create_app(cfg)) as client:
        assert not client.get("/api/control").json()["active"]
        assert client.get("/api/runs").json()["total"]==2
        assert client.get(f"/api/runs/{run_id}/history").json()["samples"]==history
        assert client.get(f"/api/runs/{run_id}/history?durationSec=42").status_code==422
        assert client.get("/api/runs/nonexistent").status_code==404


def test_configuration_and_cross_origin_validation(tmp_path):
    with TestClient(create_app(settings(tmp_path))) as client:
        assert client.post("/api/control/start",json={"configId":"none"}).status_code==409
        bad=config();bad["torque_off_on_normal_exit"]=True
        assert client.post("/api/control/config",json={"source":"mock","config":bad}).status_code==422
        bad=config();bad["acceleration_ms"]=151
        assert client.post("/api/control/config",json={"source":"mock","config":bad}).status_code==422
        assert client.post("/api/control/config",json={"source":"mock","config":config()},headers={"Origin":"https://different.example"}).status_code==403


def test_hardware_launch_failure_is_recorded_without_motor_access(tmp_path):
    app=create_app(settings(tmp_path))
    with TestClient(app) as client:
        result=client.post("/api/control/config",json={"source":"real","config":config()}).json()
        with patch("motor_dashboard.control.asyncio.create_subprocess_exec",side_effect=OSError("worker launch failed")):
            run_id=client.post("/api/control/start",json={"configId":result["saved"]["id"]}).json()["run"]["runId"]
            done=wait_done(client)
        assert done["status"]=="failed"
        assert "worker launch failed" in done["error"]
        assert app.state.controller.repository.directory(run_id).is_relative_to(app.state.controller.settings.experiment_data_root)
        assert not list(app.state.controller.settings.data_root.rglob("*"))


def test_recovery_marks_unfinished_mock_as_interrupted(tmp_path):
    cfg=settings(tmp_path);repo=RunRepository(cfg)
    saved=repo.save_config("mock",config());run=repo.create(saved,"old-server")
    with TestClient(create_app(cfg)) as client:
        recovered=client.get("/api/runs/"+run["runId"]).json()
        assert recovered["status"]=="interrupted"
        assert client.get("/api/runs/"+run["runId"]+"/history").json()["samples"]==[]


def test_managed_hardware_copy_finishes_cycle_keeps_torque_and_replays(tmp_path):
    from contextlib import ExitStack
    from motor_dashboard.experiment import acquisition
    from motor_dashboard.experiment.run_manifest import RunManifest
    from motor_dashboard.tests.test_experiment_copy import FakeDevice, FakeClock
    cfg=settings(tmp_path);repo=RunRepository(cfg)
    values=config(max_cycles=3);saved=repo.save_config("real",values);meta=repo.create(saved,"server")
    directory=repo.directory(meta["runId"]);device=FakeDevice();clock=FakeClock()
    with ExitStack() as stack:
        stack.enter_context(patch.object(acquisition,"PortHandler",return_value=device.port()))
        stack.enter_context(patch.object(acquisition,"PacketHandler",return_value=device.packet()))
        stack.enter_context(patch.object(acquisition,"GroupSyncRead",return_value=device.reader()))
        stack.enter_context(patch.object(acquisition,"time",clock))
        stack.enter_context(patch.object(acquisition.threading,"Thread"))
        experiment=acquisition.Experiment(load_config(directory/"config.toml"),directory/"config.toml",
            run_directory=directory,run_id=meta["runId"],manifest_path=cfg.manifest_path)
        original_dwell=experiment.dwell
        def dwell(*args):
            (directory/"stop.request").touch()
            return original_dwell(*args)
        experiment.dwell=dwell
        assert experiment.run()==0
    assert experiment.completed_cycles==1
    torque_writes=[value for size,address,value in device.writes if address==64]
    assert torque_writes==[0,1]  # Setup OFF/ON; no OFF on exit.
    assert device.closed
    with (directory/"telemetry.csv").open(encoding="utf-8-sig",newline="") as handle:
        rows=list(csv.DictReader(handle))
    assert rows[-1]["Phase"]=="BOTTOM_DWELL"
    assert {row["Cycle"] for row in rows}=={"1"}
    app=create_app(cfg)
    app.state.controller.summarize(meta)
    repo.update(meta["runId"],status="completed",completedCycles=1)
    with TestClient(app) as client:
        data=client.get(f"/api/runs/{meta['runId']}/history").json()
        assert len(data["samples"])==len(rows)
        assert data["samples"][-1]["position"]==100
        assert data["samples"][0]["runId"]==meta["runId"]
        assert not list(cfg.data_root.rglob("*"))


def test_restart_adopts_surviving_managed_worker_and_stop_marker(tmp_path):
    from motor_dashboard.experiment.run_manifest import RunManifest
    from motor_dashboard.experiment.configuration import ExperimentConfig
    cfg=settings(tmp_path);repo=RunRepository(cfg)
    saved=repo.save_config("real",config());meta=repo.create(saved,"previous-server")
    directory=repo.directory(meta["runId"])
    manifest=RunManifest(ExperimentConfig(**saved["config"]),cfg.manifest_path,meta["runId"])
    manifest.begin();manifest.update(status="running")
    try:
        with TestClient(create_app(cfg)) as client:
            state=client.get("/api/control").json()
            assert state["active"] and state["run"]["runId"]==meta["runId"]
            assert client.post("/api/control/stop",json={"runId":meta["runId"]}).status_code==200
            assert (directory/"stop.request").exists()
            (directory/"result.json").write_text(json.dumps({"code":0,"completedCycles":1}),encoding="utf-8")
            manifest.finish(0);manifest.release()
            assert wait_done(client)["status"]=="completed"
    finally:
        manifest.release()


def test_korean_date_folder_stays_fixed_across_midnight(tmp_path):
    from datetime import datetime,timezone
    from motor_dashboard import run_repository
    class Clock(datetime):
        @classmethod
        def now(cls,tz=None):
            return datetime(2026,12,31,15,0,1,tzinfo=timezone.utc)
    repo=RunRepository(settings(tmp_path));saved=repo.save_config("mock",config())
    with patch.object(run_repository,"datetime",Clock):
        meta=repo.create(saved,"server")
    assert meta["date"]=="2027-01-01"
    directory=repo.directory(meta["runId"])
    assert directory.parent.parts[-3:]==("2027","01","01")
    repo.update(meta["runId"],endedAt="2027-01-02T03:00:00+09:00")
    assert repo.directory(meta["runId"])==directory


def test_archive_creation_failure_never_reuses_previous_run(tmp_path):
    app=create_app(settings(tmp_path))
    with TestClient(app) as client:
        saved=save(client,max_cycles=1)
        client.post("/api/control/start",json={"configId":saved["id"]})
        first=wait_done(client)
        with patch("motor_dashboard.control.MockArchive",side_effect=OSError("cannot create archive")):
            second=client.post("/api/control/start",json={"configId":saved["id"]}).json()["run"]
            assert wait_done(client)["status"]=="failed"
        assert second["runId"]!=first["runId"]
        assert app.state.mock_archive is None
        assert app.state.mock_hub.snapshot["runId"]==second["runId"]
        assert app.state.mock_hub.snapshot["history"]==[]
        assert app.state.mock_hub.snapshot["system"]["experimentStatus"]=="failed"
