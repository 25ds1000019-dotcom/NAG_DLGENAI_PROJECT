import time
import uuid
import os
from pathlib import Path
from typing import Any

import yaml
from dotenv import dotenv_values
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware


EMAIL = "25ds1000019@ds.study.iitm.ac.in"
BASE_DIR = Path(__file__).resolve().parent

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
    allow_origins=["https://dash-ujy8zs.example.com"],
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
