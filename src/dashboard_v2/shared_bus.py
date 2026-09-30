"""Reuse the experiment motion loop with serialized shared-port transactions."""
from dynamixel_sdk import PortHandler, GroupSyncRead
from .experiment.acquisition import Experiment


class SharedExperiment(Experiment):
    def __init__(self, *args, pool, **kwargs):
        super().__init__(*args, **kwargs)
        self.pool, self.bus = pool, None

    def connect(self):
        self.bus = self.pool.acquire(self.config, PortHandler)
        self.port = self.bus['port']
        self.reader = GroupSyncRead(self.port, self.packet, 224, self.data_length)
        self.port_open = True
        with self.bus['lock']:
            model, result, error = self.packet.ping(self.port, self.config.motor_id)
            self.check(result, error, 'Ping')
            if model != self.config.model.number:
                raise RuntimeError('설정한 모터 종류와 연결된 모터가 다릅니다')
            self.model_number = model
            self.firmware = self.read(1, 6)
            if self.firmware < 42:
                raise RuntimeError('모터 펌웨어를 확인하세요')

    def read(self, *args, **kwargs):
        with self.bus['lock']:
            return super().read(*args, **kwargs)

    def write(self, *args, **kwargs):
        with self.bus['lock']:
            return super().write(*args, **kwargs)

    def snapshot(self):
        with self.bus['lock']:
            return super().snapshot()

    def wait_for_finish(self):
        # Web control uses the per-run stop.request file, never shared stdin.
        pass

    def close(self):
        if not self.bus:
            return
        try:
            if self.port_open and self.torque_enabled and not self.normal_exit:
                self.goal(self.read(4, 132, signed=True))
            self.finish_event.set()
            if self.reader_added:
                self.reader.clearParam()
        finally:
            self.pool.release(self.config)
            self.port_open = False
