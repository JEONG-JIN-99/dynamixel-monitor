"""One port owner and transaction lock for each physical motor bus."""
import threading


class BusPool:
    def __init__(self):
        self.lock = threading.RLock()
        self.buses = {}

    def acquire(self, config, factory):
        key = config.port.strip().casefold()
        with self.lock:
            bus = self.buses.get(key)
            if bus:
                if bus['baud'] != config.baudrate or bus['protocol'] != config.protocol_version:
                    raise RuntimeError('같은 포트의 통신 설정이 다릅니다')
                if config.motor_id in bus['ids']:
                    raise RuntimeError('이미 실행 중인 모터 ID입니다')
            else:
                port = factory(config.port)
                try:
                    if not port.openPort() or not port.setBaudRate(config.baudrate):
                        raise RuntimeError('통신 포트를 열 수 없습니다')
                except BaseException:
                    port.closePort()
                    raise
                bus = dict(port=port, baud=config.baudrate, protocol=config.protocol_version,
                           lock=threading.RLock(), ids=set())
                self.buses[key] = bus
            bus['ids'].add(config.motor_id)
            return bus

    def release(self, config):
        key = config.port.strip().casefold()
        with self.lock:
            bus = self.buses.get(key)
            if not bus:
                return
            bus['ids'].discard(config.motor_id)
            if not bus['ids']:
                with bus['lock']:
                    bus['port'].closePort()
                del self.buses[key]
