import asyncio
import pytest
from fastapi.testclient import TestClient
from motor_dashboard.main import create_app
from motor_dashboard.settings import Settings
from motor_dashboard.mock_source import MockSource
from motor_dashboard.experiment.configuration import ExperimentConfig
from test_dual import wait_until, configuration


@pytest.mark.parametrize('slot', [1, 6])
@pytest.mark.parametrize('status', ['running', 'finishing', 'completed', 'failed', 'interrupted'])
def test_simulated_power_follows_lifecycle_not_last_diagnosis(tmp_path, slot, status):
    app = create_app(Settings(mock_data_root=tmp_path/'mock_runs'))
    controller = app.state.motors[slot].state.controller
    controller.repository.save_config('mock', configuration(slot))
    controller.source = MockSource(config=ExperimentConfig(**configuration(slot)), profile=slot)
    last = controller.source.buffer.latest
    last['diagnosis'] = {'state': 'fault', 'codes': ['overload']}
    last['registers']['122']['raw'] = 1
    controller.current = {'runId': controller.source.run_id, 'source': 'mock', 'status': status}
    expected = {'power': 'on', 'moving': True} if status in {'running', 'finishing'} else {'power': 'off', 'moving': None}
    assert controller.state()['motorStatus'] == expected
    # Lifecycle presentation must not erase actual historical measurements.
    assert last['diagnosis']['codes'] == ['overload']
    assert last['registers']['122']['raw'] == 1


def test_completed_real_run_does_not_report_stale_snapshot_as_current(tmp_path):
    app = create_app(Settings(mock_data_root=tmp_path/'mock_runs'))
    child = app.state.motors[1]
    controller = child.state.controller
    controller.current = {'runId': 'finished-real', 'source': 'real', 'status': 'completed'}
    child.state.hub.snapshot.update(runId='finished-real', latest={'moving': True},
                                   system={'validity': 'valid', 'writerActive': True})
    assert controller.state()['motorStatus'] == {'power': 'unknown', 'moving': None}


def test_eight_runs_isolated_and_six_simulated_profiles(tmp_path):
    app = create_app(Settings(mock_data_root=tmp_path/'mock_runs'))
    with TestClient(app) as client:
        assert client.get('/api/health').json()['motorSlots'] == list(range(1, 9))
        assert not list(tmp_path.rglob('telemetry.csv'))
        states = {i:client.get(f'/motors/{i}/api/control').json() for i in range(1,9)}
        assert all(not s['active'] for s in states.values())
        assert states[1]['defaultSource'] == 'real' and states[1]['motorStatus']['power'] == 'unknown'
        assert len({s['saved']['config']['profile_duration_ms'] for i,s in states.items() if i>=3}) == 6
        assert all(states[i]['motorStatus']['power']=='off' for i in range(3,9))
        for i in range(3,9):
            assert states[i]['allowedSources'] == ['mock']
            assert client.post(f'/motors/{i}/api/control/config', json={'source':'real','config':configuration(i)}).status_code == 422
        runs = {}
        for i in range(1,9):
            response = client.post(f'/motors/{i}/api/control/config',json={'source':'mock','config':configuration(i)})
            saved=response.json()['saved']
            started=client.post(f'/motors/{i}/api/control/start',json={'configId':saved['id']})
            assert started.status_code == 200, started.text
            runs[i]=started.json()['run']['runId']
        assert len(set(runs.values())) == 8
        wait_until(lambda: all(app.state.motors[i].state.mock_hub.snapshot['seq']>4 for i in range(1,9)))
        for i in range(1,9):
            with client.websocket_connect(f'/motors/{i}/ws/telemetry?source=mock') as ws:
                snapshot=ws.receive_json()
                assert snapshot['runId']==runs[i]
                assert snapshot['latest']['id']==i
                assert len(snapshot['latest']['registers'])==53
        samples=[MockSource(config=ExperimentConfig(**configuration(i)),profile=i).sample(1234) for i in range(3,9)]
        assert len({s['registers']['126']['raw'] for s in samples})==6
        assert len({s['registers']['146']['raw'] for s in samples})==6
        client.post('/motors/3/api/control/stop',json={'runId':runs[3]})
        wait_until(lambda: not client.get('/motors/3/api/control').json()['active'])
        state=client.get('/motors/3/api/control').json()
        assert state['motorStatus']=={'power':'off','moving':None}
        assert all(client.get(f'/motors/{i}/api/control').json()['active'] for i in (1,2,4,5,6,7,8))
        assert client.get(f'/motors/4/api/runs/{runs[3]}').status_code==404
        for i in (1,2,4,5,6,7,8):
            client.post(f'/motors/{i}/api/control/stop',json={'runId':runs[i]})
        wait_until(lambda: all(not c.state.controller.active for c in app.state.motors.values()))
        for i in range(1,9):
            history=client.get(f'/motors/{i}/api/runs/{runs[i]}/history').json()['samples']
            assert history[-1]['registers']['64']['raw']==1
            assert history[-1]['registers']['122']['raw']==0
            assert list((tmp_path/'motors'/str(i)/'mock_runs').glob('*/*/*/*/telemetry.csv'))


def test_six_profiles_have_distinct_diagnosis_windows():
    codes=set()
    for i in range(3,9):
        source=MockSource(config=ExperimentConfig(**configuration(i)),profile=i)
        sample=source.sample((13+2*(i-3))*1000)
        assert sample['diagnosis']['state']=='fault'
        codes.update(sample['diagnosis']['codes'])
    assert len(codes)==6


def test_two_hardware_controllers_with_six_virtual_runs(tmp_path, monkeypatch):
    from motor_dashboard.dual import MotorController
    async def fake_real(self):
        while not self.stop_requested:
            await asyncio.sleep(.01)
        self.current=self.repository.update(self.current['runId'],status='completed')
    monkeypatch.setattr(MotorController,'run_real',fake_real)
    app=create_app(Settings(mock_data_root=tmp_path/'mock_runs'))
    with TestClient(app) as client:
        for i in range(1,9):
            source='real' if i<=2 else 'mock'
            s=client.post(f'/motors/{i}/api/control/config',json={'source':source,'config':configuration(i)}).json()['saved']
            assert client.post(f'/motors/{i}/api/control/start',json={'configId':s['id']}).status_code==200
        wait_until(lambda: all(app.state.motors[i].state.mock_hub.snapshot['seq']>3 for i in range(3,9)))
        assert all(child.state.controller.active for child in app.state.motors.values())
        # Hardware worker being active alone is not evidence of power or motion.
        assert client.get('/motors/1/api/control').json()['motorStatus']['power']=='unknown'
        for i,child in app.state.motors.items():
            client.post(f'/motors/{i}/api/control/stop',json={'runId':child.state.controller.current['runId']})
        wait_until(lambda: all(not child.state.controller.active for child in app.state.motors.values()))
