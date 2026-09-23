from collections import deque
from datetime import datetime
from uuid import uuid4


class Events:
    def __init__(self):
        self.items = deque(maxlen=200)
        self.states = {}

    def change(self, key, value, message, severity="info"):
        if key in self.states and self.states[key] == value:
            return None
        self.states[key] = value
        event = {"id": str(uuid4()), "time": datetime.now().astimezone().isoformat(),
                 "severity": severity, "message": message}
        self.items.append(event)
        return event
