import asyncpg
from datetime import datetime
from config import DATABASE_URL

_pool: asyncpg.Pool | None = None


async def get_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(DATABASE_URL, ssl="require")
    return _pool


async def init_db():
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id          SERIAL PRIMARY KEY,
                telegram_id BIGINT UNIQUE NOT NULL,
                username    TEXT,
                full_name   TEXT,
                balance     INTEGER DEFAULT 0,
                created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS payments (
                id          SERIAL PRIMARY KEY,
                telegram_id BIGINT NOT NULL,
                amount      INTEGER NOT NULL,
                status      TEXT DEFAULT 'pending',
                created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at  TIMESTAMP,
                approved_at TIMESTAMP,
                FOREIGN KEY (telegram_id) REFERENCES users(telegram_id)
            )
        """)


async def get_user(telegram_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetchrow(
            "SELECT * FROM users WHERE telegram_id = $1", telegram_id
        )


async def create_user(telegram_id: int, username: str, full_name: str):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO users (telegram_id, username, full_name)
            VALUES ($1, $2, $3)
            ON CONFLICT (telegram_id) DO NOTHING
            """,
            telegram_id, username, full_name,
        )


async def update_user_balance(telegram_id: int, amount: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE users SET balance = balance + $1 WHERE telegram_id = $2",
            amount, telegram_id,
        )


async def create_payment(telegram_id: int, amount: int, expires_at: str) -> int:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO payments (telegram_id, amount, status, expires_at)
            VALUES ($1, $2, 'pending', $3::timestamp)
            RETURNING id
            """,
            telegram_id, amount, expires_at,
        )
        return row["id"]


async def get_payment(payment_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetchrow(
            "SELECT * FROM payments WHERE id = $1", payment_id
        )


async def update_payment_status(payment_id: int, status: str):
    approved_at = datetime.now() if status == "approved" else None
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE payments SET status = $1, approved_at = $2 WHERE id = $3",
            status, approved_at, payment_id,
        )


async def get_pending_payment(telegram_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetchrow(
            """
            SELECT * FROM payments
            WHERE telegram_id = $1 AND status IN ('pending', 'waiting_approval')
            ORDER BY created_at DESC LIMIT 1
            """,
            telegram_id,
        )


async def get_all_users():
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetch("SELECT * FROM users ORDER BY created_at DESC")


async def get_all_pending_payments():
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetch(
            """
            SELECT p.*, u.username, u.full_name
            FROM payments p
            JOIN users u ON p.telegram_id = u.telegram_id
            WHERE p.status IN ('pending', 'waiting_approval')
            ORDER BY p.created_at DESC
            """
        )
