"""Eight independent motor services sharing serialized hardware buses."""
import asyncio
from contextlib import asynccontextmanager, AsyncExitStack
from dataclasses import replace
from types import SimpleNamespace
from fastapi import FastAPI
from .control import ExperimentController
from .run_repository import ACTIVE, now_iso
from .settings import ROOT

MOTOR_SLOTS = tuple(range(1, 9))
REAL_SLOTS = (1, 2)


def virtual_timing(slot):
    k = slot - 3
    return dict(acceleration_ms=1200 + 150*k, profile_duration_ms=10000 + 1000*k,
                top_dwell_sec=2 + .2*k, bottom_dwell_sec=2 + .2*k)


class MotorController(ExperimentController):
    def __init__(self, settings, hub, app, slot, fleet):
        super().__init__(settings, hub, app)
        self.slot, self.fleet = slot, fleet

    def state(self):
        value = super().state()
        value['motorSlot'] = self.slot
        value['defaults'].update(motor_id=self.slot,
                                 motor_name='XM430-W210' if self.slot == 1 else 'XM430-W350')
        value['allowedSources'] = ['real', 'mock'] if self.slot in REAL_SLOTS else ['mock']
        value['defaultSource'] = 'real' if self.slot in REAL_SLOTS else 'mock'
        if self.slot >= 3:
            k = self.slot - 3
            value['defaults'].update(turns=.35 + .12*k, direction=1 if k % 2 == 0 else -1,
                                     **virtual_timing(self.slot))
        source = (self.current if self.active else value['saved']) or {}
        mode = source.get('source', value['defaultSource'])
        if mode == 'mock':
            sample = self.source.buffer.latest if self.source else None
            # Retained telemetry belongs to the recording, not a live simulator.
            powered = bool(sample and self.current and self.current['source'] == 'mock'
                           and self.current['status'] in ACTIVE
                           and self.current['runId'] == self.source.run_id)
            value['motorStatus'] = {'power': 'on' if powered else 'off',
                'moving': bool(sample['registers']['122']['raw']) if powered else None}
        else:
            snapshot = self.app.state.hub.snapshot
            sample, system = snapshot.get('latest'), snapshot['system']
            fresh = sample and system.get('validity') == 'valid' and system.get('writerActive') is True
            if (self.current and self.current['source'] == 'real'
                    and self.current['status'] not in ACTIVE
                    and snapshot.get('runId') == self.current['runId']):
                fresh = False
            # A missing response cannot prove power loss. Torque is not a power sensor.
            value['motorStatus'] = {'power': 'on' if fresh else 'unknown',
                                    'moving': sample.get('moving') if fresh else None}
        return value

    async def open(self):
        await super().open()
        if self.slot >= 3:
            saved = self.repository.saved()
            if not saved:
                await asyncio.to_thread(self.repository.save_config, 'mock', self.state()['defaults'])
            elif saved['source'] == 'mock':
                k = self.slot - 3
                previous = [
                    dict(acceleration_ms=250 + 80*k, profile_duration_ms=1800 + 350*k,
                         top_dwell_sec=.2 + .1*k, bottom_dwell_sec=.3 + .12*k),
                    dict(acceleration_ms=1200 + 150*k, profile_duration_ms=5000 + 500*k,
                         top_dwell_sec=2 + .2*k, bottom_dwell_sec=2 + .2*k),
                ]
                # Upgrade only the old generated timing; preserve custom settings
                # and immutable configs belonging to already recorded runs.
                if (saved['config']['move_timeout_sec'] > virtual_timing(self.slot)['profile_duration_ms'] / 1000
                        and any(all(abs(saved['config'].get(key, -1) - value) < 1e-8
                                    for key, value in timing.items()) for timing in previous)):
                    await asyncio.to_thread(self.repository.save_config, 'mock',
                        {**saved['config'], **virtual_timing(self.slot)})

    async def save(self, source, config):
        if source == 'real' and self.slot not in REAL_SLOTS:
            raise ValueError('이 모터는 가상 모터로 실행합니다')
        return await super().save(source, config)

    async def start(self, config_id, prehistory=None):
        # Reserve identity before scheduling motion; simultaneous requests cannot race.
        async with self.fleet.lock:
            saved = self.repository.saved()
            if saved and saved['source'] == 'real':
                if self.slot not in REAL_SLOTS:
                    raise ValueError('이 모터는 가상 모터로 실행합니다')
                c = saved['config']
                for peer in self.fleet.controllers:
                    if peer is self or not peer.active or not peer.current or peer.current['source'] != 'real':
                        continue
                    other = peer.current['config']
                    if c['port'].strip().casefold() != other['port'].strip().casefold():
                        continue
                    if c['motor_id'] == other['motor_id']:
                        raise RuntimeError('같은 포트의 모터 ID가 중복됩니다')
                    if (c['baudrate'], c['protocol_version']) != (other['baudrate'], other['protocol_version']):
                        raise RuntimeError('같은 포트에서는 통신 속도와 프로토콜을 동일하게 설정하세요')
            return await super().start(config_id, prehistory)

    async def run_real(self):
        # Import the SDK only when the user explicitly starts a hardware run.
        from .shared_bus import SharedExperiment
        from .experiment.configuration import load_config
        directory = self.repository.directory(self.current['runId'])
        experiment = SharedExperiment(load_config(directory/'config.toml'), directory/'config.toml',
            pool=self.fleet.buses, run_directory=directory, run_id=self.current['runId'],
            manifest_path=self.settings.manifest_path)
        self.current = await asyncio.to_thread(self.repository.update, self.current['runId'], status='running')
        # stop.request is checked after a full round trip by the original experiment loop.
        code = await asyncio.to_thread(experiment.run)
        self.current = await asyncio.to_thread(self.summarize, self.current)
        self.current = await asyncio.to_thread(self.repository.update, self.current['runId'],
            status={0:'completed',130:'interrupted'}.get(code,'failed'), endedAt=now_iso(),
            completedCycles=experiment.completed_cycles,
            stopReason='requested' if self.stop_requested else 'cycles_completed' if code == 0 else 'execution_error',
            error=None if code == 0 else '실험 실행 실패 · 연결과 설정을 확인하세요')


def create_dual_app(settings, dist=None, mock_prehistory_ms=None):
    from .main import create_single_app
    from .bus_pool import BusPool
    fleet = SimpleNamespace(lock=asyncio.Lock(), controllers=[], buses=BusPool())
    children = {}
    for slot in MOTOR_SLOTS:
        root = settings.mock_data_root.parent / 'motors' / str(slot)
        scoped = replace(settings, manifest_path=root/'current_experiment.json',
                         data_root=root/'standalone_runs', mock_data_root=root/'mock_runs')
        child = create_single_app(scoped, dist, mock_prehistory_ms,
            controller_factory=lambda s,h,a,slot=slot: MotorController(s,h,a,slot,fleet))
        fleet.controllers.append(child.state.controller)
        children[slot] = child

    @asynccontextmanager
    async def lifespan(app):
        async with AsyncExitStack() as stack:
            for child in children.values():
                await stack.enter_async_context(child.router.lifespan_context(child))
            yield

    app = FastAPI(title='Motor Dashboard V2', lifespan=lifespan)
    app.state.motors = children
    @app.get('/api/health')
    async def health():
        return {'ok':True, 'motorSlots':list(MOTOR_SLOTS), 'realMotorSlots':list(REAL_SLOTS)}
    for slot, child in children.items():
        app.mount(f'/motors/{slot}', child)
    # The unchanged single-page file handler serves the root UI; API paths are scoped above.
    from fastapi import HTTPException
    from fastapi.responses import FileResponse
    from pathlib import Path
    files = Path(dist) if dist else ROOT/'frontend'/'dist'
    @app.get('/{path:path}', include_in_schema=False)
    async def frontend(path: str):
        target = (files/path).resolve()
        if not target.is_relative_to(files.resolve()) or path.startswith(('api/','ws/')):
            raise HTTPException(404)
        if target.is_file():
            return FileResponse(target)
        if path and not path.startswith('logs/') and path not in {'control','motors','trends','alerts','logs','overview','settings'}:
            raise HTTPException(404)
        if not (files/'index.html').exists():
            raise HTTPException(503, '화면을 불러올 수 없습니다')
        return FileResponse(files/'index.html')
    return app
