# Question 4: FastAPI + Redis via Docker Compose

Start the stack:

```bash
docker compose up --build -d
```

Test it locally:

```bash
curl http://localhost:8000/healthz
curl -X POST http://localhost:8000/hit/example
curl http://localhost:8000/count/example
```

The `api` service is published on local port 8000. Redis is reachable only on
the internal Compose network, and its data is stored in the `redis_data` volume.
