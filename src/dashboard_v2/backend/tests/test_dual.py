import time
from dataclasses import replace
from types import SimpleNamespace
import pytest
from fastapi.testclient import TestClient
from motor_dashboard.app import create_app
from motor_dashboard.settings import Settings
from motor_dashboard.experiment.configuration import load_config
from motor_dashboard.adapters.dynamixel.bus_pool import BusPool


def configuration(slot):
    return replace(load_config(), motor_id=slot, motor_name='XM430-W210' if slot == 1 else 'XM430-W350',
        profile_duration_ms=200, acceleration_ms=50, top_dwell_sec=0, bottom_dwell_sec=0,
        sample_interval_sec=.02, flush_every_rows=1, max_cycles=0).snapshot()


def wait_until(check, timeout=5):
    end = time.monotonic()+timeout
    while time.monotonic()<end:
        result=check()
        if result: return result
        time.sleep(.03)
    raise AssertionError('Timed out')


def test_two_independent_runs_history_and_restart(tmp_path):
    settings=Settings(mock_data_root=tmp_path/'mock_runs')
    app=create_app(settings)
    with TestClient(app) as client:
        saved, runs = {}, {}
        for slot in (1,2):
            base=f'/motors/{slot}/api'
            assert not client.get(base+'/control').json()['active']
            response=client.post(base+'/control/config',json={'source':'mock','config':configuration(slot)})
            assert response.status_code==200, response.text
            saved[slot]=response.json()['saved']['id']
            response=client.post(base+'/control/start',json={'configId':saved[slot]})
            assert response.status_code==200, response.text
            runs[slot]=response.json()['run']['runId']
        assert runs[1] != runs[2]
        wait_until(lambda: all(app.state.motors[s].state.mock_hub.snapshot['seq']>4 for s in (1,2)))
        for slot in (1,2):
            with client.websocket_connect(f'/motors/{slot}/ws/telemetry?source=mock') as ws:
                snap=ws.receive_json()
                assert snap['type']=='snapshot'
                assert snap['runId']==runs[slot]
                assert {s['id'] for s in snap['history']}=={slot}
                assert snap['latest']['registers']['7']['raw']==slot
            r=client.get(f'/motors/{slot}/api/history',params={'source':'mock','runId':runs[slot],
                'sourceSessionId':snap['sourceSessionId'],'durationSec':0})
            assert r.status_code==200,r.text
            assert {s['id'] for s in r.json()['samples']}=={slot}
        assert client.post('/motors/1/api/control/stop',json={'runId':runs[2]}).status_code==409
        client.post('/motors/1/api/control/stop',json={'runId':runs[1]})
        wait_until(lambda: not client.get('/motors/1/api/control').json()['active'])
        assert client.get('/motors/2/api/control').json()['active']
        old=app.state.motors[1].state.controller.repository.directory(runs[1])/'telemetry.csv'
        old_bytes=old.read_bytes()
        seq=app.state.motors[2].state.mock_hub.snapshot['seq']
        wait_until(lambda: app.state.motors[2].state.mock_hub.snapshot['seq']>seq+3)
        assert old.read_bytes()==old_bytes
        history=client.get(f'/motors/1/api/runs/{runs[1]}/history').json()['samples']
        assert history[-1]['registers']['64']['raw']==1
        assert history[-1]['registers']['122']['raw']==0
        assert client.get(f'/motors/2/api/runs/{runs[1]}').status_code==404
        again=client.post('/motors/1/api/control/start',json={'configId':saved[1]}).json()['run']
        assert again['runId']!=runs[1]
        for slot,run in [(1,again['runId']),(2,runs[2])]:
            client.post(f'/motors/{slot}/api/control/stop',json={'runId':run})
            wait_until(lambda: not client.get(f'/motors/{slot}/api/control').json()['active'])
    with TestClient(create_app(settings)) as client:
        assert client.get('/motors/1/api/runs').json()['total']==2
        assert client.get('/motors/2/api/runs').json()['total']==1
        assert client.get('/motors/2/api/control').json()['saved']['config']['motor_id']==2


def test_shared_bus_refcounts_conflicts_and_failed_open():
    ports=[]
    class Port:
        def __init__(self,name): self.closed=0; ports.append(self)
        def openPort(self): return True
        def setBaudRate(self,rate): return rate != 1
        def closePort(self): self.closed+=1
    pool=BusPool()
    a=SimpleNamespace(port='COM6',baudrate=57600,protocol_version=2,motor_id=1)
    b=SimpleNamespace(**{**vars(a),'motor_id':2})
    one=pool.acquire(a,Port);two=pool.acquire(b,Port)
    assert one is two and len(ports)==1
    with pytest.raises(RuntimeError): pool.acquire(a,Port)
    with pytest.raises(RuntimeError): pool.acquire(SimpleNamespace(**{**vars(b),'baudrate':115200}),Port)
    pool.release(a);assert ports[0].closed==0
    pool.release(b);assert ports[0].closed==1 and not pool.buses
    with pytest.raises(RuntimeError):pool.acquire(SimpleNamespace(**{**vars(a),'baudrate':1}),Port)
    assert ports[-1].closed==1 and not pool.buses


def test_hardware_conflicts_rejected_without_opening_sdk(tmp_path,monkeypatch):
    import asyncio
    from motor_dashboard.control.fleet import MotorController
    async def fake_real(self):
        while not self.stop_requested: await asyncio.sleep(.01)
        self.current=self.repository.update(self.current['runId'],status='completed')
    monkeypatch.setattr(MotorController,'run_real',fake_real)
    with TestClient(create_app(Settings(mock_data_root=tmp_path/'mock_runs'))) as client:
        def save(slot,c):
            return client.post(f'/motors/{slot}/api/control/config',json={'source':'real','config':c}).json()['saved']['id']
        first=save(1,configuration(1))
        a=client.post('/motors/1/api/control/start',json={'configId':first}).json()
        second=save(2,configuration(1))
        assert client.post('/motors/2/api/control/start',json={'configId':second}).status_code==409
        c=configuration(2);c['baudrate']=115200
        second=save(2,c)
        assert client.post('/motors/2/api/control/start',json={'configId':second}).status_code==409
        second=save(2,configuration(2))
        assert client.post('/motors/2/api/control/start',json={'configId':second}).status_code==200


def test_shared_sdk_transactions_are_serialized_and_torque_is_retained(monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from motor_dashboard.adapters.dynamixel import shared_bus
    from motor_dashboard.experiment.configuration import ExperimentConfig
    pool=BusPool()
    busy=0
    calls=[]
    class Port:
        closed=0
        def __init__(self,name):pass
        def openPort(self):return True
        def setBaudRate(self,value):return True
        def closePort(self):self.closed+=1
    class Packet:
        def getProtocolVersion(self):return 2.0
        def ping(self,port,id):return (1030 if id==1 else 1020),0,0
        def read1ByteTxRx(self,port,id,address):
            nonlocal busy
            busy+=1
            assert busy==1, 'Overlapping transactions on shared bus'
            time.sleep(.003)
            calls.append((id,address))
            busy-=1
            return 42,0,0
        def write1ByteTxRx(self,*args):raise AssertionError('Normal exit must not disable torque')
    monkeypatch.setattr(shared_bus,'PortHandler',Port)
    one=shared_bus.SharedExperiment(ExperimentConfig(**configuration(1)),pool=pool)
    two=shared_bus.SharedExperiment(ExperimentConfig(**configuration(2)),pool=pool)
    one.packet=two.packet=Packet()
    one.connect();two.connect()
    assert one.port is two.port
    with ThreadPoolExecutor(2) as threads:
        list(threads.map(lambda exp:[exp.read(1,6) for _ in range(10)],[one,two]))
    assert {id for id,_ in calls}=={1,2}
    one.normal_exit=two.normal_exit=True
    one.torque_enabled=two.torque_enabled=True
    one.close();assert two.port.closed==0
    two.read(1,6)
    two.close();assert two.port.closed==1
