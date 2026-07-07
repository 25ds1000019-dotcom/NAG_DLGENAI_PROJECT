import time
import uuid
import os
import secrets
import json
import threading
import re
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import yaml
from dotenv import dotenv_values
from fastapi import Body, FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field
from starlette.middleware.base import BaseHTTPMiddleware

from token_verify import TokenVerificationError, verify_jwt


EMAIL = "25ds1000019@ds.study.iitm.ac.in"
ANALYTICS_API_KEY = os.getenv(
    "ANALYTICS_API_KEY", "ak_6zj0h4yyq5kk9y4b1dh46gsu"
)
BASE_DIR = Path(__file__).resolve().parent
START_TIME = time.monotonic()
STATE_LOCK = threading.Lock()
HTTP_REQUESTS_TOTAL = 0
RECENT_LOGS = deque(maxlen=1000)

DEFAULTS = {
    "port": 8000,
    "workers": 1,
    "debug": False,
    "log_level": "info",
    "api_key": "default-secret-000",
}

ENV_KEYS = {
    "APP_PORT": "port",
    "APP_WORKERS": "workers",
    "APP_DEBUG": "debug",
    "APP_LOG_LEVEL": "log_level",
    "APP_API_KEY": "api_key",
}

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


class RequestHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        global HTTP_REQUESTS_TOTAL

        start = time.perf_counter()
        request_id = str(uuid.uuid4())
        status_code = 500
        level = "INFO"

        try:
            response = await call_next(request)
            status_code = response.status_code
            if status_code >= 500:
                level = "ERROR"
            elif status_code >= 400:
                level = "WARNING"
            response.headers["X-Request-ID"] = request_id
            response.headers["X-Process-Time"] = f"{time.perf_counter() - start:.6f}"
            return response
        except Exception:
            level = "ERROR"
            raise
        finally:
            entry = {
                "level": level,
                "ts": datetime.now(timezone.utc).isoformat(),
                "path": request.url.path,
                "request_id": request_id,
                "status_code": status_code,
            }
            with STATE_LOCK:
                HTTP_REQUESTS_TOTAL += 1
                RECENT_LOGS.append(entry)
            print(json.dumps(entry, separators=(",", ":")), flush=True)


app.add_middleware(RequestHeadersMiddleware)


class InvoiceRequest(BaseModel):
    text: str = Field(min_length=1)


class InvoiceExtraction(BaseModel):
    vendor: str = Field(min_length=1)
    amount: float
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")


def extract_vendor(text: str) -> Optional[str]:
    marker = re.search(
        r"(?is)\b(?:vendor|supplier|seller|from|issued by|billed by)\s*"
        r"(?:is|:|-)?\s*(.+?)\s*"
        r"(?=(?:[.;]\s*(?:invoice|total|amount|currency|payment|due)\b)|\n|$)",
        text,
    )
    if marker:
        vendor = marker.group(1).strip(" ,;")
        if re.search(r"\b(?:Ltd|Inc|Corp)$", vendor, re.IGNORECASE):
            vendor += "."
        return vendor

    company = re.search(
        r"([A-Z][A-Za-z0-9&,'’\.\- ]{1,100}?"
        r"(?:Industries\s+Ltd\.?|Ltd\.?|Limited|Inc\.?|LLC|Corp\.?|Corporation))",
        text,
    )
    return company.group(1).strip(" ,;") if company else None


def extract_amount(text: str) -> Optional[float]:
    number = r"([0-9]+(?:,[0-9]{3})*(?:\.[0-9]{1,2})?)"
    patterns = [
        rf"(?i)(?:total\s+(?:amount\s+)?due|amount\s+due|balance\s+due|grand\s+total|total)"
        rf"\s*(?:is|:|-)?\s*(?:USD|EUR|GBP|[$€£])?\s*{number}",
        rf"(?i)(?:USD|EUR|GBP|[$€£])\s*{number}",
        rf"(?i){number}\s*(?:USD|EUR|GBP)\b",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return float(match.group(1).replace(",", ""))
    return None


@app.post("/extract", response_model=InvoiceExtraction)
async def extract_invoice(payload: InvoiceRequest) -> InvoiceExtraction:
    text = payload.text.strip()
    if not text:
        raise HTTPException(status_code=422, detail="text must not be empty")

    vendor = extract_vendor(text)
    amount = extract_amount(text)
    currency_match = re.search(r"\b(USD|EUR|GBP)\b", text, re.IGNORECASE)
    date_match = re.search(r"\b(2026-(?:0[1-9]|1[0-2])-(?:0[1-9]|[12]\d|3[01]))\b", text)

    if not all((vendor, amount is not None, currency_match, date_match)):
        raise HTTPException(status_code=422, detail="Could not extract invoice fields")

    return InvoiceExtraction(
        vendor=vendor,
        amount=amount,
        currency=currency_match.group(1).upper(),
        date=date_match.group(1),
    )


@app.get("/work")
async def work(n: int = Query(..., ge=0, le=1_000_000)):
    for unit in range(n):
        unit * unit
    return {"email": EMAIL, "done": n}


@app.get("/metrics")
async def metrics():
    with STATE_LOCK:
        count = HTTP_REQUESTS_TOTAL
    content = (
        "# HELP http_requests_total Total HTTP requests.\n"
        "# TYPE http_requests_total counter\n"
        f"http_requests_total {float(count)}\n"
    )
    return Response(content=content, media_type="text/plain; version=0.0.4")


@app.get("/healthz")
async def healthz():
    return {"status": "ok", "uptime_s": max(0.0, time.monotonic() - START_TIME)}


@app.get("/logs/tail")
async def logs_tail(limit: int = Query(100, ge=1, le=1000)):
    with STATE_LOCK:
        return list(RECENT_LOGS)[-limit:]


@app.post("/analytics")
async def analytics(
    payload: Any = Body(...),
    api_key: Optional[str] = Header(default=None, alias="X-API-Key"),
):
    if api_key is None or not secrets.compare_digest(api_key, ANALYTICS_API_KEY):
        raise HTTPException(status_code=401, detail="Unauthorized")

    events = payload.get("events") if isinstance(payload, dict) else None
    if not isinstance(events, list):
        raise HTTPException(status_code=400, detail="events must be a list")

    users: set[Any] = set()
    positive_totals: dict[Any, float] = {}
    revenue = 0.0

    for event in events:
        if not isinstance(event, dict) or "user" not in event:
            raise HTTPException(status_code=400, detail="Invalid event")
        user = event["user"]
        amount = event.get("amount", 0)
        if not isinstance(user, str) or not isinstance(amount, (int, float)):
            raise HTTPException(status_code=400, detail="Invalid event")

        users.add(user)
        if amount > 0:
            revenue += amount
            positive_totals[user] = positive_totals.get(user, 0.0) + amount

    top_user = max(positive_totals, key=positive_totals.get) if positive_totals else None
    return {
        "email": EMAIL,
        "total_events": len(events),
        "unique_users": len(users),
        "revenue": revenue,
        "top_user": top_user,
    }


@app.post("/verify")
async def verify_token(payload: Any = Body(...)) -> JSONResponse:
    token = payload.get("token") if isinstance(payload, dict) else None
    if not isinstance(token, str) or not token:
        return JSONResponse(status_code=401, content={"valid": False})

    try:
        verified = verify_jwt(token)
    except TokenVerificationError:
        return JSONResponse(status_code=401, content={"valid": False})

    return JSONResponse(
        content={
            "valid": True,
            "email": verified.email,
            "sub": verified.sub,
            "aud": verified.aud,
        }
    )


def coerce_value(key: str, value: Any) -> Any:
    if key in {"port", "workers"}:
        try:
            return int(value)
        except (TypeError, ValueError) as exc:
            raise HTTPException(
                status_code=400,
                detail=f"{key} must be an integer",
            ) from exc
    if key == "debug":
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() in {"true", "1", "yes", "on"}
    return str(value)


def base_config() -> dict[str, Any]:
    config: dict[str, Any] = dict(DEFAULTS)

    environment = os.getenv("APP_ENV", "development")
    yaml_path = BASE_DIR / f"config.{environment}.yaml"
    if yaml_path.exists():
        with yaml_path.open(encoding="utf-8") as yaml_file:
            yaml_config = yaml.safe_load(yaml_file) or {}
        if not isinstance(yaml_config, dict):
            raise HTTPException(status_code=500, detail="Invalid YAML configuration")
        config.update(yaml_config)

    dotenv_config = dotenv_values(BASE_DIR / ".env")
    for env_key, value in dotenv_config.items():
        if value is None:
            continue
        key = "workers" if env_key == "NUM_WORKERS" else ENV_KEYS.get(env_key)
        if key:
            config[key] = value

    for env_key, key in ENV_KEYS.items():
        if env_key in os.environ:
            config[key] = os.environ[env_key]

    return config


@app.get("/effective-config")
async def effective_config(
    set_values: list[str] = Query(default=[], alias="set"),
):
    config = base_config()

    for override in set_values:
        if "=" not in override:
            raise HTTPException(
                status_code=400,
                detail="Each set override must use key=value",
            )
        key, value = override.split("=", 1)
        key = key.strip().lower()
        if not key:
            raise HTTPException(status_code=400, detail="Override key cannot be empty")
        config[key] = value

    result = {key: coerce_value(key, value) for key, value in config.items()}
    result["api_key"] = "****"
    return result


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
