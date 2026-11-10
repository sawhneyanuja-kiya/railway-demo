"""
MySQL access for the single `trains` table.

Every function here does ONE small job: read or write the seat count.
The booking logic (and the locking) lives in main.py, not here.
"""
import os

import aiomysql

TRAIN_ID = 1


async def create_pool():
    # A connection POOL is a set of open database connections that requests borrow and return.
    # Two requests can therefore talk to MySQL at the same time, which is what makes the race possible.
    return await aiomysql.create_pool(
        host=os.getenv("MYSQL_HOST", "127.0.0.1"),
        port=int(os.getenv("MYSQL_PORT", "3306")),
        user=os.getenv("MYSQL_USER", "root"),
        password=os.getenv("MYSQL_PASSWORD", ""),
        db=os.getenv("MYSQL_DATABASE", "railway_demo"),
        autocommit=True,  # every statement is saved immediately, so no hidden transactions
        minsize=1,
        maxsize=10,
    )


async def read_seats(pool) -> int:
    # READ of the shared resource (the seat count).
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT available_seats FROM trains WHERE id = %s", (TRAIN_ID,)
            )
            row = await cur.fetchone()
    if row is None:
        raise RuntimeError("Train not found. Run backend/schema.sql in MySQL first.")
    return row[0]


async def write_seats(pool, seats: int) -> None:
    # WRITE to the shared resource (the seat count).
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "UPDATE trains SET available_seats = %s WHERE id = %s",
                (seats, TRAIN_ID),
            )
