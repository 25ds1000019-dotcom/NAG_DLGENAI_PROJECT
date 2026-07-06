# NAG DLGenAI Project

FastAPI service for descriptive statistics with a strict per-origin CORS policy.

## Endpoint

`GET /stats?values=1,2,3`

Returns:

```json
{
  "email": "25ds1000019@ds.study.iitm.ac.in",
  "count": 3,
  "sum": 6,
  "min": 1,
  "max": 3,
  "mean": 2.0
}
```

## CORS

Only `https://dash-ujy8zs.example.com` is allowed.

## Run locally

```bash
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000
```
