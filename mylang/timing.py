import math
import time

def every(interval, duration):
    if not all(isinstance(value, (int, float)) and math.isfinite(value)
               for value in (interval, duration)) or interval <= 0 or duration < 0:
        raise ValueError('every requires a positive interval and nonnegative duration')
    start = time.monotonic()
    deadline = start + duration
    tick = 0
    while True:
        target = start + tick * interval
        if target >= deadline:
            return
        time.sleep(max(0, target - time.monotonic()))
        now = time.monotonic()
        if now >= deadline:
            return
        yield now - start

        tick = max(tick + 1, math.floor((time.monotonic() - start) / interval) + 1)
