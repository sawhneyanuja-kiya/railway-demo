"""
Railway Reservation Demo: Race Condition vs. Synchronized Critical Section.

Two booking endpoints compete for the ONE seat on ONE train:

  POST /book_without_sync  No lock. Shows the RACE CONDITION (double-booking).
  POST /book_with_sync     Protected by asyncio.Lock (a mutex). Prevents it.

OS CONCEPTS USED IN THIS FILE
  Critical section: code that reads and writes a SHARED resource (the seat count).
      Only one execution flow should be inside it at a time.
  Race condition: the result depends on the timing of two flows that both enter
      the critical section at once. Here the result is two people booking one seat.
  Mutex (mutual exclusion lock): a lock that only one flow can hold. Any other
      flow that wants it must wait until the holder releases it.

WHY A RACE CAN HAPPEN IN ASYNCIO (which runs on a single thread)
  asyncio does not run two requests at the exact same instant. Instead, a request
  runs until it hits an `await` (a database call or asyncio.sleep), and then the
  event loop switches to another request. The switch happens at every `await`,
  so the "read, then write later" gap is enough for the race to appear.
"""
import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from database import create_pool, read_seats, write_seats, TRAIN_ID
from event_log import add_event, clear, events_since

FRONTEND_FILE = Path(__file__).resolve().parent.parent / "frontend" / "index.html"

# The MUTEX. One shared object for the whole server process.
# Every request that uses /book_with_sync must hold this lock while it is in the
# critical section. Because the object is shared, all requests see the same lock.
booking_lock = asyncio.Lock()

# Simulated processing time. The sleep sits between "read the seat count" and
# "write the new seat count", which is the window where the race happens.
PROCESSING_SECONDS = 2


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.pool = await create_pool()
    yield
    app.state.pool.close()
    await app.state.pool.wait_closed()


app = FastAPI(lifespan=lifespan)


class BookingRequest(BaseModel):
    user: str = Field(min_length=1, max_length=30)


def get_pool(request: Request):
    return request.app.state.pool


@app.get("/")
async def index():
    return FileResponse(FRONTEND_FILE)


@app.get("/seats")
async def current_seats(pool=Depends(get_pool)):
    return {"available_seats": await read_seats(pool)}


@app.get("/log")
async def log(since: int = 0):
    return {"events": events_since(since)}


@app.post("/reset")
async def reset(pool=Depends(get_pool)):
    # Puts the seat count back to 1 so the demo can be run again.
    await write_seats(pool, 1)
    clear()
    add_event(f"Database reset: train {TRAIN_ID} has 1 seat available")
    return {"available_seats": 1}


@app.post("/book_without_sync")
async def book_without_sync(body: BookingRequest, pool=Depends(get_pool)):
    user = body.user
    add_event(f"{user} trying to book... (no lock)")

    # STEP 1: READ the shared seat count.
    # RACE CONDITION: this read is NOT protected. Another request can read the
    # same value before this request writes anything.
    seats = await read_seats(pool)

    if seats <= 0:
        add_event(f"{user} rejected: {seats} seats left")
        return {"success": False, "user": user}

    # STEP 2: the "gap". asyncio.sleep yields control to the event loop, so the
    # other request runs now. It also reads the seat count and sees 1.
    # Both requests are now past the check and believe the seat is theirs.
    await asyncio.sleep(PROCESSING_SECONDS)

    # STEP 3: WRITE a value computed from the OLD read in step 1. This is a
    # read-modify-write done without a lock. Both requests write 0, so the
    # second write overwrites the first, and both users are told they booked.
    await write_seats(pool, seats - 1)
    add_event(f"{user} booked seat (read {seats}, wrote {seats - 1})")
    return {"success": True, "user": user}


@app.post("/book_with_sync")
async def book_with_sync(body: BookingRequest, pool=Depends(get_pool)):
    user = body.user
    add_event(f"{user} trying to book... (with lock)")

    # If the lock is already held, this request must wait. Log that for the student.
    if booking_lock.locked():
        add_event(f"{user} waiting for lock (another booking is in progress)")

    # `async with` ACQUIRES the mutex before the block and RELEASES it after the
    # block, even if the block returns early or raises an error.
    # Only one request can be inside this block at a time.
    async with booking_lock:
        add_event(f"{user} acquired lock")
        try:
            # CRITICAL SECTION START: read, sleep, write.
            # Any other request that reaches this line must wait at the `async with`
            # above. So it cannot read the seat count until this request has finished
            # writing the new value.
            seats = await read_seats(pool)

            if seats <= 0:
                add_event(f"{user} rejected: {seats} seats left")
                return {"success": False, "user": user}

            await asyncio.sleep(PROCESSING_SECONDS)

            # Safe to write: nobody else can have changed the seat count since we read it.
            await write_seats(pool, seats - 1)
            add_event(f"{user} booked seat (read {seats}, wrote {seats - 1})")
            return {"success": True, "user": user}
            # CRITICAL SECTION END
        finally:
            # Runs on every exit path, so the lock is never left held by mistake.
            add_event(f"{user} released lock")
