import asyncio


class TelemetryHub:
    """All publication/subscription occurs on the event loop, without an await between snapshot and registration."""
    def __init__(self, snapshot, queue_size=32):
        self.snapshot = snapshot
        self.queue_size = queue_size
        self.subscribers = set()

    def envelope(self, message):
        return {"schemaVersion": 1, "serverSessionId": self.snapshot["serverSessionId"],
                "sourceSessionId": self.snapshot["sourceSessionId"], **message}

    def subscribe(self):
        queue = asyncio.Queue(maxsize=self.queue_size)
        self.subscribers.add(queue)
        queue.put_nowait(self.envelope({"type": "snapshot", **self.snapshot}))
        return queue

    def publish(self, snapshot, messages):
        self.snapshot = snapshot
        for queue in tuple(self.subscribers):
            if queue.qsize() + len(messages) > self.queue_size:
                while not queue.empty():
                    queue.get_nowait()
                queue.put_nowait(self.envelope({"type": "reset", "reason": "slow-client-resync", **snapshot}))
            else:
                for message in messages:
                    queue.put_nowait(self.envelope(message))

    def unsubscribe(self, queue):
        self.subscribers.discard(queue)
