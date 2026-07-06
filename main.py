import time
import uuid

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware


ALLOWED_ORIGIN = "https://dash-ujy8zs.example.com"
EMAIL = "25ds1000019@ds.study.iitm.ac.in"

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[ALLOWED_ORIGIN],
    allow_credentials=False,
    allow_methods=["GET", "OPTIONS"],
    allow_headers=["*"],
)


class RequestHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        start = time.perf_counter()
        response = await call_next(request)
        elapsed = time.perf_counter() - start
        response.headers["X-Request-ID"] = str(uuid.uuid4())
        response.headers["X-Process-Time"] = f"{elapsed:.6f}"
        return response


app.add_middleware(RequestHeadersMiddleware)


def parse_values(values: str) -> list[int]:
    try:
        nums = [int(part.strip()) for part in values.split(",") if part.strip()]
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail="values must contain integers only",
        ) from exc

    if not nums:
        raise HTTPException(
            status_code=400,
            detail="No values supplied",
        )

    return nums


@app.get("/stats")
async def stats(values: str = Query(...)):
    nums = parse_values(values)
    total = sum(nums)

    return {
        "email": EMAIL,
        "count": len(nums),
        "sum": total,
        "min": min(nums),
        "max": max(nums),
        "mean": total / len(nums),
    }
