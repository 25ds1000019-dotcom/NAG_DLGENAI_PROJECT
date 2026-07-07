import time
import uuid

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware


EMAIL = "25ds1000019@ds.study.iitm.ac.in"
ALLOWED_ORIGIN = "https://dash-ujy8zs.example.com"

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[ALLOWED_ORIGIN],
    allow_credentials=False,
    allow_methods=["GET", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID", "X-Process-Time"],
)


@app.middleware("http")
async def request_metadata(request: Request, call_next):
    request_id = str(uuid.uuid4())
    started = time.perf_counter()
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Process-Time"] = f"{time.perf_counter() - started:.6f}"
    return response


@app.get("/stats")
async def stats(values: str = Query(..., min_length=1)):
    parts = [part.strip() for part in values.split(",")]
    if not parts or any(not part for part in parts):
        raise HTTPException(status_code=400, detail="values must contain integers")

    try:
        numbers = [int(part) for part in parts]
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="values must contain integers") from exc

    total = sum(numbers)
    return {
        "email": EMAIL,
        "count": len(numbers),
        "sum": total,
        "min": min(numbers),
        "max": max(numbers),
        "mean": total / len(numbers),
    }
