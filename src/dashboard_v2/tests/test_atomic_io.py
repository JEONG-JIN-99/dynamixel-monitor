import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from motor_dashboard import atomic_io
from motor_dashboard.main import create_app
from motor_dashboard.settings import Settings
from test_dual import configuration, wait_until


def denied(code=5):
    error = PermissionError('file replacement denied')
    error.winerror = code
    return error


@pytest.mark.parametrize('code', [5, 32, 33])
def test_transient_replace_preserves_old_json_then_recovers(tmp_path, monkeypatch, code):
    path = tmp_path/'metadata.json'
    path.write_text('{"old": true}', encoding='utf-8')
    replace = Path.replace
    calls, delays = [], []
    def busy(staging, destination):
        calls.append(staging)
        if len(calls) <= 2:
            assert json.loads(path.read_text()) == {'old': True}
            raise denied(code)
        return replace(staging, destination)
    monkeypatch.setattr(Path, 'replace', busy)
    monkeypatch.setattr(atomic_io, 'time', SimpleNamespace(sleep=delays.append))
    atomic_io.atomic_json(path, {'new': True})
    assert json.loads(path.read_text()) == {'new': True}
    assert len(calls) == 3 and len(delays) == 2
    assert not list(tmp_path.glob('*.tmp'))


@pytest.mark.parametrize('code,attempts', [(5, 8), (112, 1)])
def test_persistent_failure_is_bounded_and_preserves_destination(tmp_path, monkeypatch, code, attempts):
    path = tmp_path/'metadata.json'
    path.write_text('{}', encoding='utf-8')
    calls = []
    def fail(staging, destination):
        calls.append(staging)
        raise denied(code)
    monkeypatch.setattr(Path, 'replace', fail)
    monkeypatch.setattr(atomic_io, 'time', SimpleNamespace(sleep=lambda _: None))
    with pytest.raises(PermissionError):
        atomic_io.atomic_json(path, {'new': True})
    assert len(calls) == attempts
    assert path.read_text() == '{}'
    assert not list(tmp_path.glob('*.tmp'))


def test_concurrent_writers_use_their_own_staging_files(tmp_path, monkeypatch):
    path = tmp_path/'metadata.json'
    replace, names = Path.replace, []
    def record(staging, destination):
        names.append(staging.name)
        return replace(staging, destination)
    monkeypatch.setattr(Path, 'replace', record)
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(lambda i: atomic_io.atomic_json(path, {'index': i}), range(20)))
    assert len(set(names)) == 20
    assert json.loads(path.read_text())['index'] in range(20)
    assert not list(tmp_path.glob('*.tmp'))


@pytest.mark.parametrize('persistent', [False, True])
def test_mock_metadata_lock_isolated_from_other_motors(tmp_path, monkeypatch, persistent):
    app = create_app(Settings(mock_data_root=tmp_path/'mock_runs'))
    with TestClient(app) as client:
        runs = {}
        for slot in (6, 7):
            base = f'/motors/{slot}/api/control'
            saved = client.post(base+'/config', json={'source': 'mock', 'config': configuration(slot)}).json()['saved']
            runs[slot] = client.post(base+'/start', json={'configId': saved['id']}).json()['run']['runId']
        c6, c7 = [app.state.motors[i].state.controller for i in (6, 7)]
        wait_until(lambda: all(app.state.motors[i].state.mock_hub.snapshot['seq'] > 4 for i in (6, 7)))
        replace, attempts = Path.replace, []
        target = c6.repository.directory(runs[6])/'metadata.json'
        def busy(staging, destination):
            if destination == target:
                attempts.append(staging)
                if persistent or len(attempts) <= 2:
                    raise denied()
            return replace(staging, destination)
        monkeypatch.setattr(Path, 'replace', busy)
        if persistent:
            wait_until(lambda: c6.task.done(), timeout=8)
            assert not c6.active
            assert c6.current['status'] == 'failed'
            assert app.state.motors[6].state.mock_archive.handle.closed
            assert c6.state()['motorStatus'] == {'power': 'off', 'moving': None}
            assert c6.hub.snapshot['system']['validity'] == 'error'
            assert c6.hub.snapshot['system']['writerActive'] is False
        else:
            wait_until(lambda: len(attempts) >= 3 and c6.current['elapsedMs'] >= 1000)
            assert c6.active and c6.current['error'] is None
        assert c7.active and c7.current['error'] is None
        # Restore disk availability before teardown; all test runs use temporary folders.
        monkeypatch.setattr(Path, 'replace', replace)
        for slot, controller in ((6, c6), (7, c7)):
            if controller.active:
                client.post(f'/motors/{slot}/api/control/stop', json={'runId': runs[slot]})
        wait_until(lambda: not c6.active and not c7.active)
