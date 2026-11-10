"""
In-memory execution log.

The booking endpoints call add_event() as they run. The browser polls /log
and prints each new line in the Execution Log box, so the student can watch
the two requests interleave in real time.
"""
import itertools
from datetime import datetime

_events = []
# Ids keep increasing even after clear(), so the browser never misses or repeats a line.
_ids = itertools.count(1)


def add_event(message: str) -> None:
    _events.append({
        "id": next(_ids),
        "time": datetime.now().strftime("%H:%M:%S.%f")[:-3],  # millisecond timestamp
        "message": message,
    })


def events_since(last_id: int) -> list:
    return [event for event in _events if event["id"] > last_id]


def clear() -> None:
    _events.clear()
