from collections import deque


class SampleBuffer:
    def __init__(self, retention_sec=60, capacity=12000):
        self.retention_ms = retention_sec * 1000
        self.samples = deque()
        self.capacity = capacity

    def append(self, sample):
        if self.samples and sample["elapsedMs"] < self.samples[-1]["elapsedMs"]:
            raise ValueError("Elapsed time moved backwards")
        self.samples.append(sample)
        cutoff = sample["elapsedMs"] - self.retention_ms
        while self.samples and self.samples[0]["elapsedMs"] < cutoff:
            self.samples.popleft()
        overflow = len(self.samples) > self.capacity
        while len(self.samples) > self.capacity:
            self.samples.popleft()
        return overflow

    def clear(self):
        self.samples.clear()

    @property
    def latest(self):
        return self.samples[-1] if self.samples else None
