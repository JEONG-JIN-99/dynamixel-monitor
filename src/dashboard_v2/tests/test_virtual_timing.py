from fastapi.testclient import TestClient
import pytest
from motor_dashboard.main import create_app
from motor_dashboard.settings import Settings
from motor_dashboard.mock_source import MockSource
from motor_dashboard.experiment.configuration import ExperimentConfig
from test_dual import configuration


def test_new_virtual_defaults_have_visible_motion_and_pauses(tmp_path):
    app = create_app(Settings(mock_data_root=tmp_path/'mock_runs'))
    with TestClient(app) as client:
        for slot in range(3, 9):
            cfg = client.get(f'/motors/{slot}/api/control').json()['saved']['config']
            assert 10000 <= cfg['profile_duration_ms'] <= 15000
            assert 2 <= cfg['top_dwell_sec'] <= 3
            assert 2 <= cfg['bottom_dwell_sec'] <= 3
            assert cfg['sample_interval_sec'] == .1
            source = MockSource(config=ExperimentConfig(**cfg), profile=slot)
            move = cfg['profile_duration_ms']
            pause = round(cfg['top_dwell_sec']*1000)
            assert source.cycle_seconds == pytest.approx(24 + 2.4*(slot-3))
            assert source.sample(move-100)['registers']['122']['raw'] == 1
            assert source.sample(move+100)['registers']['122']['raw'] == 0
            assert source.sample(move+pause-100)['registers']['122']['raw'] == 0
            assert source.sample(move+pause+100)['registers']['122']['raw'] == 1
            assert source.sample(2*move+pause+100)['registers']['122']['raw'] == 0
            assert source.sample(round(source.cycle_seconds*1000)+100)['registers']['122']['raw'] == 1


@pytest.mark.parametrize('version', ['original', 'slower'])
def test_old_generated_timing_upgrades_without_changing_recorded_runs(tmp_path, version):
    settings = Settings(mock_data_root=tmp_path/'mock_runs')
    app = create_app(settings)
    preserved = []
    for slot in range(1, 9):
        controller = app.state.motors[slot].state.controller
        cfg = configuration(slot)
        if slot >= 3:
            k = slot-3
            cfg.update(acceleration_ms=250+80*k, profile_duration_ms=1800+350*k,
                       top_dwell_sec=.2+.1*k, bottom_dwell_sec=.3+.12*k)
            if version == 'slower':
                cfg.update(acceleration_ms=1200+150*k, profile_duration_ms=5000+500*k,
                           top_dwell_sec=2+.2*k, bottom_dwell_sec=2+.2*k)
        saved = controller.repository.save_config('mock', cfg)
        if slot <= 2:
            preserved.append((controller.settings.control_root/'saved.json', None))
        run = controller.repository.create(saved, 'test-server')
        controller.repository.update(run['runId'], status='completed')
        directory = controller.repository.directory(run['runId'])
        preserved.extend((directory/name, None) for name in ('config.toml', 'metadata.json'))
    preserved = [(path, path.read_bytes()) for path, _ in preserved]
    with TestClient(create_app(settings)) as client:
        for slot in range(3, 9):
            state = client.get(f'/motors/{slot}/api/control').json()
            cfg = state['saved']['config']
            assert cfg['profile_duration_ms'] == 10000+1000*(slot-3)
            assert cfg['sample_interval_sec'] == .02  # Preserve unrelated user settings.
            assert not state['active']
        assert all(path.read_bytes() == contents for path, contents in preserved)


def test_custom_virtual_timing_is_preserved(tmp_path):
    settings = Settings(mock_data_root=tmp_path/'mock_runs')
    controller = create_app(settings).state.motors[6].state.controller
    saved = controller.repository.save_config('mock', configuration(6))
    with TestClient(create_app(settings)) as client:
        assert client.get('/motors/6/api/control').json()['saved'] == saved
