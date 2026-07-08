import os
from contextlib import asynccontextmanager

import redis.asyncio as redis
from fastapi import FastAPI, HTTPException


REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
COUNTER_PREFIX = "counter:"


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.redis = redis.from_url(REDIS_URL, decode_responses=True)
    try:
        yield
    finally:
        await app.state.redis.aclose()


app = FastAPI(lifespan=lifespan)


@app.post("/hit/{key}")
async def hit(key: str) -> dict[str, str | int]:
    count = await app.state.redis.incr(f"{COUNTER_PREFIX}{key}")
    return {"key": key, "count": count}


@app.get("/count/{key}")
async def count(key: str) -> dict[str, str | int]:
    value = await app.state.redis.get(f"{COUNTER_PREFIX}{key}")
    return {"key": key, "count": int(value) if value is not None else 0}


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    try:
        redis_is_up = await app.state.redis.ping()
    except redis.RedisError as exc:
        raise HTTPException(status_code=503, detail="Redis is unavailable") from exc

    if not redis_is_up:
        raise HTTPException(status_code=503, detail="Redis is unavailable")
    return {"status": "ok", "redis": "up"}
