"""DYNAMIXEL SDK connection, register access and synchronized telemetry reads."""
from dynamixel_sdk import COMM_SUCCESS, GroupSyncRead, PacketHandler, PortHandler

def indirect_fields(model):
    # XL과 XM은 주소와 길이가 같고, 주소 126의 의미와 단위가 다릅니다.
    return [
        ("Hardware Error Status", 70, 1, False),
        ("Realtime Tick", 120, 2, False),
        ("Moving", 122, 1, False),
        ("Moving Status", 123, 1, False),
        ("Present PWM", 124, 2, True),
        (model.feedback_name, 126, 2, True),
        ("Present Velocity", 128, 4, True),
        ("Present Position", 132, 4, True),
        ("Velocity Trajectory", 136, 4, True),
        ("Position Trajectory", 140, 4, True),
        ("Present Input Voltage", 144, 2, False),
        ("Present Temperature", 146, 1, False),
    ]

def to_signed(value, size):
    return value - (1 << (size * 8)) if value & (1 << (size * 8 - 1)) else value


class DynamixelDevice:
    def initialize_device(self, config):
        self.fields = indirect_fields(config.model)
        self.data_length = sum(field[2] for field in self.fields)
        self.port = PortHandler(config.port)
        self.packet = PacketHandler(config.protocol_version)
        self.reader = GroupSyncRead(self.port, self.packet, 224, self.data_length)
        self.port_open = False
        self.torque_enabled = False
        self.reader_added = False

    def check(self, result, error, operation):
        if result != COMM_SUCCESS:
            raise RuntimeError(f"{operation}: {self.packet.getTxRxResult(result)}")
        if error:
            raise RuntimeError(f"{operation}: {self.packet.getRxPacketError(error)}")

    def write(self, size, address, value):
        method = getattr(self.packet, f"write{size}ByteTxRx")
        result, error = method(self.port, self.config.motor_id, address, value & ((1 << (8 * size)) - 1))
        self.check(result, error, f"Write address {address}")

    def read(self, size, address, signed=False):
        value, result, error = getattr(self.packet, f"read{size}ByteTxRx")(
            self.port, self.config.motor_id, address)
        self.check(result, error, f"Read address {address}")
        return to_signed(value, size) if signed else value

    def goal(self, position):
        if not -1048575 <= position <= 1048575:
            raise ValueError(f"Goal position out of range: {position}")
        self.write(4, 116, position)

    def connect(self):
        if not self.port.openPort():
            raise RuntimeError(f"Failed to open port: {self.config.port}")
        self.port_open = True
        if not self.port.setBaudRate(self.config.baudrate):
            raise RuntimeError(f"Failed to set baudrate: {self.config.baudrate}")
        model, result, error = self.packet.ping(self.port, self.config.motor_id)
        self.check(result, error, "Ping")
        if model != self.config.model.number:
            raise RuntimeError(
                f"Motor model mismatch: config={self.config.motor_name} "
                f"({self.config.model.number}), connected={model}. No control settings were written.")
        self.model_number = model
        self.firmware = self.read(1, 6)
        if self.firmware < 42:
            raise RuntimeError("Time-based Profile requires firmware version 42 or later")
        print(f"Connected: {self.config.motor_name}, ID={self.config.motor_id}, firmware={self.firmware}")

    def snapshot(self):
        result = self.reader.txRxPacket()
        if result != COMM_SUCCESS:
            raise RuntimeError(f"GroupSyncRead: {self.packet.getTxRxResult(result)}")
        values = {}
        offset = 0
        for name, _, size, signed in self.fields:
            address = 224 + offset
            if not self.reader.isAvailable(self.config.motor_id, address, size):
                raise RuntimeError(f"GroupSyncRead data unavailable: {name}")
            value = self.reader.getData(self.config.motor_id, address, size)
            values[name] = to_signed(value, size) if signed else value
            offset += size
        return values
